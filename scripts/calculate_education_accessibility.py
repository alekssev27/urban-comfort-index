"""Calculate education accessibility for every cell in the city grid."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from src.education_accessibility import calculate_education_accessibility

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
INFRASTRUCTURE_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
OUTPUT_PATH = ROOT / "data/processed/education_accessibility.csv"
EDUCATION_AMENITIES = {
    "school", "kindergarten", "college", "university", "music_school",
}


def _amenity_from_tags(value):
    if isinstance(value, dict):
        return value.get("amenity")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed.get("amenity")
        except json.JSONDecodeError:
            return None
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
    if "category" not in infrastructure.columns:
        raise SystemExit("В инфраструктуре отсутствует столбец category.")

    education = infrastructure.loc[
        infrastructure["category"].eq("education")
    ].copy()
    if "amenity" not in education.columns:
        if "tags" not in education.columns:
            raise SystemExit("В образовательных объектах отсутствуют amenity и tags.")
        education["amenity"] = education["tags"].map(_amenity_from_tags)

    education = education.loc[
        education["amenity"].isin(EDUCATION_AMENITIES)
    ].copy()
    if education.empty:
        raise SystemExit(
            "Не найдено образовательных объектов. Проверьте "
            "data/raw/infrastructure_osm.geojson и категорию education."
        )

    result = calculate_education_accessibility(grid, education)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    valid = result["score_education"].dropna()
    print(f"Ячеек обработано: {len(result)}")
    print(f"Образовательных объектов: {len(education)}")
    print(f"Ячеек с найденным объектом: {len(valid)}")
    if not valid.empty:
        print(f"Среднее расстояние: "
              f"{result['nearest_distance_education_m'].mean():.1f} м")
        print(f"Средняя оценка образования: {valid.mean():.2f}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
