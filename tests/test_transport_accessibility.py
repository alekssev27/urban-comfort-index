import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.transport_accessibility import (
    calculate_transport_accessibility,
    transport_count_bonus,
    transport_diversity_bonus,
)

CRS = "EPSG:32640"
CENTER_X = 632000.0
CENTER_Y = 5910000.0


def make_grid(cell_ids=None):
    cell_ids = cell_ids or ["cell_1"]
    return gpd.GeoDataFrame(
        {"cell_id": cell_ids},
        geometry=[box(CENTER_X - 50 + i * 100, CENTER_Y - 50,
                      CENTER_X + 50 + i * 100, CENTER_Y + 50)
                  for i in range(len(cell_ids))],
        crs=CRS,
    )


def make_stops(rows):
    return gpd.GeoDataFrame(
        rows,
        geometry=[Point(row["x"], row["y"]) for row in rows],
        crs=CRS,
    ).drop(columns=["x", "y"])


def test_calculates_nearest_stop_distance_and_score():
    stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus"], "x": CENTER_X + 100, "y": CENTER_Y},
    ])
    result = calculate_transport_accessibility(make_grid(), stops)
    assert result.loc[0, "nearest_distance_transport_m"] == pytest.approx(100)
    assert result.loc[0, "nearest_stop_group_id"] == "s1"
    assert result.loc[0, "transport_stop_count_500m"] == 1
    assert result.loc[0, "transport_mode_count_500m"] == 1
    assert result.loc[0, "score_transport"] == pytest.approx(95)


def test_counts_each_stop_once_and_collects_all_modes():
    stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus", "tram"], "x": CENTER_X + 1000, "y": CENTER_Y},
        {"stop_group_id": "s2", "name": "B", "transport_modes": ["tram"], "x": CENTER_X + 1100, "y": CENTER_Y},
        {"stop_group_id": "s3", "name": "C", "transport_modes": ["train"], "x": CENTER_X + 1200, "y": CENTER_Y},
    ])
    result = calculate_transport_accessibility(make_grid(), stops)
    assert result.loc[0, "transport_stop_count_500m"] == 0
    assert result.loc[0, "transport_mode_count_500m"] == 0
    assert result.loc[0, "score_transport"] == pytest.approx(40)


def test_counts_stops_within_radius_and_unique_transport_modes():
    stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus", "tram"], "x": CENTER_X + 1000, "y": CENTER_Y},
        {"stop_group_id": "s2", "name": "B", "transport_modes": ["tram"], "x": CENTER_X + 1100, "y": CENTER_Y},
        {"stop_group_id": "s3", "name": "C", "transport_modes": ["train"], "x": CENTER_X + 1200, "y": CENTER_Y},
    ])
    result = calculate_transport_accessibility(make_grid(), stops, count_radius_m=1250)
    assert result.loc[0, "transport_stop_count_500m"] == 3
    assert result.loc[0, "transport_mode_count_500m"] == 3
    assert result.loc[0, "transport_modes_500m"] == "bus,train,tram"
    assert result.loc[0, "score_transport"] == pytest.approx(63)


def test_stops_outside_count_radius_still_contribute_nearest_distance():
    stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus"], "x": CENTER_X + 700, "y": CENTER_Y},
    ])
    result = calculate_transport_accessibility(make_grid(), stops)
    assert result.loc[0, "nearest_distance_transport_m"] == pytest.approx(700)
    assert result.loc[0, "transport_stop_count_500m"] == 0
    assert result.loc[0, "score_transport"] == pytest.approx(65)


def test_empty_stops_returns_missing_distance_and_score():
    stops = gpd.GeoDataFrame(
        {"stop_group_id": [], "name": [], "transport_modes": []},
        geometry=gpd.GeoSeries([], crs=CRS), crs=CRS,
    )
    result = calculate_transport_accessibility(make_grid(), stops)
    assert result.loc[0, "transport_stop_count_500m"] == 0
    assert pd.isna(result.loc[0, "nearest_distance_transport_m"])
    assert pd.isna(result.loc[0, "score_transport"])


def test_rejects_duplicate_cell_ids_and_stop_ids():
    duplicate_grid = make_grid(["same", "same"])
    unique_stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus"], "x": CENTER_X, "y": CENTER_Y},
    ])
    duplicate_stops = make_stops([
        {"stop_group_id": "s1", "name": "A", "transport_modes": ["bus"], "x": CENTER_X, "y": CENTER_Y},
        {"stop_group_id": "s1", "name": "B", "transport_modes": ["tram"], "x": CENTER_X + 10, "y": CENTER_Y},
    ])
    with pytest.raises(ValueError, match="cell_id"):
        calculate_transport_accessibility(duplicate_grid, unique_stops)
    with pytest.raises(ValueError, match="stop_group_id"):
        calculate_transport_accessibility(make_grid(), duplicate_stops)


def test_transport_bonus_thresholds():
    assert [transport_count_bonus(n) for n in range(6)] == [0, 0, 1, 3, 5, 10]
    assert [transport_diversity_bonus(n) for n in range(5)] == [0, 0, 5, 10, 15]
