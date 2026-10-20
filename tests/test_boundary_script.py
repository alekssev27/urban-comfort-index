from scripts.fetch_osm_boundary import is_boundary_candidate


def test_accepts_jsonv2_administrative_polygon():
    item = {"category": "boundary", "type": "administrative", "geojson": {"type": "Polygon", "coordinates": []}, "extratags": {"admin_level": "8"}}
    assert is_boundary_candidate(item)


def test_rejects_place_point():
    item = {"category": "place", "type": "city", "geojson": {"type": "Point", "coordinates": [58.98, 53.42]}, "extratags": {}}
    assert not is_boundary_candidate(item)


def test_rejects_polygon_without_admin_level():
    item = {"category": "boundary", "type": "administrative", "geojson": {"type": "Polygon", "coordinates": []}, "extratags": {}}
    assert not is_boundary_candidate(item)
