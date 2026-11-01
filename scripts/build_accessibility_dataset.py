"""Собрать оценки шести критериев и профильные индексы для Mesto."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import geopandas as gpd
import pandas as pd

from src.dataset_builder import CRITERION_FILES, build_accessibility_dataset

GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
PROCESSED_DIR = ROOT / "data/processed"
OUTPUT_PATH = PROCESSED_DIR / "residential_comfort_scores.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--input-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    if not args.grid.exists():
        raise SystemExit(f"Не найден файл сетки: {args.grid}")

    grid = gpd.read_file(args.grid)
    criterion_frames = {}
    for criterion, filename in CRITERION_FILES.items():
        path = args.input_dir / filename
        if not path.exists():
            raise SystemExit(
                f"Не найден результат критерия {criterion}: {path}. "
                "Сначала рассчитайте все шесть критериев."
            )
        criterion_frames[criterion] = pd.read_csv(path, encoding="utf-8-sig")

    try:
        result = build_accessibility_dataset(grid, criterion_frames)
    except ValueError as error:
        raise SystemExit(f"Не удалось объединить результаты: {error}") from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"Ячеек в сетке: {len(grid)}")
    print(f"Ячеек в итоговом датасете: {len(result)}")
    print("\nСредние оценки критериев:")
    for criterion in CRITERION_FILES:
        column = f"score_{criterion}"
        print(f"  {criterion}: {result[column].mean():.2f}")
    print("\nСредние профильные индексы:")
    for profile in ("student", "couple", "family"):
        column = f"comfort_index_{profile}"
        print(f"  {profile}: {result[column].mean():.2f}")
    print(f"\nСохранено: {args.output}")


if __name__ == "__main__":
    main()
