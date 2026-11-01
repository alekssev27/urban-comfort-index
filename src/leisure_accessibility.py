"""Leisure accessibility from grid-cell centroids to OSM facilities.

Distances are straight-line. Counts use unique OSM objects within 750 m;
diversity counts distinct leisure categories in the same radius.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_COUNT_RADIUS_M = 750.0
DEFAULT_DISTANCE_THRESHOLD_M = 2000.0


def leisure_count_bonus(count: int) -> float:
    if count <= 2:
        return 0.0
    if count <= 5:
        return 1.0
    if count <= 9:
        return 3.0
    if count <= 14:
        return 5.0
    return 10.0


def leisure_diversity_bonus(category_count: int) -> float:
    if category_count <= 1:
        return 0.0
    if category_count == 2:
        return 5.0
    if category_count == 3:
        return 10.0
    if category_count <= 5:
        return 15.0
    return 20.0


def calculate_leisure_accessibility(
    grid: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    count_radius_m: float = DEFAULT_COUNT_RADIUS_M,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
) -> pd.DataFrame:
    """Calculate nearest leisure distance, local count, diversity and score.

    Required facility columns: facility_id and leisure_category. Facilities
    can be points or polygons. A physical OSM feature is counted once.
    """
    if count_radius_m <= 0 or distance_threshold_m <= 0:
        raise ValueError("Радиусы и порог расстояния должны быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    required = {"facility_id", "leisure_category"}
    missing = required - set(facilities.columns)
    if missing:
        raise ValueError("В facilities отсутствуют столбцы: " + ", ".join(sorted(missing)))
    if facilities["facility_id"].duplicated().any():
        raise ValueError("facility_id должен быть уникальным.")
    if facilities["leisure_category"].isna().any():
        raise ValueError("У каждого объекта должна быть leisure_category.")
    if grid.crs is None or facilities.crs is None:
        raise ValueError("У сетки и объектов leisure должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")
    if not facilities.empty and facilities.geometry.isna().any():
        raise ValueError("У объектов leisure отсутствует геометрия.")

    columns = [
        "cell_id", "nearest_distance_leisure_m", "nearest_leisure_name",
        "nearest_leisure_type", "leisure_count_750m",
        "leisure_category_count_750m", "leisure_categories_750m",
        "score_leisure",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid
    data_columns = ["facility_id", "leisure_category", "geometry"]
    if "name" in facilities.columns:
        data_columns.append("name")
    if "leisure_type" in facilities.columns:
        data_columns.append("leisure_type")
    data = facilities[data_columns].copy().to_crs(metric_crs)
    data = data.loc[data.geometry.notna() & ~data.geometry.is_empty].reset_index(drop=True)

    result = origins[["cell_id"]].copy().set_index("cell_id")
    result["nearest_distance_leisure_m"] = float("nan")
    result["nearest_leisure_name"] = None
    result["nearest_leisure_type"] = None
    result["leisure_count_750m"] = 0
    result["leisure_category_count_750m"] = 0
    result["leisure_categories_750m"] = ""

    if data.empty:
        result["score_leisure"] = float("nan")
        return result.reset_index()[columns]

    nearest = gpd.sjoin_nearest(
        origins,
        data,
        how="left",
        distance_col="nearest_distance_leisure_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_leisure_m", "facility_id"], kind="stable"
    ).drop_duplicates("cell_id").set_index("cell_id")
    result["nearest_distance_leisure_m"] = nearest["nearest_distance_leisure_m"]
    if "name" in nearest.columns:
        result["nearest_leisure_name"] = nearest["name"]
    if "leisure_type" in nearest.columns:
        result["nearest_leisure_type"] = nearest["leisure_type"]

    buffers = origins[["cell_id", "geometry"]].copy()
    buffers["geometry"] = buffers.geometry.buffer(count_radius_m)
    nearby = gpd.sjoin(
        buffers,
        data[["facility_id", "leisure_category", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    if not nearby.empty:
        grouped = nearby.groupby("cell_id", sort=False)
        result.loc[grouped.groups.keys(), "leisure_count_750m"] = (
            grouped["facility_id"].nunique().astype(int)
        )
        categories_by_cell = grouped["leisure_category"].agg(
            lambda values: sorted(set(values))
        )
        for cell_id, categories in categories_by_cell.items():
            result.at[cell_id, "leisure_category_count_750m"] = len(categories)
            result.at[cell_id, "leisure_categories_750m"] = ",".join(categories)

    distance_score = (
        100.0 * (1.0 - result["nearest_distance_leisure_m"] / distance_threshold_m)
    ).clip(lower=0.0, upper=100.0)
    count_bonus = result["leisure_count_750m"].map(leisure_count_bonus)
    diversity_bonus = result["leisure_category_count_750m"].map(leisure_diversity_bonus)
    result["score_leisure"] = (
        distance_score + count_bonus + diversity_bonus
    ).clip(0.0, 100.0)
    return result.reset_index()[columns]
