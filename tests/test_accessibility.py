import geopandas as gpd
import pytest
from shapely.geometry import Point
from src.accessibility import distance_score, nearest_distance_by_category


def test_distance_score():
    assert distance_score(0, 1000) == 100
    assert distance_score(500, 1000) == 50
    assert distance_score(1500, 1000) == 0


def test_distance_score_rejects_nonpositive_threshold():
    with pytest.raises(ValueError):
        distance_score(10, 0)


def test_nearest_distance_by_category():
    origins = gpd.GeoDataFrame({"cell_id": ["a"]}, geometry=[Point(0, 0)], crs="EPSG:32640")
    facilities = gpd.GeoDataFrame({"category": ["school", "school", "park"]}, geometry=[Point(300, 400), Point(100, 0), Point(0, 800)], crs="EPSG:32640")
    result = nearest_distance_by_category(origins, facilities)
    distances = dict(zip(result.category, result.nearest_distance_m))
    assert distances["school"] == pytest.approx(100)
    assert distances["park"] == pytest.approx(800)
