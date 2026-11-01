"""Transport accessibility metrics for the urban grid.

Distances are straight-line distances from grid-cell centroids to deduplicated
OSM stop-group points. This is a baseline, not pedestrian-network travel time.
"""
from __future__ import annotations

import ast
import json

import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_COUNT_RADIUS_M = 500.0
DEFAULT_DISTANCE_THRESHOLD_M = 2000.0


def _normalise_modes(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    elif isinstance(value, str):
        try:
            values = json.loads(value)
        except json.JSONDecodeError:
            try:
                values = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                values = [value]
    else:
        return set()
    return {str(item).strip() for item in values if str(item).strip()}


def transport_count_bonus(stop_count: int) -> float:
    if stop_count < 2:
        return 0.0
    if stop_count == 2:
        return 1.0
    if stop_count == 3:
        return 3.0
    if stop_count == 4:
        return 5.0
    return 10.0


def transport_diversity_bonus(mode_count: int) -> float:
    if mode_count <= 1:
        return 0.0
    if mode_count == 2:
        return 5.0
    if mode_count == 3:
        return 10.0
    return 15.0


def calculate_transport_accessibility(
    grid: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    count_radius_m: float = DEFAULT_COUNT_RADIUS_M,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
) -> pd.DataFrame:
    """Calculate nearest-stop distance, 500 m stop count, mode diversity and score.

    One feature in stops represents one deduplicated stop group. A stop with
    multiple modes is counted once but contributes every listed mode to local
    transport diversity. All grid cells are processed; residential filtering
    is deliberately a separate workflow step.
    """
    if count_radius_m <= 0:
        raise ValueError("count_radius_m должен быть больше нуля.")
    if distance_threshold_m <= 0:
        raise ValueError("distance_threshold_m должен быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    if "stop_group_id" not in stops.columns:
        raise ValueError("stops должен содержать столбец stop_group_id.")
    if stops["stop_group_id"].duplicated().any():
        raise ValueError("stop_group_id должен быть уникальным.")
    if "transport_modes" not in stops.columns:
        raise ValueError("stops должен содержать столбец transport_modes.")
    if grid.crs is None or stops.crs is None:
        raise ValueError("У сетки и остановок должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")
    if not stops.empty and not stops.geometry.geom_type.isin(["Point", "MultiPoint"]).all():
        raise ValueError("Остановки должны быть представлены точками.")

    columns = [
        "cell_id", "nearest_distance_transport_m", "nearest_stop_group_id",
        "nearest_stop_name", "transport_stop_count_500m",
        "transport_mode_count_500m", "transport_modes_500m", "score_transport",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid
    facilities = stops[["stop_group_id", "name", "transport_modes", "geometry"]].copy().to_crs(metric_crs)
    facilities["_modes"] = facilities["transport_modes"].map(_normalise_modes)

    result = origins[["cell_id"]].copy().set_index("cell_id")
    result["nearest_distance_transport_m"] = float("nan")
    result["nearest_stop_group_id"] = None
    result["nearest_stop_name"] = None
    result["transport_stop_count_500m"] = 0
    result["transport_mode_count_500m"] = 0
    result["transport_modes_500m"] = ""

    if facilities.empty:
        result["score_transport"] = float("nan")
        return result.reset_index()[columns]

    nearest = gpd.sjoin_nearest(
        origins,
        facilities[["stop_group_id", "name", "geometry"]],
        how="left",
        distance_col="nearest_distance_transport_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_transport_m", "stop_group_id"], kind="stable"
    ).drop_duplicates("cell_id").set_index("cell_id")
    result["nearest_distance_transport_m"] = nearest["nearest_distance_transport_m"]
    result["nearest_stop_group_id"] = nearest["stop_group_id"]
    result["nearest_stop_name"] = nearest["name"]

    buffers = origins[["cell_id", "geometry"]].copy()
    buffers["geometry"] = buffers.geometry.buffer(count_radius_m)
    nearby = gpd.sjoin(
        buffers,
        facilities[["stop_group_id", "_modes", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    if not nearby.empty:
        grouped = nearby.groupby("cell_id", sort=False)
        counts = grouped["stop_group_id"].nunique()
        result.loc[counts.index, "transport_stop_count_500m"] = counts.astype(int)

        # Aggregate modes explicitly instead of relying on pandas object-column
        # aggregation; this also handles empty sets and GeoPandas join output.
        modes_by_cell = {}
        for cell_id, modes in nearby[["cell_id", "_modes"]].itertuples(index=False, name=None):
            modes_by_cell.setdefault(cell_id, set()).update(modes or set())
        for cell_id, modes in modes_by_cell.items():
            ordered_modes = sorted(modes)
            result.at[cell_id, "transport_mode_count_500m"] = len(ordered_modes)
            result.at[cell_id, "transport_modes_500m"] = ",".join(ordered_modes)

    distance_score = (
        100.0 * (1.0 - result["nearest_distance_transport_m"] / distance_threshold_m)
    ).clip(lower=0.0, upper=100.0)
    count_bonus = result["transport_stop_count_500m"].map(transport_count_bonus)
    diversity_bonus = result["transport_mode_count_500m"].map(transport_diversity_bonus)
    result["score_transport"] = (distance_score + count_bonus + diversity_bonus).clip(0.0, 100.0)
    return result.reset_index()[columns]
