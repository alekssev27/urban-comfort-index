"""Audit OSM infrastructure categories, geometry types, tags and green-area sizes."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/raw/infrastructure_osm.geojson"
METRIC_CRS = "EPSG:32640"
TAG_KEYS = (
    "amenity",
    "shop",
    "leisure",
    "landuse",
    "public_transport",
    "highway",
    "railway",
    "healthcare",
)


def load_features(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Не найден файл: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        raise SystemExit("Ожидается GeoJSON FeatureCollection.")
    return data.get("features", [])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--top", type=int, default=12, help="Сколько значений каждого OSM-тега показывать.")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top должен быть положительным числом.")

    features = load_features(args.input)
    category_counts = Counter()
    geometry_counts = defaultdict(Counter)
    tag_counts = defaultdict(Counter)
    green_areas = defaultdict(list)
    transformer = Transformer.from_crs("EPSG:4326", METRIC_CRS, always_xy=True)

    invalid_geometry = 0
    for feature in features:
        props = feature.get("properties") or {}
        category = props.get("category") or "без категории"
        category_counts[category] += 1

        geometry_data = feature.get("geometry")
        if not geometry_data:
            invalid_geometry += 1
            continue
        try:
            geom = shape(geometry_data)
            if geom.is_empty:
                invalid_geometry += 1
                continue
            geometry_counts[category][geom.geom_type] += 1
            if category in {"green", "green_additional"} and geom.geom_type in {"Polygon", "MultiPolygon"}:
                metric_geom = transform(transformer.transform, geom)
                green_areas[category].append(metric_geom.area)
        except Exception:
            invalid_geometry += 1
            continue

        tags = props.get("tags") or {}
        for key in TAG_KEYS:
            value = tags.get(key)
            if value:
                tag_counts[key][str(value)] += 1

    print(f"Файл: {args.input}")
    print(f"Всего объектов: {len(features)}")
    print(f"Объектов с отсутствующей/ошибочной геометрией: {invalid_geometry}")

    print("\nОбъекты по категориям:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")

    print("\nТипы геометрии по категориям:")
    for category in sorted(geometry_counts):
        details = ", ".join(
            f"{geom_type}: {count}"
            for geom_type, count in sorted(geometry_counts[category].items())
        )
        print(f"  {category}: {details}")

    print("\nПлощадь зелёных полигонов (м², EPSG:32640):")
    for category in ("green", "green_additional"):
        areas = green_areas.get(category, [])
        if not areas:
            print(f"  {category}: полигоны не найдены")
            continue
        print(
            f"  {category}: {len(areas)} полигонов; "
            f"суммарная площадь={sum(areas):.0f}; "
            f"медианная площадь={sorted(areas)[len(areas) // 2]:.0f}; "
            f"максимальная площадь={max(areas):.0f}"
        )

    print("\nЧастые значения исходных OSM-тегов:")
    for key in TAG_KEYS:
        values = tag_counts.get(key)
        if not values:
            continue
        top_values = ", ".join(
            f"{value} ({count})" for value, count in values.most_common(args.top)
        )
        print(f"  {key}: {top_values}")


if __name__ == "__main__":
    main()
