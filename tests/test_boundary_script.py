from scripts.fetch_osm_boundary import candidate_kind, is_boundary_candidate


def test_accepts_administrative_boundary_polygon():
    item = {"category": "boundary", "type": "administrative", "geojson": {"type": "Polygon", "coordinates": []}, "extratags": {"admin_level": "6"}}
    assert is_boundary_candidate(item)
    assert candidate_kind(item) == "administrative_boundary"


def test_settlement_polygon_is_not_mistaken_for_admin_boundary():
    item = {"category": "place", "type": "town", "geojson": {"type": "MultiPolygon", "coordinates": []}, "extratags": {}}
    assert not is_boundary_candidate(item)
    assert candidate_kind(item) == "settlement_polygon_candidate"


def test_rejects_place_point():
    item = {"category": "place", "type": "town", "geojson": {"type": "Point", "coordinates": [58.98, 53.42]}, "extratags": {}}
    assert candidate_kind(item) is None
