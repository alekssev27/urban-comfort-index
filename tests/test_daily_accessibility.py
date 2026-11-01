import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.daily_accessibility import (
    calculate_daily_accessibility,
    daily_count_bonus,
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
    return gpd.GeoDataFrame(
        rows,
        geometry=[row.pop("geometry") for row in rows],
        crs=CRS,
    )


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0), (2, 0), (3, 1), (4, 3), (5, 5), (7, 10), (8, 10)],
)
def test_daily_count_bonus_thresholds(count, expected):
    assert daily_count_bonus(count) == expected


def test_distance_score_and_basic_count_bonus():
    facilities = make_facilities([
        {"facility_id": "a", "daily_group": "basic", "daily_type": "shop",
         "name": "Shop", "geometry": Point(X + 500, Y)},
        {"facility_id": "b", "daily_group": "basic", "daily_type": "pharmacy",
         "name": "Pharmacy", "geometry": Point(X + 100, Y)},
        {"facility_id": "c", "daily_group": "basic", "daily_type": "market",
         "name": "Market", "geometry": Point(X - 100, Y)},
    ])
    result = calculate_daily_accessibility(make_grid(), facilities)
    assert result.loc[0, "nearest_distance_daily_m"] == pytest.approx(100)
    assert result.loc[0, "daily_basic_count_500m"] == 3
    assert result.loc[0, "daily_weighted_count_500m"] == pytest.approx(3)
    assert result.loc[0, "score_daily"] == pytest.approx(96)


def test_additional_facilities_weighted_only_when_basic_exists():
    facilities = make_facilities([
        {"facility_id": "basic", "daily_group": "basic", "daily_type": "shop",
         "name": "Shop", "geometry": Point(X + 100, Y)},
        {"facility_id": "bank", "daily_group": "additional", "daily_type": "bank",
         "name": "Bank", "geometry": Point(X + 150, Y)},
        {"facility_id": "atm", "daily_group": "additional", "daily_type": "atm",
         "name": "ATM", "geometry": Point(X + 200, Y)},
    ])
    result = calculate_daily_accessibility(make_grid(), facilities)
    assert result.loc[0, "daily_basic_count_500m"] == 1
    assert result.loc[0, "daily_additional_count_500m"] == 2
    assert result.loc[0, "daily_weighted_count_500m"] == pytest.approx(1.8)
    assert result.loc[0, "score_daily"] == pytest.approx(95)


def test_additional_facilities_do_not_count_without_basic_facility_nearby():
    facilities = make_facilities([
        {"facility_id": "basic", "daily_group": "basic", "daily_type": "shop",
         "name": "Distant shop", "geometry": Point(X + 1000, Y)},
        {"facility_id": "bank", "daily_group": "additional", "daily_type": "bank",
         "name": "Bank", "geometry": Point(X + 100, Y)},
    ])
    result = calculate_daily_accessibility(make_grid(), facilities)
    assert result.loc[0, "daily_basic_count_500m"] == 0
    assert result.loc[0, "daily_additional_count_500m"] == 1
    assert result.loc[0, "daily_weighted_count_500m"] == 0
    assert result.loc[0, "score_daily"] == pytest.approx(50)


def test_polygon_facilities_are_counted_by_intersection():
    facilities = make_facilities([
        {"facility_id": "market", "daily_group": "basic", "daily_type": "market",
         "name": "Market", "geometry": box(X + 400, Y - 50, X + 600, Y + 50)},
    ])
    result = calculate_daily_accessibility(make_grid(), facilities)
    assert result.loc[0, "daily_basic_count_500m"] == 1
    assert result.loc[0, "nearest_distance_daily_m"] == pytest.approx(400)


def test_no_basic_facilities_returns_missing_score():
    facilities = make_facilities([
        {"facility_id": "bank", "daily_group": "additional", "daily_type": "bank",
         "name": "Bank", "geometry": Point(X + 100, Y)},
    ])
    result = calculate_daily_accessibility(make_grid(), facilities)
    assert pd.isna(result.loc[0, "score_daily"])


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
        {"facility_id": "shop", "daily_group": "basic", "daily_type": "shop",
         "name": "Shop", "geometry": Point(X, Y)},
    ])
    with pytest.raises(ValueError, match="cell_id"):
        calculate_daily_accessibility(grid, facilities)
