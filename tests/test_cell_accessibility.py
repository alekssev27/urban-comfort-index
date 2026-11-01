import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from scripts.calculate_cell_accessibility import calculate_cell_accessibility


def test_calculate_cell_accessibility_returns_distances_and_residentiality():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["cell_a", "cell_b"]},
        geometry=[box(0, 0, 250, 250), box(500, 0, 750, 250)],
        crs="EPSG:32640",
    )
    facilities = gpd.GeoDataFrame(
        {"category": ["education", "medical"]},
        geometry=[Point(125, 375), Point(875, 125)],
        crs="EPSG:32640",
    )
    residentiality = pd.DataFrame({
        "cell_id": ["cell_a", "cell_b"],
        "residential_building_count": [3, 0],
        "has_residential_building": [True, False],
    })

    result = calculate_cell_accessibility(grid, facilities, residentiality)

    assert len(result) == 2
    assert result.loc[0, "nearest_distance_education_m"] == pytest.approx(250)
    assert result.loc[0, "nearest_distance_medical_m"] > 0
    assert pd.isna(result.loc[0, "nearest_distance_transport_m"])
    assert result.loc[0, "residential_building_count"] == 3
    assert bool(result.loc[1, "has_residential_building"]) is False


def test_calculate_cell_accessibility_requires_unique_cell_ids():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["same", "same"]},
        geometry=[box(0, 0, 250, 250), box(250, 0, 500, 250)],
        crs="EPSG:32640",
    )
    facilities = gpd.GeoDataFrame(
        {"category": ["education"]}, geometry=[Point(0, 0)], crs="EPSG:32640"
    )

    with pytest.raises(ValueError, match="уникальными"):
        calculate_cell_accessibility(grid, facilities)
