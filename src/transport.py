"""Utilities for grouping OSM transport-stop elements into physical-stop candidates."""
from __future__ import annotations

import re
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
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
_NAME_PREFIXES = (
    "остановка общественного транспорта",
    "остановка",
    "улица",
    "ул",
    "проспект",
    "просп",
    "пр",
    "площадь",
    "пл",
)


def _normalise_name(value: Any) -> str | None:
    """Normalise common OSM stop-name variants without guessing identities."""
    if not isinstance(value, str) or not value.strip():
        return None
    name = value.casefold().replace("ё", "е")
    name = re.sub(r"[^\w\s-]", " ", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    changed = True
    while changed:
        changed = False
        for prefix in _NAME_PREFIXES:
            if name == prefix:
                name = ""
                changed = True
                break
            if name.startswith(prefix + " "):
                name = name[len(prefix):].strip()
                changed = True
                break
    return name or None


def _names_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_name = _normalise_name(left.get("properties", {}).get("name"))
    right_name = _normalise_name(right.get("properties", {}).get("name"))
    # Missing names are inconclusive; two explicitly different names are a
    # strong signal that nearby elements may be separate physical stops.
    return not (left_name and right_name and left_name != right_name)


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
    return modes


def deduplicate_transport_features(
    features: list[dict[str, Any]],
    merge_radius_m: float = DEFAULT_MERGE_RADIUS_M,
    metric_crs: str = DEFAULT_METRIC_CRS,
) -> list[dict[str, Any]]:
    """Group nearby OSM stop elements into candidate physical stops.

    Features are expected in WGS84 coordinates. Every pair in a group must be
    within merge_radius_m (complete-link), and explicitly different names are
    never merged. Missing names do not prevent a spatial match.
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
        feature, point = candidate
        matching = next(
            (
                group for group in groups
                if all(
                    point.distance(member_point) <= merge_radius_m
                    and _names_compatible(feature, member_feature)
                    for member_feature, member_point in group
                )
            ),
            None,
        )
        if matching is None:
            groups.append([candidate])
        else:
            matching.append(candidate)

    result = []
    inverse = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True)
    for index, group in enumerate(groups, start=1):
        x = sum(point.x for _, point in group) / len(group)
        y = sum(point.y for _, point in group) / len(group)
        lon, lat = inverse.transform(x, y)
        modes = set()
        members = []
        names = []
        for feature, member_point in group:
            props = feature.get("properties", {})
            tags = props.get("tags") or {}
            modes.update(_transport_modes(tags))
            member_lon, member_lat = inverse.transform(member_point.x, member_point.y)
            members.append({
                "osm_type": props.get("osm_type"),
                "osm_id": props.get("osm_id"),
                "name": props.get("name"),
                "longitude": member_lon,
                "latitude": member_lat,
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
                "deduplication_method": "complete_link_with_name_guard",
            },
        })
    return result
