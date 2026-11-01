"""Education accessibility from grid-cell centroids to OSM facility geometries.

Uses straight-line distance to the nearest point, line or polygon facility.
This is a geographic baseline, not pedestrian-network travel time.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_DISTANCE_THRESHOLD_M = 2000.0


def calculate_education_accessibility(
    grid: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
) -> pd.DataFrame:
    """Calculate nearest education-facility distance and a 0-100 score.

    Grid requires unique cell_id and polygon geometries. Facilities may be
    points or polygons, because OSM schools and kindergartens are often mapped
    as areas. Missing facilities produce NaN distance and score.
    """
    if distance_threshold_m <= 0:
        raise ValueError("distance_threshold_m должен быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    if grid.crs is None or facilities.crs is None:
        raise ValueError("У сетки и образовательных объектов должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")
    if not facilities.empty and facilities.geometry.isna().any():
        raise ValueError("У образовательных объектов отсутствует геометрия.")

    columns = [
        "cell_id",
        "nearest_distance_education_m",
        "nearest_education_name",
        "nearest_education_amenity",
        "score_education",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid

    if facilities.empty:
        result = origins[["cell_id"]].copy()
        result["nearest_distance_education_m"] = float("nan")
        result["nearest_education_name"] = None
        result["nearest_education_amenity"] = None
        result["score_education"] = float("nan")
        return result[columns]

    facility_columns = ["geometry"]
    for column in ("name", "amenity"):
        if column in facilities.columns:
            facility_columns.append(column)
    facility_data = facilities[facility_columns].copy().to_crs(metric_crs)
    facility_data = facility_data.loc[
        facility_data.geometry.notna() & ~facility_data.geometry.is_empty
    ].copy()
    if facility_data.empty:
        return calculate_education_accessibility(
            grid, facilities.iloc[0:0], metric_crs=metric_crs,
            distance_threshold_m=distance_threshold_m,
        )

    facility_data = facility_data.reset_index(drop=True)
    nearest = gpd.sjoin_nearest(
        origins,
        facility_data,
        how="left",
        distance_col="nearest_distance_education_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_education_m"], kind="stable"
    ).drop_duplicates("cell_id")

    result = nearest[[
        "cell_id", "nearest_distance_education_m"
    ]].copy()
    result["nearest_education_name"] = (
        nearest["name"].to_numpy() if "name" in nearest.columns else None
    )
    result["nearest_education_amenity"] = (
        nearest["amenity"].to_numpy() if "amenity" in nearest.columns else None
    )
    result["score_education"] = (
        100.0 * (1.0 - result["nearest_distance_education_m"] / distance_threshold_m)
    ).clip(lower=0.0, upper=100.0)
    return result[columns].reset_index(drop=True)
