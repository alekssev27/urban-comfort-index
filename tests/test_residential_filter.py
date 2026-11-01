import geopandas as gpd
import pytest
from shapely.geometry import box

from src.residential_filter import filter_grid_by_residential_buildings


def test_keeps_only_cells_with_positive_building_overlap():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["a", "b", "c"]},
        geometry=[box(0, 0, 250, 250), box(250, 0, 500, 250), box(500, 0, 750, 250)],
        crs="EPSG:32640",
    )
    buildings = gpd.GeoDataFrame(
        {"building": ["apartments", "house"]},
        geometry=[box(20, 20, 80, 80), box(250, 20, 280, 80)],
        crs="EPSG:32640",
    )

    result = filter_grid_by_residential_buildings(grid, buildings)

    assert result["cell_id"].tolist() == ["a", "b"]


def test_does_not_keep_cell_for_boundary_touch_only():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["a", "b"]},
        geometry=[box(0, 0, 250, 250), box(250, 0, 500, 250)],
        crs="EPSG:32640",
    )
    buildings = gpd.GeoDataFrame(
        geometry=[box(250, 20, 300, 80)],
        crs="EPSG:32640",
    )

    result = filter_grid_by_residential_buildings(grid, buildings)

    assert result["cell_id"].tolist() == ["b"]


def test_rejects_empty_buildings():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["a"]}, geometry=[box(0, 0, 250, 250)], crs="EPSG:32640"
    )
    buildings = gpd.GeoDataFrame(geometry=[], crs="EPSG:32640")

    with pytest.raises(ValueError, match="пуст"):
        filter_grid_by_residential_buildings(grid, buildings)
