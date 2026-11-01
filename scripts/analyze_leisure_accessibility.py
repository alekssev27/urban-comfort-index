"""Summarise calculated leisure accessibility scores."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data/processed/leisure_accessibility.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    if args.top < 1:
        raise SystemExit("--top должен быть не меньше 1.")
    if not args.input.exists():
        raise SystemExit(f"Не найден файл: {args.input}")

    data = pd.read_csv(args.input, encoding="utf-8-sig")
    required = {
        "cell_id", "nearest_distance_leisure_m", "nearest_leisure_name",
        "nearest_leisure_type", "leisure_count_750m",
        "leisure_category_count_750m", "leisure_categories_750m", "score_leisure",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise SystemExit("В CSV отсутствуют столбцы: " + ", ".join(missing))

    for column in ("score_leisure", "nearest_distance_leisure_m"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    scores = data["score_leisure"].dropna()
    if scores.empty:
        raise SystemExit("В файле нет рассчитанных оценок leisure.")

    bins = [-0.001, 20, 40, 60, 80, 100]
    labels = ["0–20", "20–40", "40–60", "60–80", "80–100"]
    counts = pd.cut(scores, bins=bins, labels=labels, include_lowest=True).value_counts(sort=False)

    print("\n=== Общая статистика ===")
    print(f"Всего ячеек: {len(data)}")
    print(f"Ячеек с рассчитанной оценкой: {len(scores)}")
    print(f"Без найденного объекта досуга: {int(data['score_leisure'].isna().sum())}")
    print(f"Среднее: {scores.mean():.2f}")
    print(f"Медиана: {scores.median():.2f}")
    print(f"Минимум: {scores.min():.2f}")
    print(f"Максимум: {scores.max():.2f}")
    print(f"Среднее расстояние до объекта: "
          f"{data['nearest_distance_leisure_m'].mean():.1f} м")

    print("\n=== Распределение оценок ===")
    print(f"{'Диапазон':<12}{'Ячеек':>10}{'Доля':>12}")
    for label in labels:
        print(f"{label:<12}{int(counts[label]):>10}"
              f"{counts[label] / len(scores) * 100:>11.1f}%")

    columns = [
        "cell_id", "score_leisure", "nearest_distance_leisure_m",
        "leisure_count_750m", "leisure_category_count_750m",
        "leisure_categories_750m", "nearest_leisure_name", "nearest_leisure_type",
    ]
    print(f"\n=== {args.top} ячеек с лучшей доступностью ===")
    print(data.nlargest(args.top, "score_leisure")[columns].to_string(index=False))
    print(f"\n=== {args.top} ячеек с худшей доступностью ===")
    print(data.nsmallest(args.top, "score_leisure")[columns].to_string(index=False))


if __name__ == "__main__":
    main()
