import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.green_accessibility import (
    calculate_green_accessibility,
    dissolve_green_areas,
)

CRS = "EPSG:32640"
X = 632000.0
Y = 5910000.0


def make_grid():
    return gpd.GeoDataFrame(
        {"cell_id": ["cell_1"]},
        geometry=[box(X - 50, Y - 50, X + 50, Y + 50)],
        crs=CRS,
    )


def make_green(geometries):
    return gpd.GeoDataFrame(
        {"name": [f"Green {i}" for i in range(len(geometries))]},
        geometry=geometries,
        crs=CRS,
    )


def test_combines_distance_and_area_factors():
    green = make_green([box(X + 500, Y - 50, X + 600, Y + 50)])
    result = calculate_green_accessibility(make_grid(), green)
    expected = 100 * (1 - (1 - (1 - 500 / 1500) * (10000 / 30000) ** 0.5))
    assert result.loc[0, "nearest_distance_green_m"] == pytest.approx(500)
    assert result.loc[0, "score_green"] == pytest.approx(expected)
    assert result.loc[0, "green_area_count_1500m"] == 1


def test_area_factor_is_capped_at_reference_area():
    green = make_green([box(X - 100, Y - 100, X + 100, Y + 100)])
    result = calculate_green_accessibility(make_grid(), green)
    assert result.loc[0, "nearest_distance_green_m"] == pytest.approx(0)
    assert result.loc[0, "score_green"] == pytest.approx(100)


def test_overlapping_polygons_are_dissolved_before_scoring():
    green = make_green([
        box(X + 100, Y - 50, X + 200, Y + 50),
        box(X + 150, Y - 50, X + 250, Y + 50),
    ])
    dissolved = dissolve_green_areas(green)
    assert len(dissolved) == 1
    assert dissolved.loc[0, "area_m2"] == pytest.approx(15000)
    result = calculate_green_accessibility(make_grid(), green)
    distance_factor = 1 - 100 / 1500
    area_factor = (15000 / 30000) ** 0.5
    assert result.loc[0, "score_green"] == pytest.approx(
        100 * distance_factor * area_factor
    )


def test_multiple_separate_green_areas_combine_without_exceeding_100():
    green = make_green([
        box(X + 100, Y - 50, X + 200, Y + 50),
        box(X - 200, Y - 50, X - 100, Y + 50),
    ])
    result = calculate_green_accessibility(make_grid(), green)
    assert result.loc[0, "green_area_count_1500m"] == 2
    assert 0 <= result.loc[0, "score_green"] <= 100


def test_no_green_area_within_threshold_gets_zero_but_keeps_nearest_distance():
    green = make_green([box(X + 2000, Y - 50, X + 2100, Y + 50)])
    result = calculate_green_accessibility(make_grid(), green)
    assert result.loc[0, "nearest_distance_green_m"] == pytest.approx(1950)
    assert result.loc[0, "green_area_count_1500m"] == 0
    assert result.loc[0, "score_green"] == 0


def test_empty_green_layer_returns_missing_score():
    green = gpd.GeoDataFrame(
        {"name": []},
        geometry=gpd.GeoSeries([], crs=CRS),
        crs=CRS,
    )
    result = calculate_green_accessibility(make_grid(), green)
    assert pd.isna(result.loc[0, "score_green"])


def test_rejects_duplicate_cell_ids():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["same", "same"]},
        geometry=[
            box(X - 50, Y - 50, X + 50, Y + 50),
            box(X + 50, Y - 50, X + 150, Y + 50),
        ],
        crs=CRS,
    )
    with pytest.raises(ValueError, match="cell_id"):
        calculate_green_accessibility(grid, make_green([box(X, Y, X + 100, Y + 100)]))
