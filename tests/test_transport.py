import pytest

from src.transport import deduplicate_transport_features


def feature(osm_id, lon, lat, tags, category="transport", name=None):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "osm_type": "node",
            "osm_id": osm_id,
            "category": category,
            "name": name,
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
    items = [
        feature(1, 58.98000, 53.40, {"highway": "bus_stop"}),
        feature(2, 58.98025, 53.40, {"public_transport": "platform"}),
        feature(3, 58.98050, 53.40, {"highway": "bus_stop"}),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 2


def test_does_not_merge_close_stops_with_conflicting_names():
    items = [
        feature(1, 58.98, 53.40, {"public_transport": "platform"}, name="Улица Галиуллина"),
        feature(2, 58.98005, 53.40, {"public_transport": "platform"}, name="Дом творчества"),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 2


def test_normalises_common_stop_name_prefixes():
    items = [
        feature(1, 58.98, 53.40, {"public_transport": "platform"}, name="ул. Чапаева"),
        feature(2, 58.98005, 53.40, {"public_transport": "stop_position"}, name="Чапаева"),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 1


def test_missing_name_does_not_prevent_spatial_match():
    items = [
        feature(1, 58.98, 53.40, {"highway": "bus_stop"}, name="Цирк"),
        feature(2, 58.98005, 53.40, {"public_transport": "platform"}, name=None),
    ]

    result = deduplicate_transport_features(items, merge_radius_m=25)

    assert len(result) == 1


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
