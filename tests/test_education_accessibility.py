import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.education_accessibility import calculate_education_accessibility

CRS = "EPSG:32640"
X = 632000.0
Y = 5910000.0


def make_grid():
    return gpd.GeoDataFrame(
        {"cell_id": ["cell_1"]},
        geometry=[box(X - 50, Y - 50, X + 50, Y + 50)],
        crs=CRS,
    )


def test_scores_distance_to_nearest_point_facility():
    facilities = gpd.GeoDataFrame(
        {"name": ["School"], "amenity": ["school"]},
        geometry=[Point(X + 500, Y)],
        crs=CRS,
    )
    result = calculate_education_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_education_m"] == pytest.approx(500)
    assert result.loc[0, "score_education"] == pytest.approx(75)
    assert result.loc[0, "nearest_education_name"] == "School"


def test_uses_polygon_geometry_not_only_centroid_or_point():
    facilities = gpd.GeoDataFrame(
        {"name": ["Kindergarten"], "amenity": ["kindergarten"]},
        geometry=[box(X + 400, Y - 100, X + 600, Y + 100)],
        crs=CRS,
    )
    result = calculate_education_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_education_m"] == pytest.approx(400)
    assert result.loc[0, "score_education"] == pytest.approx(80)


def test_facility_covering_cell_centroid_has_zero_distance():
    facilities = gpd.GeoDataFrame(
        {"name": ["University"], "amenity": ["university"]},
        geometry=[box(X - 10, Y - 10, X + 10, Y + 10)],
        crs=CRS,
    )
    result = calculate_education_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_education_m"] == pytest.approx(0)
    assert result.loc[0, "score_education"] == pytest.approx(100)


def test_no_facilities_returns_missing_score():
    facilities = gpd.GeoDataFrame(
        {"name": [], "amenity": []},
        geometry=gpd.GeoSeries([], crs=CRS),
        crs=CRS,
    )
    result = calculate_education_accessibility(make_grid(), facilities)
    assert pd.isna(result.loc[0, "nearest_distance_education_m"])
    assert pd.isna(result.loc[0, "score_education"])


def test_rejects_duplicate_cell_ids():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["same", "same"]},
        geometry=[box(X - 50, Y - 50, X + 50, Y + 50),
                  box(X + 50, Y - 50, X + 150, Y + 50)],
        crs=CRS,
    )
    facilities = gpd.GeoDataFrame(
        {"name": ["School"], "amenity": ["school"]},
        geometry=[Point(X, Y)],
        crs=CRS,
    )
    with pytest.raises(ValueError, match="cell_id"):
        calculate_education_accessibility(grid, facilities)
