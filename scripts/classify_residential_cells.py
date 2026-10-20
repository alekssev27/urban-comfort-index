"""Download residential building centroids from OSM and mark grid cells.

This is a first-pass proxy for residential use, not a complete building
register. OSM building tags can be missing or inconsistent; inspect coverage.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape, mapping

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "data" / "raw" / "city_boundary.geojson"
GRID_PATH = ROOT / "data" / "processed" / "grid_cells.geojson"
BUILDINGS_PATH = ROOT / "data" / "raw" / "residential_buildings_osm.geojson"
OUTPUT_PATH = ROOT / "data" / "processed" / "cell_residentiality.csv"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "urban-comfort-index-student-project/0.1 (OSM research)"
RESIDENTIAL_VALUES = {"residential", "apartments", "house", "detached", "semidetached_house", "terrace", "dormitory", "bungalow", "houseboat"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=BOUNDARY_PATH)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--buildings-output", type=Path, default=BUILDINGS_PATH)
    parser.add_argument("--cells-output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    for path in (args.boundary, args.grid):
        if not path.exists():
            raise SystemExit(f"Не найден файл {path}. Сначала скачайте границу и постройте сетку.")
    collection = json.loads(args.boundary.read_text(encoding="utf-8"))
    if len(collection.get("features", [])) != 1:
        raise SystemExit("Ожидается один проверенный полигон границы.")
    boundary = shape(collection["features"][0]["geometry"])
    if not boundary.is_valid or boundary.is_empty:
        raise SystemExit("Граница невалидна.")
    query_boundary = boundary.simplify(0.001, preserve_topology=True)
    if query_boundary.geom_type == "MultiPolygon":
        query_boundary = max(query_boundary.geoms, key=lambda geom: geom.area)
    coords = list(query_boundary.exterior.coords)
    if len(coords) > 250:
        step = max(1, len(coords) // 249)
        coords = coords[::step]
        if coords[-1] != coords[0]: coords.append(coords[0])
    poly = " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in coords)
    query = f'''[out:json][timeout:{args.timeout}];
(
  nwr(poly:"{poly}")[building~"^(residential|apartments|house|detached|semidetached_house|terrace|dormitory|bungalow|houseboat)$"];
);
out center tags;'''
    response = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=args.timeout + 30)
    response.raise_for_status()
    elements = response.json().get("elements", [])
    features, seen = [], set()
    for element in elements:
        tags = element.get("tags", {})
        building_type = tags.get("building")
        if building_type not in RESIDENTIAL_VALUES:
            continue
        center = element.get("center")
        lat = element.get("lat", center.get("lat") if center else None)
        lon = element.get("lon", center.get("lon") if center else None)
        if lat is None or lon is None: continue
        point = Point(float(lon), float(lat))
        if not boundary.covers(point): continue
        key = (element.get("type"), element.get("id"))
        if key in seen: continue
        seen.add(key)
        props = {"osm_type": element.get("type"), "osm_id": element.get("id"), "building": building_type,
                 "name": tags.get("name"), "source": "OpenStreetMap via Overpass API", "license": "OpenStreetMap data, ODbL 1.0"}
        features.append({"type": "Feature", "geometry": mapping(point), "properties": props})
    args.buildings_output.parent.mkdir(parents=True, exist_ok=True)
    building_collection = {"type": "FeatureCollection", "name": "residential_building_centroids",
                           "metadata": {"retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                        "source_url": OVERPASS_URL, "license": "OpenStreetMap data, ODbL 1.0",
                                        "warning": "OSM residential building tags are incomplete; this is a proxy, not authoritative land-use data."},
                           "features": features}
    args.buildings_output.write_text(json.dumps(building_collection, ensure_ascii=False, indent=2), encoding="utf-8")

    grid = gpd.read_file(args.grid)
    if grid.crs is None: raise SystemExit("У сетки не указана CRS.")
    grid = grid.to_crs("EPSG:32640")
    if features:
        buildings = gpd.GeoDataFrame([feature["properties"] for feature in features],
            geometry=[shape(feature["geometry"]) for feature in features], crs="EPSG:4326").to_crs("EPSG:32640")
        joined = gpd.sjoin(buildings[["geometry"]], grid[["cell_id", "geometry"]], how="inner", predicate="within")
        counts = joined.groupby("cell_id").size().rename("residential_building_count")
    else:
        counts = pd.Series(dtype="int64", name="residential_building_count")
    result = grid[["cell_id"]].copy()
    result["residential_building_count"] = result["cell_id"].map(counts).fillna(0).astype(int)
    result["has_residential_building"] = result["residential_building_count"] > 0
    result["classification_source"] = "OSM building=* residential tag; incomplete proxy"
    args.cells_output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.cells_output, index=False)
    residential_cells = int(result["has_residential_building"].sum())
    print(f"Загружено центроидов жилых зданий: {len(features)}")
    print(f"Ячеек с хотя бы одним найденным жилым зданием: {residential_cells} / {len(result)}")
    print(f"GeoJSON зданий: {args.buildings_output}")
    print(f"Классификация ячеек: {args.cells_output}")
    print("Важно: нулевой счётчик не доказывает отсутствие жилья — в OSM может не быть разметки здания.")

if __name__ == "__main__":
    main()
