"""Calculate transport accessibility for every cell in the city grid."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from src.transport_accessibility import calculate_transport_accessibility

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
STOPS_PATH = ROOT / "data/processed/transport_stops_deduplicated.geojson"
OUTPUT_PATH = ROOT / "data/processed/transport_accessibility.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--stops", type=Path, default=STOPS_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--count-radius-m", type=float, default=500.0)
    parser.add_argument("--distance-threshold-m", type=float, default=2000.0)
    args = parser.parse_args()

    for path in (args.grid, args.stops):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")

    grid = gpd.read_file(args.grid)
    stops = gpd.read_file(args.stops)
    result = calculate_transport_accessibility(
        grid, stops,
        count_radius_m=args.count_radius_m,
        distance_threshold_m=args.distance_threshold_m,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"Ячеек обработано: {len(result)}")
    print(f"Остановок-кандидатов: {len(stops)}")
    print(f"Ячеек с остановкой в радиусе {args.count_radius_m:.0f} м: "
          f"{int((result['transport_stop_count_500m'] > 0).sum())}")
    print(f"Среднее число остановок в радиусе: "
          f"{result['transport_stop_count_500m'].mean():.2f}")
    print(f"Среднее расстояние до ближайшей остановки: "
          f"{result['nearest_distance_transport_m'].mean():.1f} м")
    print(f"Средняя оценка транспорта: {result['score_transport'].mean():.2f}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
