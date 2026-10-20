"""Find OSM administrative boundary candidates around Magnitogorsk.

This tool only lists candidate IDs. It does not decide which boundary is the
right study area; verify whether each candidate is the built-up city or a
larger municipal district before using it.
"""
from __future__ import annotations
import argparse
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "urban-comfort-index-student-project/0.1 (boundary research)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--south", type=float, default=53.20)
    parser.add_argument("--west", type=float, default=58.70)
    parser.add_argument("--north", type=float, default=53.70)
    parser.add_argument("--east", type=float, default=59.30)
    args = parser.parse_args()
    query = f'''[out:json][timeout:60];
(
  relation["boundary"="administrative"]["name"~"Магнитогорск"]({args.south},{args.west},{args.north},{args.east});
  way["boundary"="administrative"]["name"~"Магнитогорск"]({args.south},{args.west},{args.north},{args.east});
  relation["place"~"^(city|town)$"]["name"~"Магнитогорск"]({args.south},{args.west},{args.north},{args.east});
);
out tags center;'''
    response = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=90)
    response.raise_for_status()
    elements = response.json().get("elements", [])
    if not elements:
        print("Кандидаты не найдены в указанном bbox. Проверьте bbox или повторите позже.")
        return
    for element in elements:
        tags = element.get("tags", {})
        osm_type = "R" if element["type"] == "relation" else "W"
        print(f"{element['type']}:{element['id']} | name={tags.get('name')} | boundary={tags.get('boundary')} | place={tags.get('place')} | admin_level={tags.get('admin_level')} | type={tags.get('type')}")
        print(f"  https://www.openstreetmap.org/{'relation' if osm_type == 'R' else 'way'}/{element['id']}")
    print("\nНе выбирайте объект только по имени: place=town может быть точкой/местом, а муниципальная граница может охватывать территории вне городской застройки.")

if __name__ == "__main__":
    main()
