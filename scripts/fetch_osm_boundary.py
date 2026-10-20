"""Download a candidate Magnitogorsk boundary from Nominatim/OSM.

The result is a candidate dataset, not an official legal boundary. Review the
metadata and geometry before using it for research results.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "raw" / "city_boundary.geojson"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "urban-comfort-index-student-project/0.1 (boundary research)"


def fetch_candidates(query: str) -> list[dict]:
    response = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "polygon_geojson": 1,
                 "addressdetails": 1, "extratags": 1, "limit": 10,
                 "countrycodes": "ru"},
        headers={"User-Agent": USER_AGENT}, timeout=45,
    )
    response.raise_for_status()
    return response.json()


def is_boundary_candidate(item: dict) -> bool:
    """Accept only administrative polygon features with an admin_level tag."""
    geometry = item.get("geojson")
    if not geometry or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        return False
    extratags = item.get("extratags") or {}
    category = item.get("category", item.get("class"))  # JSONv2 calls this `category`.
    return category == "boundary" and item.get("type") == "administrative" and extratags.get("admin_level") is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="Магнитогорск, Челябинская область, Россия")
    parser.add_argument("--osm-id", type=int, help="Explicit OSM way/relation ID, if already verified")
    parser.add_argument("--osm-type", choices=["W", "R"], help="W=way, R=relation; required with --osm-id")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if bool(args.osm_id) != bool(args.osm_type):
        parser.error("--osm-id и --osm-type нужно указывать вместе")

    if args.osm_id:
        response = requests.get(
            "https://nominatim.openstreetmap.org/lookup",
            params={"osm_ids": f"{args.osm_type}{args.osm_id}", "format": "jsonv2",
                     "polygon_geojson": 1, "addressdetails": 1, "extratags": 1},
            headers={"User-Agent": USER_AGENT}, timeout=45,
        )
        response.raise_for_status()
        candidates = response.json()
    else:
        candidates = fetch_candidates(args.query)

    matches = [item for item in candidates if is_boundary_candidate(item)]
    if not matches:
        print("Не найден административный полигон-кандидат. Ничего не сохранено.")
        print("Проверьте кандидатов в Nominatim вручную или передайте проверенный OSM ID.")
        for item in candidates[:10]:
            category = item.get("category", item.get("class"))
            print(f"- {item.get('display_name')} | {category}/{item.get('type')} | OSM {item.get('osm_type')}:{item.get('osm_id')}")
        raise SystemExit(2)

    if len(matches) > 1 and not args.osm_id:
        print("Найдено несколько административных полигонов-кандидатов:")
        for index, item in enumerate(matches, start=1):
            tags = item.get("extratags") or {}
            print(f"{index}. {item.get('display_name')} | admin_level={tags.get('admin_level')} | OSM {item.get('osm_type')}:{item.get('osm_id')}")
        print("Проверьте нужный объект и повторите с --osm-id и --osm-type.")
        raise SystemExit(3)

    item = matches[0]
    geom = shape(item["geojson"])
    if geom.is_empty or not geom.is_valid:
        raise SystemExit("Геометрия пуста или невалидна; файл не сохранён.")
    props = {
        "name": item.get("name"), "display_name": item.get("display_name"),
        "source": "OpenStreetMap via Nominatim",
        "source_url": f"https://www.openstreetmap.org/{'relation' if item.get('osm_type') == 'relation' else 'way'}/{item.get('osm_id')}",
        "osm_type": item.get("osm_type"), "osm_id": item.get("osm_id"),
        "admin_level": (item.get("extratags") or {}).get("admin_level"),
        "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "license": "OpenStreetMap data, ODbL 1.0",
        "status": "candidate_boundary_requires_manual_review",
    }
    collection = {"type": "FeatureCollection", "name": "magnitogorsk_boundary_candidate",
                  "features": [{"type": "Feature", "properties": props, "geometry": item["geojson"]}]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Сохранено: {args.output}")
    print(f"Объект: {props['display_name']}")
    print(f"OSM: {props['osm_type']}:{props['osm_id']} | admin_level={props['admin_level']}")
    print("ВАЖНО: проверьте, что контур соответствует территории исследования, прежде чем строить сетку.")


if __name__ == "__main__":
    main()
