"""Calculate main green-area accessibility for every grid cell."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import geopandas as gpd

from src.green_accessibility import (
    calculate_green_accessibility,
    dissolve_green_areas,
)

GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
GREEN_PATH = ROOT / "data/raw/green_areas.geojson"
OUTPUT_PATH = ROOT / "data/processed/green_accessibility.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--green-areas", type=Path, default=GREEN_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    for path in (args.grid, args.green_areas):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")

    grid = gpd.read_file(args.grid)
    green = gpd.read_file(args.green_areas)
    if green.empty:
        raise SystemExit(
            "Файл основных зелёных зон пуст. Проверьте data/raw/green_areas.geojson."
        )

    result = calculate_green_accessibility(grid, green)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    valid = result["score_green"].dropna()
    print(f"Ячеек обработано: {len(result)}")
    print(f"Исходных зелёных полигонов: {len(green)}")
    dissolved = dissolve_green_areas(green)
    print(f"Объединённых зелёных территорий: {len(dissolved)}")
    print(f"Ячеек с рассчитанной оценкой: {len(valid)}")
    if not valid.empty:
        print(f"Средняя оценка зелёных зон: {valid.mean():.2f}")
        print(f"Среднее расстояние до ближайшей зоны: "
              f"{result['nearest_distance_green_m'].mean():.1f} м")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
