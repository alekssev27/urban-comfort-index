"""Daily-needs accessibility from grid-cell centroids to OSM facilities.

Uses straight-line distance to the nearest basic facility and a weighted
500 m count of basic and additional facilities.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_COUNT_RADIUS_M = 500.0
DEFAULT_DISTANCE_THRESHOLD_M = 2000.0


def daily_count_bonus(weighted_count: float) -> float:
    if weighted_count < 3:
        return 0.0
    if weighted_count < 4:
        return 1.0
    if weighted_count < 5:
        return 3.0
    if weighted_count < 7:
        return 5.0
    return 10.0


def calculate_daily_accessibility(
    grid: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    count_radius_m: float = DEFAULT_COUNT_RADIUS_M,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
) -> pd.DataFrame:
    """Calculate daily accessibility for each grid cell.

    Required facility columns:
      - facility_id: unique physical OSM object identifier
      - daily_group: "basic" or "additional"
      - daily_type: descriptive OSM facility type
    Basic facilities determine nearest distance. Additional facilities
    contribute 0.4 each to the local weighted count, but only if at least
    one basic facility is within the count radius.
    """
    if count_radius_m <= 0 or distance_threshold_m <= 0:
        raise ValueError("Радиусы и порог расстояния должны быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    required = {"facility_id", "daily_group", "daily_type"}
    missing = required - set(facilities.columns)
    if missing:
        raise ValueError("В facilities отсутствуют столбцы: " + ", ".join(sorted(missing)))
    if facilities["facility_id"].duplicated().any():
        raise ValueError("facility_id должен быть уникальным.")
    if not facilities["daily_group"].isin(["basic", "additional"]).all():
        raise ValueError("daily_group должен быть basic или additional.")
    if grid.crs is None or facilities.crs is None:
        raise ValueError("У сетки и объектов daily должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")
    if not facilities.empty and facilities.geometry.isna().any():
        raise ValueError("У объектов daily отсутствует геометрия.")

    columns = [
        "cell_id", "nearest_distance_daily_m", "nearest_daily_name",
        "nearest_daily_type", "daily_basic_count_500m",
        "daily_additional_count_500m", "daily_weighted_count_500m",
        "score_daily",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid
    result = origins[["cell_id"]].copy()
    result["nearest_distance_daily_m"] = float("nan")
    result["nearest_daily_name"] = None
    result["nearest_daily_type"] = None
    result["daily_basic_count_500m"] = 0
    result["daily_additional_count_500m"] = 0
    result["daily_weighted_count_500m"] = 0.0

    data = facilities[
        ["facility_id", "daily_group", "daily_type", "geometry"]
        + (["name"] if "name" in facilities.columns else [])
    ].copy().to_crs(metric_crs)
    data = data.loc[data.geometry.notna() & ~data.geometry.is_empty].reset_index(drop=True)
    basic = data.loc[data["daily_group"].eq("basic")].copy()

    if basic.empty:
        result["score_daily"] = float("nan")
        return result[columns]

    nearest = gpd.sjoin_nearest(
        origins,
        basic,
        how="left",
        distance_col="nearest_distance_daily_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_daily_m", "facility_id"], kind="stable"
    ).drop_duplicates("cell_id").set_index("cell_id")
    result = result.set_index("cell_id")
    result["nearest_distance_daily_m"] = nearest["nearest_distance_daily_m"]
    result["nearest_daily_name"] = (
        nearest["name"] if "name" in nearest.columns else None
    )
    result["nearest_daily_type"] = nearest["daily_type"]

    buffers = origins[["cell_id", "geometry"]].copy()
    buffers["geometry"] = buffers.geometry.buffer(count_radius_m)
    nearby = gpd.sjoin(
        buffers,
        data[["facility_id", "daily_group", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    if not nearby.empty:
        counts = nearby.groupby(["cell_id", "daily_group"])["facility_id"].nunique()
        for (cell_id, group), count in counts.items():
            column = (
                "daily_basic_count_500m"
                if group == "basic" else "daily_additional_count_500m"
            )
            result.at[cell_id, column] = int(count)

    has_basic_nearby = result["daily_basic_count_500m"] > 0
    result["daily_weighted_count_500m"] = (
        result["daily_basic_count_500m"].astype(float)
        + result["daily_additional_count_500m"].astype(float).where(has_basic_nearby, 0.0) * 0.4
    )
    distance_score = (
        100.0 * (1.0 - result["nearest_distance_daily_m"] / distance_threshold_m)
    ).clip(lower=0.0, upper=100.0)
    bonus = result["daily_weighted_count_500m"].map(daily_count_bonus)
    result["score_daily"] = (distance_score + bonus).clip(0.0, 100.0)
    return result.reset_index()[columns]
