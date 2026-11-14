"""Подготовка оценок и пространственных групп без зависимости от интерфейса."""
from pathlib import Path
import geopandas as gpd
import pandas as pd
from src.data_loader import CRITERIA

def prepare_scores(raw_data, weights):
    """Подготовить оценки критериев и рассчитать индекс с текущими весами."""
    data = raw_data.copy()
    for key in CRITERIA:
        data[key] = data[f"score_{key}"]
    positive_weights = pd.Series({key: max(0, weights.get(key, 0)) for key in CRITERIA})
    values = data[list(CRITERIA)]
    denominator = values.notna().mul(positive_weights).sum(axis=1)
    data["comfort_index"] = (
        values.mul(positive_weights).sum(axis=1) / denominator.replace(0, float("nan"))
        if positive_weights.sum() else 0.0
    )
    return data.sort_values("comfort_index", ascending=False).reset_index(drop=True)


def score_color(value, color_map):
    if pd.isna(value):
        return "#9ca3af"
    return color_map(float(value))


def load_street_segments(streets_signature=None):
    """Загрузить локальный слой улиц, подготовленный отдельным OSM-скриптом."""
    path = Path("data/raw/streets_osm.geojson")
    if not path.exists():
        return None
    try:
        streets = gpd.read_file(path)
        if streets.crs is None:
            streets = streets.set_crs("EPSG:4326")
        return streets.to_crs("EPSG:32640")
    except Exception:
        return None


def assign_cluster_street_names(clusters, streets):
    """Назначить территории название любой подходящей улицы из OSM."""
    if clusters.empty:
        return clusters

    named_streets = (
        streets[
            streets["name"].notna()
            & streets["name"].astype(str).str.strip().ne("")
        ].copy()
        if streets is not None and not streets.empty and "name" in streets.columns
        else None
    )

    footprints = gpd.GeoSeries(clusters["footprint"], crs="EPSG:4326").to_crs("EPSG:32640")
    street_index = named_streets.sindex if named_streets is not None and not named_streets.empty else None
    display_names = []
    for footprint in footprints:
        display_name = "Улица не определена по OSM"

        if named_streets is not None and not named_streets.empty:
            positions = street_index.query(footprint, predicate="intersects")
            candidates = named_streets.iloc[sorted(positions)]

            if not candidates.empty:
                display_name = str(candidates.iloc[0]["name"]).strip()
            else:
                # Если внутри контура улиц нет, показываем ближайшую как ориентир.
                positions = street_index.nearest(footprint, return_all=True)[1]
                nearest_name = str(named_streets.iloc[min(positions)]["name"]).strip()
                display_name = f"Рядом с улицей {nearest_name}"

        display_names.append(display_name)

    result = clusters.copy()
    result["display_name"] = display_names
    return result

def build_cell_clusters(frame, max_score_gap=10.0, max_cells=8):
    """Объединить соседние ячейки с ограничением диапазона оценок и размера группы."""
    projected = frame.to_crs("EPSG:32640").reset_index(drop=True)
    geometries = projected.geometry
    scores = projected["comfort_index"].astype(float).tolist()
    spatial_index = projected.sindex
    visited = set()
    clusters = []

    for seed in sorted(range(len(projected)), key=lambda i: scores[i], reverse=True):
        if seed in visited or pd.isna(scores[seed]):
            continue

        members = [seed]
        visited.add(seed)
        pending = [seed]
        min_score = max_score = scores[seed]

        while pending and len(members) < max_cells:
            current = pending.pop()
            try:
                candidates = spatial_index.query(
                    geometries.iloc[current], predicate="touches"
                )
            except TypeError:
                candidates = spatial_index.intersection(
                    geometries.iloc[current].bounds
                )

            for candidate in candidates:
                if len(members) >= max_cells:
                    break
                candidate = int(candidate)
                if candidate in visited or pd.isna(scores[candidate]):
                    continue
                if not geometries.iloc[current].touches(geometries.iloc[candidate]):
                    continue

                proposed_min = min(min_score, scores[candidate])
                proposed_max = max(max_score, scores[candidate])
                if proposed_max - proposed_min <= max_score_gap:
                    visited.add(candidate)
                    members.append(candidate)
                    pending.append(candidate)
                    min_score, max_score = proposed_min, proposed_max

        group = projected.iloc[members].copy()
        footprint_projected = group.geometry.unary_union
        footprint = gpd.GeoSeries(
            [footprint_projected], crs=projected.crs
        ).to_crs("EPSG:4326").iloc[0]
        center = footprint.centroid
        clusters.append({
            "cluster_id": len(clusters),
            "cell_ids": group["cell_id"].astype(str).tolist(),
            "representative_cell": group.loc[group["comfort_index"].idxmax(), "cell_id"],
            "cell_count": len(group),
            "comfort_index": float(group["comfort_index"].mean()),
            "score_min": float(group["comfort_index"].min()),
            "score_max": float(group["comfort_index"].max()),
            "geometry": center,
            "footprint": footprint,
            **{
                f"score_{key}": group[f"score_{key}"].mean()
                for key in CRITERIA
            },
            **{
                f"nearest_distance_{key}_m": group[f"nearest_distance_{key}_m"].mean()
                for key in CRITERIA
            },
        })

    return pd.DataFrame(clusters)
