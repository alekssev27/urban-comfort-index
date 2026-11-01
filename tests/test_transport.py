import pytest
from src.transport import deduplicate_transport_features


def feature(osm_id, lon, lat, tags, category="transport"):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "osm_type": "node",
            "osm_id": osm_id,
            "category": category,
            "name": None,
            "tags": tags,
        },
    }


def test_groups_platform_and_bus_stop_at_same_physical_stop():
    items = [
        feature(1, 58.98, 53.40, {"highway": "bus_stop"}),
        feature(2, 58.98005, 53.40, {"public_transport": "platform", "bus": "yes"}),
    ]

    result = deduplicate_transport_features(items)

    assert len(result) == 1
    assert result[0]["properties"]["member_count"] == 2
    assert len(result[0]["properties"]["member_osm_objects"]) == 2
    assert result[0]["properties"]["transport_modes"] == ["bus"]


def test_does_not_merge_stops_farther_than_radius():
    items = [
        feature(1, 58.98, 53.40, {"highway": "bus_stop"}),
        feature(2, 58.981, 53.40, {"highway": "bus_stop"}),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 2


def test_complete_link_prevents_chaining_three_stops():
    # A-B and B-C are close, but A-C are farther apart than 25 metres.
    items = [
        feature(1, 58.98000, 53.40, {"highway": "bus_stop"}),
        feature(2, 58.98025, 53.40, {"public_transport": "platform"}),
        feature(3, 58.98050, 53.40, {"highway": "bus_stop"}),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 2


def test_ignores_non_transport_features():
    items = [
        feature(1, 58.98, 53.40, {"highway": "bus_stop"}),
        feature(2, 58.98001, 53.40, {"shop": "supermarket"}, category="daily"),
    ]

    result = deduplicate_transport_features(items)

    assert len(result) == 1
    assert result[0]["properties"]["member_count"] == 1


def test_rejects_non_positive_merge_radius():
    with pytest.raises(ValueError):
        deduplicate_transport_features([], merge_radius_m=0)
