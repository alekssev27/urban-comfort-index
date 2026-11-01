'''Fetch Mesto infrastructure from OSM and preserve green-area polygons.'''
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from typing import Any
import requests
from shapely.geometry import Point, Polygon, MultiPolygon, mapping, shape, LineString
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "data/raw/city_boundary.geojson"
OUTPUT_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
POINTS_PATH = ROOT / "data/raw/infrastructure_points.geojson"
GREEN_PATH = ROOT / "data/raw/green_areas.geojson"
GREEN_ADDITIONAL_PATH = ROOT / "data/raw/green_areas_additional.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "urban-comfort-index-student-project/0.2 (OSM research)"

CATEGORY_RULES = [
    ("transport", "highway", {"bus_stop"}),
    ("transport", "public_transport", {"platform", "stop_position", "station"}),
    ("education", "amenity", {"school", "kindergarten", "college", "university", "music_school"}),
    ("medical", "amenity", {"hospital", "clinic", "doctors", "dentist", "pharmacy"}),
    ("medical", "healthcare", {"hospital", "clinic", "doctor", "dentist", "centre"}),
    ("daily", "shop", {"supermarket", "convenience", "greengrocer", "bakery", "butcher", "chemist", "general", "food"}),
    ("daily", "amenity", {"post_office", "bank", "atm", "marketplace"}),
    ("green", "leisure", {"park", "garden", "nature_reserve"}),
    ("green", "landuse", {"forest", "recreation_ground"}),
    ("green_additional", "leisure", {"playground"}),
    ("green_additional", "landuse", {"grass"}),
    ("leisure", "amenity", {"cinema", "theatre", "arts_centre", "community_centre", "library", "cafe", "restaurant", "fast_food", "bar"}),
    ("leisure", "leisure", {"sports_centre", "fitness_centre", "stadium", "swimming_pool"}),
]

def assign_category(tags: dict[str, Any]) -> str | None:
    for category, key, values in CATEGORY_RULES:
        if tags.get(key) in values:
            return category
    return None

def load_boundary(path: Path):
    if not path.exists():
        raise SystemExit(f"Не найдена граница: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    if len(features) != 1:
        raise SystemExit("Ожидается FeatureCollection с одним проверенным полигоном границы.")
    boundary = shape(features[0]["geometry"])
    if boundary.is_empty or not boundary.is_valid or boundary.geom_type not in {"Polygon", "MultiPolygon"}:
        raise SystemExit("Геометрия границы невалидна.")
    return boundary

def element_geometry(element: dict[str, Any]):
    kind = element.get("type")
    if kind == "node":
        if "lon" in element and "lat" in element:
            return Point(float(element["lon"]), float(element["lat"]))
        return None
    if kind == "way":
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", []) if "lon" in p and "lat" in p]
        if len(coords) < 2:
            return None
        if len(coords) >= 4 and coords[0] == coords[-1]:
            return Polygon(coords)
        return LineString(coords)
    if kind == "relation":
        outers, inners = [], []
        for member in element.get("members", []):
            if member.get("type") != "way":
                continue
            coords = [(p["lon"], p["lat"]) for p in member.get("geometry", []) if "lon" in p and "lat" in p]
            if len(coords) < 4 or coords[0] != coords[-1]:
                continue
            ring = Polygon(coords)
            if ring.is_empty or ring.area == 0:
                continue
            if member.get("role") == "inner":
                inners.append(ring)
            elif member.get("role") == "outer":
                outers.append(ring)
        if not outers:
            return None
        polygons = []
        for outer in outers:
            holes = [list(inner.exterior.coords) for inner in inners if outer.contains(inner.representative_point())]
            polygons.append(Polygon(outer.exterior.coords, holes))
        return MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
    return None

def polygonal(geom):
    if geom is None or geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms if g.geom_type == "Polygon" and not g.is_empty]
        if not parts:
            return None
        geom = MultiPolygon(parts) if len(parts) > 1 else parts[0]
    return geom if geom.geom_type in {"Polygon", "MultiPolygon"} and not geom.is_empty else None

def build_feature(element, boundary):
    tags = element.get("tags", {})
    category = assign_category(tags)
    if category is None:
        return None
    geom = element_geometry(element)
    if category == "green":
        # Main green infrastructure requires polygon geometry; points are rejected.
        geom = polygonal(geom)
        if geom is None:
            return None
    elif category == "green_additional":
        # Keep polygon geometry when available; point amenities remain additional.
        area_geom = polygonal(geom)
        if area_geom is not None:
            geom = area_geom
    if geom is None or geom.is_empty or not boundary.intersects(geom):
        return None
    try:
        geom = geom.intersection(boundary)
    except Exception:
        return None
    if geom.is_empty:
        return None
    props = {
        "osm_type": element.get("type"), "osm_id": element.get("id"),
        "category": category, "name": tags.get("name"), "tags": tags,
        "source": "OpenStreetMap via Overpass API", "license": "OpenStreetMap data, ODbL 1.0"
    }
    return {"type": "Feature", "geometry": mapping(geom), "properties": props}

def collection(name: str, features: list[dict], timestamp: str):
    return {"type": "FeatureCollection", "name": name, "metadata": {
        "retrieved_at_utc": timestamp, "source_url": OVERPASS_URL,
        "license": "OpenStreetMap data, ODbL 1.0",
        "warning": "Coverage and category mapping require manual review."
    }, "features": features}

def write_geojson(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=BOUNDARY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                        help="Legacy combined GeoJSON output path.")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    boundary = load_boundary(args.boundary)
    query_boundary = boundary.simplify(0.001, preserve_topology=True)
    if query_boundary.geom_type == "MultiPolygon":
        query_boundary = max(query_boundary.geoms, key=lambda g: g.area)
    coords = list(query_boundary.exterior.coords)
    if len(coords) > 250:
        coords = coords[::max(1, len(coords) // 249)]
        if coords[-1] != coords[0]:
            coords.append(coords[0])
    poly = " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in coords)
    query = (
        f'[out:json][timeout:{args.timeout}];( '
        f'nwr(poly:"{poly}")[highway="bus_stop"];'
        f'nwr(poly:"{poly}")[public_transport~"^(platform|stop_position|station)$"];'
        f'nwr(poly:"{poly}")[amenity~"^(school|kindergarten|college|university|music_school|hospital|clinic|doctors|dentist|pharmacy|post_office|bank|atm|marketplace|cinema|theatre|arts_centre|community_centre|library|cafe|restaurant|fast_food|bar)$"];'
        f'nwr(poly:"{poly}")[healthcare~"^(hospital|clinic|doctor|dentist|centre)$"];'
        f'nwr(poly:"{poly}")[shop~"^(supermarket|convenience|greengrocer|bakery|butcher|chemist|general|food)$"];'
        f'nwr(poly:"{poly}")[leisure~"^(park|garden|playground|nature_reserve|sports_centre|fitness_centre|stadium|swimming_pool)$"];'
        f'nwr(poly:"{poly}")[landuse~"^(grass|recreation_ground|forest)$"];'
        f');out geom tags;'
    )
    response = requests.post(OVERPASS_URL, data={"data": query},
        headers={"User-Agent": USER_AGENT}, timeout=args.timeout + 30)
    response.raise_for_status()
    features, seen = [], set()
    for element in response.json().get("elements", []):
        key = (element.get("type"), element.get("id"))
        if key in seen:
            continue
        seen.add(key)
        feature = build_feature(element, boundary)
        if feature:
            features.append(feature)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    points = [f for f in features if f["geometry"]["type"] == "Point"
              and f["properties"]["category"] not in {"green", "green_additional"}]
    green = [f for f in features if f["properties"]["category"] == "green"]
    green_extra = [f for f in features if f["properties"]["category"] == "green_additional"]
    write_geojson(args.output, collection("magnitogorsk_osm_infrastructure", features, timestamp))
    write_geojson(POINTS_PATH, collection("magnitogorsk_osm_infrastructure_points", points, timestamp))
    write_geojson(GREEN_PATH, collection("magnitogorsk_osm_green_areas", green, timestamp))
    write_geojson(GREEN_ADDITIONAL_PATH, collection("magnitogorsk_osm_green_areas_additional", green_extra, timestamp))
    counts = {}
    for feature in features:
        category = feature["properties"]["category"]
        counts[category] = counts.get(category, 0) + 1
    print(f"Сохранено объектов: {len(features)} -> {args.output}")
    print("По категориям:", json.dumps(counts, ensure_ascii=False))
    print(f"Основные зелёные зоны: {len(green)} -> {GREEN_PATH}")
    print(f"Дополнительные зелёные объекты: {len(green_extra)} -> {GREEN_ADDITIONAL_PATH}")
    print("Данные OSM требуют проверки покрытия и классификации перед расчётом индекса.")

if __name__ == "__main__":
    main()
