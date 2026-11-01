"""Summarize deduplicated OSM transport stops and inspect their spatial grouping."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/transport_stops_deduplicated.geojson"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--show-large", type=int, default=4,
                        help="Показывать группы с таким числом элементов и более.")
    args = parser.parse_args()
    if args.show_large < 2:
        parser.error("--show-large должен быть не меньше 2.")
    if not args.input.exists():
        raise SystemExit(f"Не найден файл: {args.input}")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    features = data.get("features", [])
    sizes = Counter()
    modes = Counter()
    empty_modes = 0
    unnamed_groups = 0
    large_groups = []
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32640", always_xy=True)

    for feature in features:
        props = feature.get("properties") or {}
        members = props.get("member_osm_objects") or []
        size = len(members)
        sizes[size] += 1
        group_modes = props.get("transport_modes") or []
        if group_modes:
            modes.update(group_modes)
        else:
            empty_modes += 1
        if not props.get("name"):
            unnamed_groups += 1

        member_points = []
        for member in members:
            lon, lat = member.get("longitude"), member.get("latitude")
            if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                x, y = transformer.transform(lon, lat)
                member_points.append((member, Point(x, y)))

        pair_distances = []
        for i, (left_member, left_point) in enumerate(member_points):
            for right_member, right_point in member_points[i + 1:]:
                pair_distances.append(
                    (left_member, right_member, left_point.distance(right_point))
                )
        max_pair_distance = max((item[2] for item in pair_distances), default=0.0)

        if size >= args.show_large:
            large_groups.append({
                "group_id": props.get("stop_group_id"),
                "member_count": size,
                "name": props.get("name"),
                "members": members,
                "transport_modes": group_modes,
                "pair_distances": pair_distances,
                "max_pair_distance": max_pair_distance,
            })

    total_members = sum(size * count for size, count in sizes.items())
    merged_groups = sum(count for size, count in sizes.items() if size > 1)
    singleton_groups = sizes.get(1, 0)

    print(f"Групп физических остановок-кандидатов: {len(features)}")
    print(f"Исходных OSM-элементов в группах: {total_members}")
    print(f"Одиночные группы: {singleton_groups}")
    print(f"Группы из нескольких элементов: {merged_groups}")
    print(f"Групп без определённых транспортных режимов: {empty_modes}")
    print(f"Групп без названия: {unnamed_groups}")

    print("\nРаспределение по размеру группы:")
    for size, count in sorted(sizes.items()):
        print(f"  {size} элемент(а): {count} групп")

    print("\nРаспределение транспортных режимов (группы могут иметь несколько режимов):")
    if modes:
        for mode, count in sorted(modes.items()):
            print(f"  {mode}: {count}")
    else:
        print("  Транспортные режимы не определены ни для одной группы.")

    if large_groups:
        print(f"\nГруппы с {args.show_large}+ элементами — пространственная диагностика:")
        for group in sorted(large_groups, key=lambda item: (-item["member_count"], str(item["group_id"]))):
            print(
                f"  {group['group_id']}: {group['member_count']} элементов; "
                f"name={group['name']!r}; modes={group['transport_modes']}"
            )
            for member in group["members"]:
                print(
                    f"    - {member.get('osm_type')}/{member.get('osm_id')}: "
                    f"name={member.get('name')!r}, "
                    f"public_transport={member.get('public_transport')!r}, "
                    f"highway={member.get('highway')!r}, "
                    f"lon={member.get('longitude')}, lat={member.get('latitude')}"
                )
            print(f"    Максимальное расстояние между элементами: {group['max_pair_distance']:.1f} м")
            for left, right, distance in sorted(
                group["pair_distances"], key=lambda item: item[2], reverse=True
            ):
                print(
                    f"      {left.get('osm_type')}/{left.get('osm_id')} — "
                    f"{right.get('osm_type')}/{right.get('osm_id')}: {distance:.1f} м"
                )


if __name__ == "__main__":
    main()
