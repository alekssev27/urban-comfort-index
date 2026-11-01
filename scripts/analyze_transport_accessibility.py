"""Summarise the distribution of calculated transport accessibility scores."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data/processed/transport_accessibility.csv"


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
        "cell_id",
        "nearest_distance_transport_m",
        "transport_stop_count_500m",
        "transport_mode_count_500m",
        "transport_modes_500m",
        "score_transport",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise SystemExit("В CSV отсутствуют столбцы: " + ", ".join(missing))

    for column in (
        "nearest_distance_transport_m",
        "transport_stop_count_500m",
        "transport_mode_count_500m",
        "score_transport",
    ):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    scores = data["score_transport"].dropna()
    if scores.empty:
        raise SystemExit("В файле нет рассчитанных оценок transport.")

    bins = [-0.001, 20, 40, 60, 80, 100]
    labels = ["0–20", "20–40", "40–60", "60–80", "80–100"]
    distribution = pd.cut(scores, bins=bins, labels=labels, include_lowest=True)
    counts = distribution.value_counts(sort=False)
    percentages = counts / len(scores) * 100

    no_nearby = data["transport_stop_count_500m"].fillna(0).eq(0)
    print("\n=== Общая статистика ===")
    print(f"Всего ячеек: {len(data)}")
    print(f"Ячеек с рассчитанной оценкой: {len(scores)}")
    print(f"Среднее: {scores.mean():.2f}")
    print(f"Медиана: {scores.median():.2f}")
    print(f"Минимум: {scores.min():.2f}")
    print(f"Максимум: {scores.max():.2f}")
    print(f"Стандартное отклонение: {scores.std():.2f}")
    print(
        "Без остановок в радиусе 500 м: "
        f"{int(no_nearby.sum())} ({no_nearby.mean() * 100:.1f}%)"
    )

    print("\n=== Распределение оценок ===")
    print(f"{'Диапазон':<12}{'Ячеек':>10}{'Доля':>12}")
    for label in labels:
        print(f"{label:<12}{int(counts[label]):>10}{percentages[label]:>11.1f}%")

    columns = [
        "cell_id",
        "score_transport",
        "nearest_distance_transport_m",
        "transport_stop_count_500m",
        "transport_mode_count_500m",
        "transport_modes_500m",
    ]
    print(f"\n=== {args.top} ячеек с лучшей доступностью ===")
    print(
        data.nlargest(args.top, "score_transport")[columns]
        .to_string(index=False, float_format=lambda value: f"{value:.1f}")
    )
    print(f"\n=== {args.top} ячеек с худшей доступностью ===")
    print(
        data.nsmallest(args.top, "score_transport")[columns]
        .to_string(index=False, float_format=lambda value: f"{value:.1f}")
    )


if __name__ == "__main__":
    main()
