import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.medical_accessibility import calculate_medical_accessibility

CRS = "EPSG:32640"
X = 632000.0
Y = 5910000.0


def make_grid():
    return gpd.GeoDataFrame(
        {"cell_id": ["cell_1"]},
        geometry=[box(X - 50, Y - 50, X + 50, Y + 50)],
        crs=CRS,
    )


def test_scores_distance_to_nearest_medical_point():
    facilities = gpd.GeoDataFrame(
        {"name": ["Clinic"], "medical_type": ["clinic"]},
        geometry=[Point(X + 500, Y)],
        crs=CRS,
    )
    result = calculate_medical_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_medical_m"] == pytest.approx(500)
    assert result.loc[0, "score_medical"] == pytest.approx(75)
    assert result.loc[0, "nearest_medical_name"] == "Clinic"


def test_uses_medical_polygon_geometry():
    facilities = gpd.GeoDataFrame(
        {"name": ["Hospital"], "medical_type": ["hospital"]},
        geometry=[box(X + 400, Y - 100, X + 600, Y + 100)],
        crs=CRS,
    )
    result = calculate_medical_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_medical_m"] == pytest.approx(400)
    assert result.loc[0, "score_medical"] == pytest.approx(80)


def test_facility_covering_cell_centroid_has_zero_distance():
    facilities = gpd.GeoDataFrame(
        {"name": ["Medical centre"], "medical_type": ["centre"]},
        geometry=[box(X - 10, Y - 10, X + 10, Y + 10)],
        crs=CRS,
    )
    result = calculate_medical_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_medical_m"] == pytest.approx(0)
    assert result.loc[0, "score_medical"] == pytest.approx(100)


def test_no_facilities_returns_missing_score():
    facilities = gpd.GeoDataFrame(
        {"name": [], "medical_type": []},
        geometry=gpd.GeoSeries([], crs=CRS),
        crs=CRS,
    )
    result = calculate_medical_accessibility(make_grid(), facilities)
    assert pd.isna(result.loc[0, "nearest_distance_medical_m"])
    assert pd.isna(result.loc[0, "score_medical"])


def test_rejects_duplicate_cell_ids():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["same", "same"]},
        geometry=[box(X - 50, Y - 50, X + 50, Y + 50),
                  box(X + 50, Y - 50, X + 150, Y + 50)],
        crs=CRS,
    )
    facilities = gpd.GeoDataFrame(
        {"name": ["Clinic"], "medical_type": ["clinic"]},
        geometry=[Point(X, Y)],
        crs=CRS,
    )
    with pytest.raises(ValueError, match="cell_id"):
        calculate_medical_accessibility(grid, facilities)
