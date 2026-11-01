"""Фильтрация сетки по фактическим контурам жилых зданий."""
from __future__ import annotations

import geopandas as gpd

METRIC_CRS = "EPSG:32640"


def filter_grid_by_residential_buildings(
    grid: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Оставить ячейки, имеющие пересечение положительной площади с жилым зданием.

    Оба слоя переводятся в метрическую CRS для корректной проверки площади.
    Простое касание границ без общей площади не считается жилой ячейкой.
    """
    if grid.empty:
        raise ValueError("Сетка пуста.")
    if buildings.empty:
        raise ValueError("Слой жилых зданий пуст.")
    if grid.crs is None or buildings.crs is None:
        raise ValueError("У сетки и жилых зданий должна быть указана CRS.")
    if "cell_id" not in grid.columns:
        raise ValueError("В сетке отсутствует cell_id.")

    grid_metric = grid.to_crs(METRIC_CRS)
    buildings_metric = buildings.to_crs(METRIC_CRS)
    buildings_metric = buildings_metric[
        buildings_metric.geometry.notna()
        & ~buildings_metric.geometry.is_empty
        & buildings_metric.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    ]
    if buildings_metric.empty:
        raise ValueError("В слое не найдено полигональных контуров жилых зданий.")

    spatial_index = buildings_metric.sindex
    keep = []
    for geometry in grid_metric.geometry:
        candidate_positions = spatial_index.query(geometry, predicate="intersects")
        has_area_overlap = any(
            geometry.intersection(buildings_metric.geometry.iloc[int(position)]).area > 0
            for position in candidate_positions
        )
        keep.append(has_area_overlap)

    filtered = grid.loc[keep].copy().reset_index(drop=True)
    if filtered.empty:
        raise ValueError(
            "Ни одна ячейка сетки не пересекается с жилыми зданиями. "
            "Проверьте контуры зданий и CRS."
        )
    if filtered["cell_id"].duplicated().any():
        raise ValueError("После фильтрации обнаружены повторяющиеся cell_id.")
    return filtered
