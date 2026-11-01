"""Utilities for grouping OSM transport-stop elements into physical stops."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, shape, mapping
from shapely.ops import transform


DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_MERGE_RADIUS_M = 25.0

_MODE_TAGS = {
    "bus": "bus",
    "tram": "tram",
    "trolleybus": "trolleybus",
    "train": "train",
    "light_rail": "light_rail",
    "subway": "subway",
    "monorail": "monorail",
}


def _representative_point(feature: dict[str, Any], transformer: Transformer):
    geometry = shape(feature["geometry"])
    if geometry.is_empty:
        return None
    point = geometry if isinstance(geometry, Point) else geometry.representative_point()
    return transform(transformer.transform, point)


def _transport_modes(tags: dict[str, Any]) -> set[str]:
    modes = set()
    for key, mode in _MODE_TAGS.items():
        if tags.get(key) in {"yes", "designated", "official"}:
            modes.add(mode)
    route = tags.get("route")
    if route in _MODE_TAGS:
        modes.add(_MODE_TAGS[route])
    railway = tags.get("railway")
    if railway in {"tram_stop", "tram"}:
        modes.add("tram")
    if railway in {"station", "halt"}:
        modes.add("train")
    # A bus_stop/platform without explicit mode tags is not assumed to support
    # every public-transport mode; leave its mode list empty.
    return modes


def deduplicate_transport_features(
    features: list[dict[str, Any]],
    merge_radius_m: float = DEFAULT_MERGE_RADIUS_M,
    metric_crs: str = DEFAULT_METRIC_CRS,
) -> list[dict[str, Any]]:
    """Group nearby OSM stop elements without discarding their source IDs.

    Features are expected in WGS84/CRS84 coordinates. A complete-link distance
    condition is used: every member of a group must be within merge_radius_m of
    every other member. This prevents long chains of nearby stops from merging.
    """
    if merge_radius_m <= 0:
        raise ValueError("merge_radius_m must be positive")

    transformer = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True)
    candidates = []
    for feature in features:
        props = feature.get("properties", {})
        if props.get("category") != "transport":
            continue
        point = _representative_point(feature, transformer)
        if point is None:
            continue
        candidates.append((feature, point))

    candidates.sort(key=lambda item: (
        str(item[0].get("properties", {}).get("osm_type", "")),
        int(item[0].get("properties", {}).get("osm_id", 0) or 0),
    ))

    groups: list[list[tuple[dict[str, Any], Point]]] = []
    for candidate in candidates:
        _, point = candidate
        matching = next(
            (group for group in groups
             if all(point.distance(member_point) <= merge_radius_m for _, member_point in group)),
            None,
        )
        if matching is None:
            groups.append([candidate])
        else:
            matching.append(candidate)

    result = []
    inverse = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True)
    for index, group in enumerate(groups, start=1):
        # Use the mean projected coordinates as the representative stop point.
        x = sum(point.x for _, point in group) / len(group)
        y = sum(point.y for _, point in group) / len(group)
        lon, lat = inverse.transform(x, y)
        modes = set()
        members = []
        names = []
        for feature, _ in group:
            props = feature.get("properties", {})
            tags = props.get("tags") or {}
            modes.update(_transport_modes(tags))
            members.append({
                "osm_type": props.get("osm_type"),
                "osm_id": props.get("osm_id"),
                "name": props.get("name"),
                "public_transport": tags.get("public_transport"),
                "highway": tags.get("highway"),
            })
            if props.get("name"):
                names.append(props["name"])
        unique_names = sorted(set(names))
        result.append({
            "type": "Feature",
            "geometry": mapping(Point(lon, lat)),
            "properties": {
                "stop_group_id": f"osm_stop_{index}",
                "category": "transport",
                "name": unique_names[0] if len(unique_names) == 1 else None,
                "member_count": len(group),
                "member_osm_objects": members,
                "transport_modes": sorted(modes),
                "deduplication_radius_m": merge_radius_m,
                "deduplication_method": "complete_link_euclidean",
            },
        })
    return result
