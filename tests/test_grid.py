import geopandas as gpd
import pytest
from shapely.geometry import box
from src.grid import generate_square_grid


def test_grid_cells_are_250m_squares_in_metric_crs():
    grid = generate_square_grid(box(58.98, 53.42, 58.99, 53.43), 250)
    assert not grid.empty
    assert grid.crs.to_epsg() == 32640
    assert grid.cell_id.is_unique
    assert (grid.cell_size_m == 250).all()
    for geometry in grid.geometry:
        assert geometry.area == pytest.approx(62500)
        assert geometry.geom_type == "Polygon"


def test_invalid_cell_size_is_rejected():
    with pytest.raises(ValueError):
        generate_square_grid(box(58.98, 53.42, 58.99, 53.43), 0)


def test_geodataframe_requires_crs():
    boundary = gpd.GeoDataFrame(geometry=[box(58.98, 53.42, 58.99, 53.43)])
    with pytest.raises(ValueError, match="CRS"):
        generate_square_grid(boundary, 250)


def test_partial_cells_are_clipped_to_boundary():
    grid = generate_square_grid(box(58.98, 53.42, 58.981, 53.421), 250, include_partial_cells=True)
    assert not grid.empty
    assert all(geometry.area <= 62500 for geometry in grid.geometry)
