from scripts.fetch_osm_infrastructure import assign_category


def test_assigns_school_to_education():
    assert assign_category({"amenity": "school"}) == "education"


def test_assigns_bus_stop_to_transport():
    assert assign_category({"highway": "bus_stop"}) == "transport"


def test_assigns_unknown_shop_to_daily():
    assert assign_category({"shop": "clothes"}) == "daily"


def test_ignores_unmapped_object():
    assert assign_category({"amenity": "bench"}) is None
