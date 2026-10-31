"""Загрузка реальных оценок и геометрии ячеек городской сетки."""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GRID_PATH = DATA_DIR / "processed" / "grid_cells.geojson"
SCORES_PATH = DATA_DIR / "processed" / "residential_comfort_scores.csv"

CRITERIA = {
    "transport": "Транспорт",
    "education": "Образование",
    "medical": "Медицина",
    "green": "Зелёные зоны",
    "daily": "Повседневная инфраструктура",
    "leisure": "Досуг",
}


@st.cache_data(show_spinner=False, ttl=3600)
def load_real_scores(
    grid_path: Path = GRID_PATH,
    scores_path: Path = SCORES_PATH,
) -> gpd.GeoDataFrame:
    """Объединить геометрию сетки с оценками жилых ячеек."""
    if not grid_path.exists():
        raise FileNotFoundError(f"Не найден файл сетки: {grid_path}")
    if not scores_path.exists():
        raise FileNotFoundError(f"Не найден файл оценок: {scores_path}")

    grid = gpd.read_file(grid_path)
    scores = pd.read_csv(scores_path, encoding="utf-8-sig")

    for frame, name in ((grid, "GeoJSON сетки"), (scores, "CSV оценок")):
        if "cell_id" not in frame.columns:
            raise ValueError(f"В {name} отсутствует столбец cell_id.")

    score_columns = [f"score_{key}" for key in CRITERIA]
    distance_columns = [f"nearest_distance_{key}_m" for key in CRITERIA]
    index_columns = [
        "comfort_index_student",
        "comfort_index_couple",
        "comfort_index_family",
    ]
    required = score_columns + distance_columns + index_columns
    missing = [column for column in required if column not in scores.columns]
    if missing:
        raise ValueError("В CSV отсутствуют столбцы: " + ", ".join(missing))
    if grid.crs is None:
        raise ValueError("У GeoJSON сетки не указана система координат.")

    scores = scores.drop_duplicates(subset=["cell_id"])
    merged = grid.merge(scores, on="cell_id", how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Не удалось сопоставить ячейки по cell_id.")

    for column in required:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    return merged.to_crs("EPSG:4326")
