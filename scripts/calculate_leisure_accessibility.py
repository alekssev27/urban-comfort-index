"""Calculate leisure accessibility for every cell in the city grid."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import geopandas as gpd

from src.leisure_accessibility import calculate_leisure_accessibility

GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
INFRASTRUCTURE_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
OUTPUT_PATH = ROOT / "data/processed/leisure_accessibility.csv"

FOOD = {"cafe", "restaurant", "fast_food", "bar"}
CINEMA_THEATRE = {"cinema", "theatre"}
CULTURE = {"arts_centre", "community_centre", "library"}
FITNESS = {"fitness_centre"}
SPORT = {"sports_centre", "stadium"}
POOL = {"swimming_pool"}


def _tags_from_value(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def classify_leisure(tags):
    """Map OSM tags to the agreed diversity categories."""
    amenity = tags.get("amenity")
    leisure = tags.get("leisure")
    tourism = tags.get("tourism")
    shop = tags.get("shop")

    if amenity in FOOD:
        return "food_service", f"amenity:{amenity}"
    if amenity in CINEMA_THEATRE:
        return "cinema_theatre", f"amenity:{amenity}"
    if tourism == "museum":
        return "museum", "tourism:museum"
    if amenity in CULTURE:
        return "culture", f"amenity:{amenity}"
    if leisure in FITNESS:
        return "fitness", f"leisure:{leisure}"
    if leisure in SPORT:
        return "sport", f"leisure:{leisure}"
    if leisure == "swimming_pool" or amenity == "swimming_pool":
        return "pool", f"leisure:{leisure or amenity}"
    if shop == "mall":
        return "shopping_entertainment", "shop:mall"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--infrastructure", type=Path, default=INFRASTRUCTURE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    for path in (args.grid, args.infrastructure):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")

    grid = gpd.read_file(args.grid)
    infrastructure = gpd.read_file(args.infrastructure)
    if "tags" not in infrastructure.columns:
        raise SystemExit("В инфраструктуре отсутствует столбец tags.")

    records = []
    for index, row in infrastructure.iterrows():
        classified = classify_leisure(_tags_from_value(row["tags"]))
        if classified is None:
            continue
        category, leisure_type = classified
        osm_type = row.get("osm_type")
        osm_id = row.get("osm_id")
        facility_id = (
            f"{osm_type}/{osm_id}"
            if osm_type is not None and osm_id is not None else f"row/{index}"
        )
        records.append({
            "facility_id": facility_id,
            "leisure_category": category,
            "leisure_type": leisure_type,
            "name": row.get("name"),
            "geometry": row.geometry,
        })

    facilities = gpd.GeoDataFrame(records, geometry="geometry", crs=infrastructure.crs)
    if facilities.empty:
        raise SystemExit(
            "Не найдено объектов досуга. Проверьте OSM-данные и правила классификации."
        )
    facilities = facilities.drop_duplicates("facility_id", keep="first").reset_index(drop=True)

    result = calculate_leisure_accessibility(grid, facilities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    valid = result["score_leisure"].dropna()
    print(f"Ячеек обработано: {len(result)}")
    print(f"Объектов досуга: {len(facilities)}")
    print("Объекты по категориям:")
    print(facilities["leisure_category"].value_counts().to_string())
    print(f"Ячеек с рассчитанной оценкой: {len(valid)}")
    if not valid.empty:
        print(f"Среднее расстояние до объекта досуга: "
              f"{result['nearest_distance_leisure_m'].mean():.1f} м")
        print(f"Средняя оценка досуга: {valid.mean():.2f}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
