"""Accessibility baseline using straight-line distances, not walking routes."""
import geopandas as gpd
import pandas as pd

DEFAULT_METRIC_CRS = "EPSG:32640"


def nearest_distance_by_category(origins: gpd.GeoDataFrame, facilities: gpd.GeoDataFrame, *, category_column: str = "category", metric_crs: str = DEFAULT_METRIC_CRS) -> pd.DataFrame:
    """Return nearest point distance (metres) for each origin/category.

    Origins require unique cell_id values; both layers need a CRS. Missing
    categories remain absent/NaN downstream and must not be treated as zero.
    """
    if "cell_id" not in origins.columns:
        raise ValueError("origins должен содержать столбец cell_id.")
    if origins["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    if category_column not in facilities.columns:
        raise ValueError(f"facilities должен содержать столбец {category_column}.")
    if origins.crs is None or facilities.crs is None:
        raise ValueError("У обоих GeoDataFrame должен быть задан CRS.")
    columns = ["cell_id", "category", "nearest_distance_m"]
    if origins.empty or facilities.empty:
        return pd.DataFrame(columns=columns)
    origin_points = origins[["cell_id", "geometry"]].to_crs(metric_crs)
    facility_points = facilities[[category_column, "geometry"]].to_crs(metric_crs)
    if not facility_points.geometry.geom_type.isin(["Point", "MultiPoint"]).all():
        raise ValueError("Инфраструктура должна быть представлена точками.")
    rows = []
    for category, group in facility_points.groupby(category_column, dropna=True):
        points = list(group.geometry)
        for _, origin in origin_points.iterrows():
            rows.append({"cell_id": origin["cell_id"], "category": category, "nearest_distance_m": float(min(origin.geometry.distance(point) for point in points))})
    return pd.DataFrame(rows, columns=columns)


def distance_score(distance_m: float, threshold_m: float) -> float:
    """Provisional linear 0-100 score; threshold must be calibrated by category."""
    if threshold_m <= 0:
        raise ValueError("threshold_m должен быть больше нуля.")
    if pd.isna(distance_m):
        return float("nan")
    return max(0.0, min(100.0, 100.0 * (1.0 - float(distance_m) / threshold_m)))
