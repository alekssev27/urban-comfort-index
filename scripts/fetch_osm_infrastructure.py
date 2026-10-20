"""Fetch a first-pass set of infrastructure POIs from OpenStreetMap/Overpass.

OSM coverage is incomplete and the tag-to-category mapping is provisional.
Review the resulting GeoJSON before calculating any published index.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from shapely.geometry import Point, shape, mapping

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "data" / "raw" / "city_boundary.geojson"
OUTPUT_PATH = ROOT / "data" / "raw" / "infrastructure_osm.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "urban-comfort-index-student-project/0.1 (OSM research)"

# Broad first-pass categories. The final mapping needs review by the team.
CATEGORY_RULES = [
    ("transport", "highway", {"bus_stop", "platform"}),
    ("transport", "public_transport", {"platform", "stop_position", "station"}),
    ("education", "amenity", {"school", "kindergarten", "college", "university", "music_school"}),
    ("medical", "amenity", {"hospital", "clinic", "doctors", "dentist"}),
    ("medical", "healthcare", {"hospital", "clinic", "doctor", "centre", "doctor"}),
    ("medical", "amenity", {"pharmacy"}),
    ("daily", "shop", {"supermarket", "convenience", "greengrocer", "bakery", "butcher", "chemist"}),
    ("daily", "amenity", {"post_office", "bank", "atm", "marketplace"}),
    ("green", "leisure", {"park", "garden", "playground", "nature_reserve"}),
    ("green", "landuse", {"grass", "recreation_ground", "forest"}),
    ("leisure", "amenity", {"cinema", "theatre", "arts_centre", "community_centre", "library"}),
    ("leisure", "leisure", {"sports_centre", "fitness_centre", "stadium", "swimming_pool"}),
]


def assign_category(tags: dict) -> str | None:
    for category, key, values in CATEGORY_RULES:
        if tags.get(key) in values:
            return category
    # Other shops are included in everyday infrastructure but remain broad.
    if tags.get("shop"):
        return "daily"
    return None


def load_boundary(path: Path):
    if not path.exists():
        raise SystemExit(f"Не найдена граница: {path}. Сначала запустите scripts/fetch_osm_boundary.py и проверьте её.")
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != 1:
        raise SystemExit("Ожидается FeatureCollection с одним проверенным полигоном границы.")
    geometry = shape(features[0]["geometry"])
    if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise SystemExit("Геометрия границы невалидна.")
    return geometry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=BOUNDARY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    boundary = load_boundary(args.boundary)
    # Simplify only the query outline to keep Overpass requests manageable;
    # all returned objects are subsequently filtered against the original boundary.
    query_boundary = boundary.simplify(0.001, preserve_topology=True)
    if query_boundary.geom_type == "MultiPolygon":
        query_boundary = max(query_boundary.geoms, key=lambda geom: geom.area)
    coords = list(query_boundary.exterior.coords)
    if len(coords) > 250:
        step = max(1, len(coords) // 249)
        coords = coords[::step]
        if coords[-1] != coords[0]:
            coords.append(coords[0])
    poly = " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in coords)
    query = f'''[out:json][timeout:{args.timeout}];
(
  nwr(poly:"{poly}")[highway~"^(bus_stop|platform)$"];
  nwr(poly:"{poly}")[public_transport~"^(platform|stop_position|station)$"];
  nwr(poly:"{poly}")[amenity~"^(school|kindergarten|college|university|music_school|hospital|clinic|doctors|dentist|pharmacy|post_office|bank|atm|marketplace|cinema|theatre|arts_centre|community_centre|library)$"];
  nwr(poly:"{poly}")[healthcare~"^(hospital|clinic|doctor|centre)$"];
  nwr(poly:"{poly}")[shop];
  nwr(poly:"{poly}")[leisure~"^(park|garden|playground|nature_reserve|sports_centre|fitness_centre|stadium|swimming_pool)$"];
  nwr(poly:"{poly}")[landuse~"^(grass|recreation_ground|forest)$"];
);
out center tags;'''
    response = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=args.timeout + 30)
    response.raise_for_status()
    payload = response.json()
    features = []
    seen = set()
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        category = assign_category(tags)
        if not category:
            continue
        lat = element.get("lat", (element.get("center") or {}).get("lat"))
        lon = element.get("lon", (element.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        point = Point(float(lon), float(lat))
        if not boundary.covers(point):
            continue
        key = (element.get("type"), element.get("id"))
        if key in seen:
            continue
        seen.add(key)
        props = {"osm_type": element.get("type"), "osm_id": element.get("id"), "category": category,
                 "name": tags.get("name"), "tags": tags, "source": "OpenStreetMap via Overpass API",
                 "license": "OpenStreetMap data, ODbL 1.0"}
        features.append({"type": "Feature", "geometry": mapping(point), "properties": props})
    collection = {"type": "FeatureCollection", "name": "magnitogorsk_osm_infrastructure",
                  "metadata": {"retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "source_url": OVERPASS_URL, "license": "OpenStreetMap data, ODbL 1.0",
                               "warning": "Coverage and category mapping require manual review."},
                  "features": features}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for feature in features:
        category = feature["properties"]["category"]
        counts[category] = counts.get(category, 0) + 1
    print(f"Сохранено объектов: {len(features)} -> {args.output}")
    print("По категориям:", json.dumps(counts, ensure_ascii=False))
    print("Это первичная OSM-выгрузка; проверьте покрытие и ошибочную классификацию перед расчётом индекса.")


if __name__ == "__main__":
    main()
