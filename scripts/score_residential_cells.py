"""Score residential grid cells using category-specific P90 distance thresholds."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.scoring import CRITERIA, PROFILE_WEIGHTS, distance_score, calculate_index

INPUT_PATH = ROOT / "data" / "processed" / "cell_accessibility.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "residential_comfort_scores.csv"
THRESHOLDS_PATH = ROOT / "data" / "processed" / "accessibility_thresholds_p90.csv"


def score_residential_cells(data: pd.DataFrame):
    """Fit P90 thresholds on residential cells and score only those cells."""
    required = {"cell_id", "has_residential_building"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError("Отсутствуют обязательные столбцы: " + ", ".join(sorted(missing)))
    residential = data[data["has_residential_building"].fillna(False).astype(bool)].copy()
    if residential.empty:
        raise ValueError("Не найдено ни одной ячейки с жилыми зданиями.")

    threshold_rows = []
    for category, label in CRITERIA.items():
        column = f"nearest_distance_{category}_m"
        if column not in residential.columns:
            raise ValueError(f"Отсутствует столбец {column}.")
        values = pd.to_numeric(residential[column], errors="coerce").dropna()
        threshold = float(values.quantile(0.90)) if not values.empty else float("nan")
        threshold_rows.append({
            "category": category,
            "category_label": label,
            "percentile": 0.90,
            "threshold_m": threshold,
            "valid_residential_cells": int(values.count()),
        })
        score_column = f"score_{category}"
        if pd.isna(threshold) or threshold <= 0:
            residential[score_column] = float("nan")
        else:
            residential[score_column] = residential[column].apply(
                lambda value: distance_score(value, threshold)
            )

    for profile, weights in PROFILE_WEIGHTS.items():
        index_values = []
        for _, row in residential.iterrows():
            criterion_scores = {key: row[f"score_{key}"] for key in CRITERIA}
            index_values.append(calculate_index(criterion_scores, weights))
        residential[f"comfort_index_{profile}"] = index_values

    return residential, pd.DataFrame(threshold_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--thresholds-output", type=Path, default=THRESHOLDS_PATH)
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Не найден файл: {args.input}")

    scores, thresholds = score_residential_cells(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.thresholds_output.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.output, index=False)
    thresholds.to_csv(args.thresholds_output, index=False)

    print(f"Ячеек в рейтинге: {len(scores)}")
    print("Пороги P90 рассчитаны только по ячейкам с найденным жильём.")
    for _, row in thresholds.iterrows():
        threshold = "нет данных" if pd.isna(row.threshold_m) else f"{row.threshold_m:.1f} м"
        print(f"{row.category_label}: {threshold} (наблюдений: {row.valid_residential_cells})")
    for profile in PROFILE_WEIGHTS:
        column = f"comfort_index_{profile}"
        print(f"Индекс {profile}: {scores[column].notna().sum()} ячеек")
    print(f"Рейтинг: {args.output}")
    print(f"Пороги: {args.thresholds_output}")
    print("Оценка предварительная: прямолинейные расстояния и неполные данные OSM.")


if __name__ == "__main__":
    main()
