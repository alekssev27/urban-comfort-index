"""Green-area accessibility using distance and dissolved polygon area.

Main green areas are parks, gardens, nature reserves, forests and recreation
grounds. Overlapping/touching polygons are dissolved before scoring to avoid
double-counting the same physical green space. Distances are straight-line.
"""
from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
from shapely.validation import make_valid

DEFAULT_METRIC_CRS = "EPSG:32640"
DEFAULT_DISTANCE_THRESHOLD_M = 1500.0
DEFAULT_REFERENCE_AREA_M2 = 30000.0


def _polygon_parts(geometry):
    """Extract polygon parts from a possibly multipart/collection geometry."""
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        parts = []
        for part in geometry.geoms:
            parts.extend(_polygon_parts(part))
        return parts
    return []


def dissolve_green_areas(
    green_areas: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
) -> gpd.GeoDataFrame:
    """Project, repair and dissolve overlapping/touching green polygons."""
    if green_areas.crs is None:
        raise ValueError("У зелёных зон должен быть задан CRS.")
    if green_areas.empty:
        return gpd.GeoDataFrame(
            {"green_area_id": [], "area_m2": []},
            geometry=gpd.GeoSeries([], crs=metric_crs),
            crs=metric_crs,
        )

    projected = green_areas[["geometry"]].copy().to_crs(metric_crs)
    geometries = []
    for geometry in projected.geometry:
        if geometry is None or geometry.is_empty:
            continue
        repaired = geometry if geometry.is_valid else make_valid(geometry)
        geometries.extend(_polygon_parts(repaired))

    if not geometries:
        return gpd.GeoDataFrame(
            {"green_area_id": [], "area_m2": []},
            geometry=gpd.GeoSeries([], crs=metric_crs),
            crs=metric_crs,
        )

    dissolved = unary_union(geometries)
    components = [
        part for part in _polygon_parts(dissolved)
        if not part.is_empty and part.area > 0
    ]
    components.sort(key=lambda geom: (geom.bounds[0], geom.bounds[1], geom.area))
    return gpd.GeoDataFrame(
        {
            "green_area_id": [f"green_{i + 1}" for i in range(len(components))],
            "area_m2": [float(geom.area) for geom in components],
        },
        geometry=components,
        crs=metric_crs,
    )


def calculate_green_accessibility(
    grid: gpd.GeoDataFrame,
    green_areas: gpd.GeoDataFrame,
    *,
    metric_crs: str = DEFAULT_METRIC_CRS,
    distance_threshold_m: float = DEFAULT_DISTANCE_THRESHOLD_M,
    reference_area_m2: float = DEFAULT_REFERENCE_AREA_M2,
) -> pd.DataFrame:
    """Calculate the combined distance-and-area score for every grid cell.

    For each dissolved green polygon within the distance threshold:
        D_i = max(0, 1 - distance_i / threshold)
        A_i = min(1, sqrt(area_i / reference_area))
        Q_i = D_i * A_i
    The final score is 100 * (1 - product(1 - Q_i)).
    """
    if distance_threshold_m <= 0:
        raise ValueError("distance_threshold_m должен быть больше нуля.")
    if reference_area_m2 <= 0:
        raise ValueError("reference_area_m2 должен быть больше нуля.")
    if "cell_id" not in grid.columns:
        raise ValueError("grid должен содержать столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("cell_id должен быть уникальным.")
    if grid.crs is None:
        raise ValueError("У сетки должен быть задан CRS.")
    if not grid.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Сетка должна состоять из Polygon или MultiPolygon.")

    columns = [
        "cell_id",
        "nearest_distance_green_m",
        "green_area_count_1500m",
        "green_area_total_m2_1500m",
        "score_green",
    ]
    if grid.empty:
        return pd.DataFrame(columns=columns)

    origins = grid[["cell_id", "geometry"]].copy().to_crs(metric_crs)
    origins["geometry"] = origins.geometry.centroid
    dissolved = dissolve_green_areas(green_areas, metric_crs=metric_crs)

    result = origins[["cell_id"]].copy().set_index("cell_id")
    result["nearest_distance_green_m"] = float("nan")
    result["green_area_count_1500m"] = 0
    result["green_area_total_m2_1500m"] = 0.0
    result["score_green"] = float("nan")

    if dissolved.empty:
        return result.reset_index()[columns]

    nearest = gpd.sjoin_nearest(
        origins,
        dissolved[["green_area_id", "area_m2", "geometry"]],
        how="left",
        distance_col="nearest_distance_green_m",
    )
    nearest = nearest.sort_values(
        ["cell_id", "nearest_distance_green_m", "green_area_id"],
        kind="stable",
    ).drop_duplicates("cell_id").set_index("cell_id")
    result["nearest_distance_green_m"] = nearest["nearest_distance_green_m"]
    result["score_green"] = 0.0

    buffers = origins[["cell_id", "geometry"]].copy()
    buffers["geometry"] = buffers.geometry.buffer(distance_threshold_m)
    nearby = gpd.sjoin(
        buffers,
        dissolved[["green_area_id", "area_m2", "geometry"]],
        how="inner",
        predicate="intersects",
    )
    if not nearby.empty:
        nearby = nearby.copy()
        nearby["distance_m"] = [
            float(origin.distance(area))
            for origin, area in zip(
                origins.set_index("cell_id").loc[nearby["cell_id"], "geometry"],
                dissolved.geometry.iloc[nearby["index_right"].to_numpy()],
            )
        ]
        nearby["distance_factor"] = (
            1.0 - nearby["distance_m"] / distance_threshold_m
        ).clip(lower=0.0, upper=1.0)
        nearby["area_factor"] = (
            nearby["area_m2"] / reference_area_m2
        ).pow(0.5).clip(upper=1.0)
        nearby["contribution"] = (
            nearby["distance_factor"] * nearby["area_factor"]
        )

        for cell_id, group in nearby.groupby("cell_id", sort=False):
            contributions = group["contribution"].tolist()
            score = 100.0 * (1.0 - math.prod(1.0 - value for value in contributions))
            result.at[cell_id, "score_green"] = min(100.0, max(0.0, score))
            result.at[cell_id, "green_area_count_1500m"] = len(group)
            result.at[cell_id, "green_area_total_m2_1500m"] = float(
                group["area_m2"].sum()
            )

    return result.reset_index()[columns]
