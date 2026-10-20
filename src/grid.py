"""Generate a square analysis grid in a metric CRS."""
from __future__ import annotations
import math
import geopandas as gpd
from shapely.geometry.base import BaseGeometry

DEFAULT_CRS = "EPSG:32640"  # UTM zone 40N, suitable for preliminary Magnitogorsk analysis.
DEFAULT_CELL_SIZE_M = 250


def generate_square_grid(boundary, cell_size_m: int = DEFAULT_CELL_SIZE_M, *, source_crs: str = "EPSG:4326", metric_crs: str = DEFAULT_CRS, include_partial_cells: bool = False) -> gpd.GeoDataFrame:
    """Build square cells from a Polygon/MultiPolygon or GeoDataFrame/GeoSeries.

    By default, retain full cells whose centroid is covered by the boundary.
    Set include_partial_cells=True to retain intersecting cells clipped to it.
    A verified boundary must be supplied; this function never invents one.
    """
    if isinstance(cell_size_m, bool) or not isinstance(cell_size_m, int) or cell_size_m <= 0:
        raise ValueError("cell_size_m должен быть положительным целым числом.")
    if isinstance(boundary, (gpd.GeoDataFrame, gpd.GeoSeries)):
        if boundary.crs is None:
            raise ValueError("Для GeoDataFrame/GeoSeries необходимо задать CRS.")
        source = gpd.GeoSeries(boundary.geometry if isinstance(boundary, gpd.GeoDataFrame) else boundary, crs=boundary.crs)
        geom = source.to_crs(metric_crs).union_all()
    else:
        if boundary is None or boundary.is_empty:
            raise ValueError("Граница территории пуста.")
        geom = gpd.GeoSeries([boundary], crs=source_crs).to_crs(metric_crs).iloc[0]
    if geom is None or geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Граница должна быть непустым Polygon или MultiPolygon.")
    min_x, min_y, max_x, max_y = geom.bounds
    start_x = math.floor(min_x / cell_size_m) * cell_size_m
    start_y = math.floor(min_y / cell_size_m) * cell_size_m
    end_x = math.ceil(max_x / cell_size_m) * cell_size_m
    end_y = math.ceil(max_y / cell_size_m) * cell_size_m
    records = []
    for x in range(start_x, end_x, cell_size_m):
        for y in range(start_y, end_y, cell_size_m):
            square = gpd.GeoSeries.from_bbox((x, y, x + cell_size_m, y + cell_size_m)).iloc[0] if False else None
            from shapely.geometry import box
            square = box(x, y, x + cell_size_m, y + cell_size_m)
            if include_partial_cells:
                if not square.intersects(geom):
                    continue
                cell_geometry = square.intersection(geom)
                if cell_geometry.is_empty:
                    continue
            else:
                if not geom.covers(square.centroid):
                    continue
                cell_geometry = square
            records.append({"cell_id": f"utm40_{x}_{y}_{cell_size_m}", "grid_x": x, "grid_y": y, "cell_size_m": cell_size_m, "geometry": cell_geometry})
    if not records:
        raise ValueError("Внутри границы не найдено ячеек. Проверьте CRS и геометрию.")
    return gpd.GeoDataFrame(records, geometry="geometry", crs=metric_crs)


def load_boundary(path: str, *, target_crs: str = DEFAULT_CRS) -> gpd.GeoDataFrame:
    """Load a polygon boundary file and transform it to the metric CRS."""
    boundary = gpd.read_file(path)
    if boundary.empty:
        raise ValueError(f"Файл границы пуст: {path}")
    if boundary.crs is None:
        raise ValueError("У файла границы не указан CRS.")
    boundary = boundary.to_crs(target_crs)
    boundary = boundary[boundary.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if boundary.empty:
        raise ValueError("В файле не найдены Polygon/MultiPolygon.")
    return boundary
