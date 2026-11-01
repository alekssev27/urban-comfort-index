import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.leisure_accessibility import (
    calculate_leisure_accessibility,
    leisure_count_bonus,
    leisure_diversity_bonus,
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


def make_facilities(rows):
    geometries = [row["geometry"] for row in rows]
    attributes = [{key: value for key, value in row.items() if key != "geometry"} for row in rows]
    return gpd.GeoDataFrame(attributes, geometry=geometries, crs=CRS)


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0), (2, 0), (3, 1), (5, 1), (6, 3), (9, 3), (10, 5), (14, 5), (15, 10)],
)
def test_count_bonus_thresholds(count, expected):
    assert leisure_count_bonus(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0), (1, 0), (2, 5), (3, 10), (4, 15), (5, 15), (6, 20)],
)
def test_diversity_bonus_thresholds(count, expected):
    assert leisure_diversity_bonus(count) == expected


def test_distance_count_and_diversity_are_combined():
    facilities = make_facilities([
        {"facility_id": "a", "leisure_category": "food_service",
         "leisure_type": "cafe", "name": "Cafe", "geometry": Point(X + 500, Y)},
        {"facility_id": "b", "leisure_category": "food_service",
         "leisure_type": "restaurant", "name": "Restaurant", "geometry": Point(X + 100, Y)},
        {"facility_id": "c", "leisure_category": "cinema_theatre",
         "leisure_type": "cinema", "name": "Cinema", "geometry": Point(X - 100, Y)},
    ])
    result = calculate_leisure_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_leisure_m"] == pytest.approx(100)
    assert result.loc[0, "leisure_count_750m"] == 3
    assert result.loc[0, "leisure_category_count_750m"] == 2
    assert result.loc[0, "score_leisure"] == pytest.approx(100)


def test_facility_polygon_is_counted_once():
    facilities = make_facilities([
        {"facility_id": "mall", "leisure_category": "shopping_entertainment",
         "leisure_type": "mall", "name": "Mall",
         "geometry": box(X + 500, Y - 50, X + 700, Y + 50)},
    ])
    result = calculate_leisure_accessibility(make_grid(), facilities)
    assert result.loc[0, "leisure_count_750m"] == 1
    assert result.loc[0, "nearest_distance_leisure_m"] == pytest.approx(500)


def test_no_facilities_returns_missing_score():
    facilities = gpd.GeoDataFrame(
        {"facility_id": [], "leisure_category": []},
        geometry=gpd.GeoSeries([], crs=CRS),
        crs=CRS,
    )
    result = calculate_leisure_accessibility(make_grid(), facilities)
    assert pd.isna(result.loc[0, "score_leisure"])


def test_rejects_duplicate_cell_ids():
    grid = gpd.GeoDataFrame(
        {"cell_id": ["same", "same"]},
        geometry=[
            box(X - 50, Y - 50, X + 50, Y + 50),
            box(X + 50, Y - 50, X + 150, Y + 50),
        ],
        crs=CRS,
    )
    facilities = make_facilities([
        {"facility_id": "cafe", "leisure_category": "food_service",
         "geometry": Point(X, Y)},
    ])
    with pytest.raises(ValueError, match="cell_id"):
        calculate_leisure_accessibility(grid, facilities)
