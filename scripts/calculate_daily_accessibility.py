"""Calculate daily-needs accessibility for every grid cell."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from src.daily_accessibility import calculate_daily_accessibility

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
INFRASTRUCTURE_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
OUTPUT_PATH = ROOT / "data/processed/daily_accessibility.csv"

BASIC_SHOPS = {
    "supermarket", "convenience", "greengrocer", "bakery",
    "butcher", "chemist", "general", "food",
}
BASIC_AMENITIES = {"pharmacy", "marketplace"}
ADDITIONAL_AMENITIES = {"bank", "atm", "post_office", "parcel_locker"}
ADDITIONAL_SHOPS = {"parcel_pickup_point", "parcel_locker"}


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


def classify_daily(tags):
    """Return (group, type) for supported basic/additional daily facilities."""
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    healthcare = tags.get("healthcare")

    if shop in BASIC_SHOPS:
        return "basic", f"shop:{shop}"
    if amenity in BASIC_AMENITIES or healthcare == "pharmacy":
        value = amenity if amenity in BASIC_AMENITIES else healthcare
        return "basic", f"facility:{value}"
    if amenity in ADDITIONAL_AMENITIES:
        return "additional", f"facility:{amenity}"
    if shop in ADDITIONAL_SHOPS:
        return "additional", f"shop:{shop}"
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
        classified = classify_daily(_tags_from_value(row["tags"]))
        if classified is None:
            continue
        group, daily_type = classified
        osm_type = row.get("osm_type")
        osm_id = row.get("osm_id")
        if osm_type is not None and osm_id is not None:
            facility_id = f"{osm_type}/{osm_id}"
        else:
            facility_id = f"row/{index}"
        records.append({
            "facility_id": facility_id,
            "daily_group": group,
            "daily_type": daily_type,
            "name": row.get("name"),
            "geometry": row.geometry,
        })

    facilities = gpd.GeoDataFrame(records, geometry="geometry", crs=infrastructure.crs)
    if facilities.empty:
        raise SystemExit(
            "Не найдено объектов повседневной инфраструктуры. "
            "Проверьте OSM-данные и правила классификации."
        )
    facilities = facilities.drop_duplicates("facility_id", keep="first").reset_index(drop=True)

    result = calculate_daily_accessibility(grid, facilities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    valid = result["score_daily"].dropna()
    print(f"Ячеек обработано: {len(result)}")
    print(f"Базовых объектов: {int(facilities['daily_group'].eq('basic').sum())}")
    print(f"Дополнительных объектов: {int(facilities['daily_group'].eq('additional').sum())}")
    print(f"Ячеек с рассчитанной оценкой: {len(valid)}")
    if not valid.empty:
        print(f"Среднее расстояние до базового объекта: "
              f"{result['nearest_distance_daily_m'].mean():.1f} м")
        print(f"Средняя оценка повседневной инфраструктуры: {valid.mean():.2f}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
