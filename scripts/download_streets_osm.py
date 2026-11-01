"""Download named OSM road segments covering the project's residential grid.

Run from the repository root:
    python scripts/download_streets_osm.py

Output:
    data/raw/streets_osm.geojson
"""
from pathlib import Path
import time

import geopandas as gpd
import requests
from shapely.geometry import LineString, MultiLineString, mapping

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data" / "processed" / "grid_cells.geojson"
OUTPUT_PATH = ROOT / "data" / "raw" / "streets_osm.geojson"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def main():
    if not GRID_PATH.exists():
        raise FileNotFoundError(f"Не найден файл сетки: {GRID_PATH}")

    grid = gpd.read_file(GRID_PATH)
    if grid.crs is None:
        raise ValueError("У grid_cells.geojson не указана система координат")
    bounds = grid.to_crs("EPSG:4326").total_bounds
    west, south, east, north = bounds

    query = f"""
    [out:json][timeout:180];
    (
      way["highway"]["name"]({south},{west},{north},{east});
    );
    out geom;
    """
    response = None
    errors = []

    for url in OVERPASS_URLS:
        for attempt in range(1, 4):
            try:
                print(f"Запрос к {url} (попытка {attempt}/3)...")
                candidate = requests.post(
                    url,
                    data={"data": query},
                    timeout=210,
                    headers={"User-Agent": "MestoUrbanComfort/1.0"},
                )
                candidate.raise_for_status()
                response = candidate
                print("Данные успешно получены.")
                break
            except requests.RequestException as error:
                errors.append(f"{url}: {error}")
                print(f"Сервер недоступен: {error}")
                if attempt < 3:
                    time.sleep(2 ** attempt)

        if response is not None:
            break

    if response is None:
        details = "\\n".join(errors)
        raise RuntimeError(
            "Не удалось получить данные ни с одного Overpass-сервера. "
            "Попробуйте запустить скрипт позже.\\n" + details
        )

    payload = response.json()

    features = []
    for element in payload.get("elements", []):
        coords = [
            (point["lon"], point["lat"])
            for point in element.get("geometry", [])
            if "lon" in point and "lat" in point
        ]
        if len(coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "name": element.get("tags", {}).get("name"),
                "highway": element.get("tags", {}).get("highway"),
                "osm_id": element.get("id"),
            },
            "geometry": mapping(LineString(coords)),
        })

    if not features:
        raise RuntimeError("Overpass не вернул именованные улицы для границ сетки")

    import json
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Сохранено дорожных сегментов: {len(features)}")
    print(f"Файл: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
