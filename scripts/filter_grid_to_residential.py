"""Оставить в городской сетке только ячейки с жилыми зданиями."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from src.residential_filter import filter_grid_by_residential_buildings

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data/processed/grid_cells.geojson"
BUILDINGS_PATH = ROOT / "data/raw/residential_buildings_osm.geojson"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--buildings", type=Path, default=BUILDINGS_PATH)
    parser.add_argument("--output", type=Path, default=GRID_PATH)
    args = parser.parse_args()

    for path in (args.grid, args.buildings):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")

    grid = gpd.read_file(args.grid)
    buildings = gpd.read_file(args.buildings)
    filtered = filter_grid_by_residential_buildings(grid, buildings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_crs("EPSG:4326").to_file(args.output, driver="GeoJSON")

    removed = len(grid) - len(filtered)
    percent = removed / len(grid) * 100
    print(f"Ячеек до фильтрации: {len(grid)}")
    print(f"Ячеек с жилыми зданиями: {len(filtered)}")
    print(f"Удалено нежилых ячеек: {removed} ({percent:.1f}%)")
    print(f"Сохранено: {args.output}")
    print("В ячейке должна быть положительная площадь пересечения с жилым зданием.")


if __name__ == "__main__":
    main()
