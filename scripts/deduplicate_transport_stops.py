"""Create a deduplicated physical-stop layer from the raw OSM infrastructure GeoJSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.transport import deduplicate_transport_features

ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data/raw/infrastructure_osm.geojson"
OUTPUT_PATH = ROOT / "data/processed/transport_stops_deduplicated.geojson"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--radius-m", type=float, default=25.0)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Не найден исходный файл: {args.input}")

    source = json.loads(args.input.read_text(encoding="utf-8"))
    features = source.get("features", [])
    stops = deduplicate_transport_features(features, merge_radius_m=args.radius_m)

    output = {
        "type": "FeatureCollection",
        "name": "magnitogorsk_deduplicated_transport_stops",
        "metadata": {
            "source_file": str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input),
            "deduplication_radius_m": args.radius_m,
            "method": "complete-link Euclidean clustering in EPSG:32640",
            "note": (
                "Nearby OSM stop elements are grouped as candidate physical stops. "
                "Groups should be visually reviewed; OSM mode tags may be incomplete."
            ),
            "license": "OpenStreetMap data, ODbL 1.0",
        },
        "features": stops,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Исходных транспортных элементов: {sum(f.get('properties', {}).get('category') == 'transport' for f in features)}")
    print(f"Групп физических остановок-кандидатов: {len(stops)}")
    print(f"Сохранено: {args.output}")


if __name__ == "__main__":
    main()
