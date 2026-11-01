"""Medical accessibility from grid-cell centroids to OSM facility geometries.

Distances are straight-line baselines, not pedestrian-network travel times.
Pharmacies are intentionally excluded: they belong to daily infrastructure.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_DISTANCE_THRESHOLD_M = 2000.0


def calculate_medical_accessibility(
    grid: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
) -> pd.DataFrame:
    """Calculate nearest medical-facility distance and a 0-100 score.

    Facilities may be points or polygons. Pharmacies must be filtered out by
    the caller so they are not counted both here and in daily infrastructure.
    Missing facilities produce NaN distance and score.
    """
    if distance_threshold_m <= 0:
        raise ValueError("distance_threshold_m должен быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    if grid.crs is None or facilities.crs is None:
        raise ValueError("У сетки и медицинских объектов должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")
    if not facilities.empty and facilities.geometry.isna().any():
        raise ValueError("У медицинских объектов отсутствует геометрия.")

    columns = [
        "cell_id",
        "nearest_distance_medical_m",
        "nearest_medical_name",
        "nearest_medical_type",
        "score_medical",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid

    if facilities.empty:
        result = origins[["cell_id"]].copy()
        result["nearest_distance_medical_m"] = float("nan")
        result["nearest_medical_name"] = None
        result["nearest_medical_type"] = None
        result["score_medical"] = float("nan")
        return result[columns]

    facility_columns = ["geometry"]
    for column in ("name", "medical_type"):
        if column in facilities.columns:
            facility_columns.append(column)
    facility_data = facilities[facility_columns].copy().to_crs(metric_crs)
    facility_data = facility_data.loc[
        facility_data.geometry.notna() & ~facility_data.geometry.is_empty
    ].copy()
    if facility_data.empty:
        return calculate_medical_accessibility(
            grid, facilities.iloc[0:0], metric_crs=metric_crs,
            distance_threshold_m=distance_threshold_m,
        )

    nearest = gpd.sjoin_nearest(
        origins,
        facility_data.reset_index(drop=True),
        how="left",
        distance_col="nearest_distance_medical_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_medical_m"], kind="stable"
    ).drop_duplicates("cell_id")

    result = nearest[["cell_id", "nearest_distance_medical_m"]].copy()
    result["nearest_medical_name"] = (
        nearest["name"].to_numpy() if "name" in nearest.columns else None
    )
    result["nearest_medical_type"] = (
        nearest["medical_type"].to_numpy()
        if "medical_type" in nearest.columns else None
    )
    result["score_medical"] = (
        100.0 * (1.0 - result["nearest_distance_medical_m"] / distance_threshold_m)
    ).clip(lower=0.0, upper=100.0)
    return result[columns].reset_index(drop=True)
