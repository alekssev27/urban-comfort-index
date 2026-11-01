"""Получить из OpenStreetMap контуры жилых зданий Магнитогорска."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape, mapping

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "data/raw/city_boundary.geojson"
OUTPUT_PATH = ROOT / "data/raw/residential_buildings_osm.geojson"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "urban-comfort-index-student-project/0.3 (residential building footprints)"

RESIDENTIAL_BUILDING_VALUES = {
    "house", "residential", "apartments", "detached",
    "semidetached_house", "terrace", "bungalow", "dormitory",
}


def load_boundary(path: Path):
    if not path.exists():
        raise SystemExit(f"Не найдена граница города: {path}")
    frame = gpd.read_file(path)
    if frame.empty or frame.crs is None:
        raise SystemExit("Граница города пуста или CRS не указана.")
    return frame.to_crs("EPSG:4326").geometry.union_all()


def element_polygon(element):
    kind = element.get("type")
    if kind == "way":
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])
                  if "lon" in p and "lat" in p]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            polygon = Polygon(coords)
            return polygon if polygon.is_valid and not polygon.is_empty else None
    elif kind == "relation":
        outers, inners = [], []
        for member in element.get("members", []):
            if member.get("type") != "way":
                continue
            coords = [(p["lon"], p["lat"]) for p in member.get("geometry", [])
                      if "lon" in p and "lat" in p]
            if len(coords) < 4 or coords[0] != coords[-1]:
                continue
            ring = Polygon(coords)
            if ring.is_empty or not ring.is_valid:
                continue
            if member.get("role") == "inner":
                inners.append(ring)
            elif member.get("role") == "outer":
                outers.append(ring)
        polygons = []
        for outer in outers:
            holes = [list(inner.exterior.coords) for inner in inners
                     if outer.contains(inner.representative_point())]
            polygons.append(Polygon(outer.exterior.coords, holes))
        if polygons:
            return MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=BOUNDARY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    boundary = load_boundary(args.boundary)
    query_boundary = boundary.simplify(0.001, preserve_topology=True)
    if query_boundary.geom_type == "MultiPolygon":
        query_boundary = max(query_boundary.geoms, key=lambda geom: geom.area)
    coords = list(query_boundary.exterior.coords)
    if len(coords) > 250:
        coords = coords[::max(1, len(coords) // 249)]
        if coords[-1] != coords[0]:
            coords.append(coords[0])
    polygon = " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in coords)
    building_values = "|".join(sorted(RESIDENTIAL_BUILDING_VALUES))
    query = (
        f'[out:json][timeout:{args.timeout}];('
        f'nwr(poly:"{polygon}")["building"~"^({building_values})$"];'
        f'nwr(poly:"{polygon}")["building:use"="residential"];'
        f');out geom;'
    )
    response = None
    errors = []
    for endpoint in OVERPASS_URLS:
        for attempt in range(1, 3):
            try:
                print(f"Запрос к {endpoint} (попытка {attempt}/2)...")
                candidate = requests.post(
                    endpoint, data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=args.timeout + 30,
                )
                candidate.raise_for_status()
                response = candidate
                print(f"Успешный ответ от {endpoint}")
                break
            except requests.RequestException as error:
                errors.append(f"{endpoint}: {error}")
                print(f"Сервер временно недоступен: {error}")
                if attempt < 2:
                    time.sleep(5)
        if response is not None:
            break

    if response is None:
        details = "\\n".join(errors)
        raise SystemExit(
            "Не удалось получить данные ни с одного сервера Overpass. "
            "Файл не перезаписан. Ошибки:\\n" + details
        )

    features, seen = [], set()
    for element in response.json().get("elements", []):
        key = (element.get("type"), element.get("id"))
        if key in seen:
            continue
        seen.add(key)
        geometry = element_polygon(element)
        if geometry is None or geometry.is_empty or not boundary.intersects(geometry):
            continue
        tags = element.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": mapping(geometry),
            "properties": {
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
                "building": tags.get("building"),
                "building_use": tags.get("building:use"),
                "name": tags.get("name"),
                "source": "OpenStreetMap",
                "license": "ODbL 1.0",
            },
        })

    if not features:
        raise SystemExit("Overpass не вернул жилых зданий; файл не перезаписан.")

    output = {
        "type": "FeatureCollection",
        "name": "magnitogorsk_residential_buildings",
        "metadata": {
            "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "OpenStreetMap via Overpass API",
            "source_url": response.url,
            "license": "ODbL 1.0",
            "building_values": sorted(RESIDENTIAL_BUILDING_VALUES),
        },
        "features": features,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(f"Найдено жилых зданий: {len(features)}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
