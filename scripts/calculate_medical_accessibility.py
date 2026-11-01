"""Calculate medical accessibility for every cell in the city grid."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from src.medical_accessibility import calculate_medical_accessibility

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
INFRASTRUCTURE_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
OUTPUT_PATH = ROOT / "data/processed/medical_accessibility.csv"

MEDICAL_AMENITIES = {"hospital", "clinic", "doctors", "dentist"}
MEDICAL_HEALTHCARE = {"hospital", "clinic", "doctor", "dentist", "centre"}


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
    if "category" not in infrastructure.columns:
        raise SystemExit("В инфраструктуре отсутствует столбец category.")

    medical = infrastructure.loc[
        infrastructure["category"].eq("medical")
    ].copy()
    if "tags" not in medical.columns:
        medical["tags"] = [{} for _ in range(len(medical))]
    medical["_osm_tags"] = medical["tags"].map(_tags_from_value)
    medical["medical_type"] = medical["_osm_tags"].map(
        lambda tags: tags.get("amenity") or tags.get("healthcare")
    )

    # Pharmacies stay in daily infrastructure and are not counted here.
    medical = medical.loc[
        medical["medical_type"].isin(MEDICAL_AMENITIES | MEDICAL_HEALTHCARE)
    ].copy()
    medical = medical.drop_duplicates(
        subset=["osm_type", "osm_id"], keep="first"
    ) if {"osm_type", "osm_id"}.issubset(medical.columns) else medical

    if medical.empty:
        raise SystemExit(
            "Не найдено медицинских объектов. Проверьте "
            "data/raw/infrastructure_osm.geojson и категорию medical."
        )

    result = calculate_medical_accessibility(grid, medical)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    valid = result["score_medical"].dropna()
    print(f"Ячеек обработано: {len(result)}")
    print(f"Медицинских объектов: {len(medical)}")
    print(f"Ячеек с найденным объектом: {len(valid)}")
    if not valid.empty:
        print(f"Среднее расстояние: "
              f"{result['nearest_distance_medical_m'].mean():.1f} м")
        print(f"Средняя оценка медицины: {valid.mean():.2f}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
