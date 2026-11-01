"""Calculate straight-line accessibility indicators for every grid cell.

Distances are measured from cell centroids to the nearest OSM facility point.
This is a baseline proxy, not a walking-network accessibility measure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import geopandas as gpd
import pandas as pd

from src.accessibility import nearest_distance_by_category
from src.scoring import CRITERIA

GRID_PATH = ROOT / "data" / "processed" / "grid_cells.geojson"
INFRASTRUCTURE_PATH = ROOT / "data" / "raw" / "infrastructure_osm.geojson"
RESIDENTIALITY_PATH = ROOT / "data" / "processed" / "cell_residentiality.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "cell_accessibility.csv"
METRIC_CRS = "EPSG:32640"


def calculate_cell_accessibility(
    grid: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    residentiality: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return one row per cell with nearest distances and residential metadata."""
    if "cell_id" not in grid.columns:
        raise ValueError("В сетке отсутствует столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id в сетке должны быть уникальными.")
    if grid.crs is None or facilities.crs is None:
        raise ValueError("У сетки и инфраструктуры должен быть задан CRS.")
    if "category" not in facilities.columns:
        raise ValueError("В инфраструктуре отсутствует столбец category.")

    # Cell centroids are temporary origins; residential building entrances
    # would be more accurate when such data becomes available.
    metric_grid = grid[["cell_id", "geometry"]].to_crs(METRIC_CRS)
    origins = metric_grid[["cell_id"]].copy()
    origins["geometry"] = metric_grid.geometry.centroid
    origins = gpd.GeoDataFrame(origins, geometry="geometry", crs=METRIC_CRS)

    metric_facilities = facilities[["category", "geometry"]].copy()
    metric_facilities = metric_facilities[
        metric_facilities["category"].isin(CRITERIA.keys())
    ]
    metric_facilities = metric_facilities.to_crs(METRIC_CRS)

    distances = nearest_distance_by_category(origins, metric_facilities)
    result = pd.DataFrame({"cell_id": grid["cell_id"].astype(str)})
    if not distances.empty:
        wide = distances.pivot(
            index="cell_id", columns="category", values="nearest_distance_m"
        )
        wide.columns = [f"nearest_distance_{category}_m" for category in wide.columns]
        result = result.merge(wide.reset_index(), on="cell_id", how="left")

    # Keep a stable schema even if a category has no mapped OSM objects.
    for category in CRITERIA:
        column = f"nearest_distance_{category}_m"
        if column not in result.columns:
            result[column] = float("nan")

    if residentiality is not None:
        required = {"cell_id", "residential_building_count", "has_residential_building"}
        missing = required - set(residentiality.columns)
        if missing:
            raise ValueError(
                "В таблице жилой застройки отсутствуют столбцы: "
                + ", ".join(sorted(missing))
            )
        if residentiality["cell_id"].astype(str).duplicated().any():
            raise ValueError("cell_id в таблице жилой застройки должны быть уникальными.")
        residential = residentiality[list(required)].copy()
        residential["cell_id"] = residential["cell_id"].astype(str)
        result = result.merge(residential, on="cell_id", how="left")
    else:
        result["residential_building_count"] = pd.NA
        result["has_residential_building"] = pd.NA

    result["residential_building_count"] = pd.to_numeric(
        result["residential_building_count"], errors="coerce"
    ).astype("Int64")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=GRID_PATH)
    parser.add_argument("--infrastructure", type=Path, default=INFRASTRUCTURE_PATH)
    parser.add_argument("--residentiality", type=Path, default=RESIDENTIALITY_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    for path in (args.grid, args.infrastructure, args.residentiality):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")

    grid = gpd.read_file(args.grid)
    facilities = gpd.read_file(args.infrastructure)
    residentiality = pd.read_csv(args.residentiality)

    result = calculate_cell_accessibility(grid, facilities, residentiality)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    print(f"Обработано ячеек: {len(result)}")
    print(f"Инфраструктурных объектов: {len(facilities)}")
    for category, label in CRITERIA.items():
        column = f"nearest_distance_{category}_m"
        available = int(result[column].notna().sum())
        print(f"{label}: расстояние рассчитано для {available} ячеек")
    print(
        "Ячеек с найденным жилым зданием: "
        f"{int(result['has_residential_building'].fillna(False).astype(bool).sum())}"
    )
    print(f"Результат: {args.output}")
    print("Расстояния прямолинейные; пороговые баллы пока не рассчитываются.")


if __name__ == "__main__":
    main()
