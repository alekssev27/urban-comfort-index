"""Build the analysis grid from a reviewed boundary GeoJSON."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Allow both `python scripts/build_grid.py` and `python -m scripts.build_grid`.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import geopandas as gpd
from src.grid import DEFAULT_CELL_SIZE_M, DEFAULT_CRS, generate_square_grid

DEFAULT_BOUNDARY = ROOT / "data" / "raw" / "city_boundary.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "grid_cells.geojson"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cell-size", type=int, default=DEFAULT_CELL_SIZE_M)
    parser.add_argument("--include-partial-cells", action="store_true", help="Обрезать крайние ячейки по границе")
    args = parser.parse_args()

    if not args.boundary.exists():
        raise SystemExit(f"Не найден файл границы: {args.boundary}. Сначала запустите scripts/fetch_osm_boundary.py и проверьте контур.")
    boundary = gpd.read_file(args.boundary)
    if boundary.empty or boundary.crs is None:
        raise SystemExit("Файл границы пуст или в нём не задана CRS.")
    grid = generate_square_grid(boundary, args.cell_size, include_partial_cells=args.include_partial_cells)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    grid.to_crs("EPSG:4326").to_file(args.output, driver="GeoJSON")
    print(f"Сохранено ячеек: {len(grid)}")
    print(f"CRS расчёта: {DEFAULT_CRS}; размер стороны: {args.cell_size} м")
    print(f"Файл: {args.output}")
    print("Сетка ещё не отфильтрована по жилой застройке; не трактуйте все ячейки как жилые.")


if __name__ == "__main__":
    main()
