"""Create an HTML preview of the candidate boundary for manual inspection."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import folium
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "city_boundary.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "boundary_preview.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Не найден файл: {args.input}")
    frame = gpd.read_file(args.input)
    if frame.empty or frame.crs is None:
        raise SystemExit("Файл пуст или у геометрии не задана CRS.")
    frame = frame.to_crs("EPSG:4326")
    if not frame.geometry.is_valid.all():
        raise SystemExit("В контуре есть невалидная геометрия. Исправьте/проверьте её до построения сетки.")
    minx, miny, maxx, maxy = frame.total_bounds
    center = [(miny + maxy) / 2, (minx + maxx) / 2]
    props = frame.iloc[0].drop(labels=[frame.geometry.name], errors="ignore").to_dict()
    map_view = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    folium.GeoJson(
        data=json.loads(frame.to_json()),
        name="Candidate settlement boundary",
        style_function=lambda _: {"color": "#dc2626", "weight": 3, "fillColor": "#fca5a5", "fillOpacity": 0.15},
        tooltip=folium.GeoJsonTooltip(fields=[col for col in frame.columns if col != frame.geometry.name][:3]),
    ).add_to(map_view)
    folium.LayerControl().add_to(map_view)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(str(args.output))
    print(f"Кандидат: {props.get('display_name', props.get('name', 'без названия'))}")
    print(f"OSM ID: {props.get('osm_id')} | kind: {props.get('candidate_kind')} | status: {props.get('status')}")
    print(f"WGS84 bbox: west={minx:.6f}, south={miny:.6f}, east={maxx:.6f}, north={maxy:.6f}")
    print(f"Геометрия: {frame.geometry.iloc[0].geom_type}; площадь в градусах² не интерпретировать как км².")
    print(f"Открой в браузере и визуально проверь контур: {args.output}")

if __name__ == "__main__":
    main()
