"""Объединение оценок инфраструктуры и расчёт профильных индексов."""
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping

import pandas as pd

from src.scoring import CRITERIA, PROFILE_WEIGHTS, calculate_index

CRITERION_FILES = {
    "transport": "transport_accessibility.csv",
    "education": "education_accessibility.csv",
    "medical": "medical_accessibility.csv",
    "green": "green_accessibility.csv",
    "daily": "daily_accessibility.csv",
    "leisure": "leisure_accessibility.csv",
}


def build_accessibility_dataset(
    grid: pd.DataFrame,
    criterion_frames: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Объединить шесть таблиц по cell_id и добавить три профильных индекса.

    Состав ячеек должен совпадать с сеткой. Дубликаты и неизвестные cell_id
    считаются ошибкой, а пропуски отдельных оценок допустимы: calculate_index
    перенормирует веса по доступным критериям.
    """
    if "cell_id" not in grid.columns:
        raise ValueError("В сетке отсутствует столбец cell_id.")
    if grid["cell_id"].duplicated().any():
        raise ValueError("В сетке обнаружены повторяющиеся cell_id.")

    expected_keys = set(CRITERIA)
    supplied_keys = set(criterion_frames)
    if supplied_keys != expected_keys:
        missing = sorted(expected_keys - supplied_keys)
        extra = sorted(supplied_keys - expected_keys)
        details = []
        if missing:
            details.append("не хватает: " + ", ".join(missing))
        if extra:
            details.append("лишние: " + ", ".join(extra))
        raise ValueError("Неверный набор критериев (" + "; ".join(details) + ").")

    grid_ids = set(grid["cell_id"].astype(str))
    result = pd.DataFrame({"cell_id": grid["cell_id"].astype(str)})

    for criterion in CRITERIA:
        frame = criterion_frames[criterion].copy()
        if "cell_id" not in frame.columns:
            raise ValueError(f"В таблице {criterion} отсутствует cell_id.")
        if frame["cell_id"].duplicated().any():
            raise ValueError(f"В таблице {criterion} обнаружены повторяющиеся cell_id.")

        source_ids = set(frame["cell_id"].astype(str))
        missing_ids = grid_ids - source_ids
        extra_ids = source_ids - grid_ids
        if missing_ids or extra_ids:
            raise ValueError(
                f"Набор ячеек в {criterion} не совпадает с сеткой: "
                f"отсутствует {len(missing_ids)}, лишних {len(extra_ids)}."
            )

        frame["cell_id"] = frame["cell_id"].astype(str)
        required_columns = [
            f"score_{criterion}",
            f"nearest_distance_{criterion}_m",
        ]
        absent = [column for column in required_columns if column not in frame.columns]
        if absent:
            raise ValueError(
                f"В таблице {criterion} отсутствуют столбцы: "
                + ", ".join(absent)
            )

        new_columns = [column for column in frame.columns if column != "cell_id"]
        collisions = sorted(set(new_columns) & set(result.columns))
        if collisions:
            raise ValueError(
                f"Повторяющиеся столбцы при объединении {criterion}: "
                + ", ".join(collisions)
            )
        result = result.merge(
            frame[["cell_id", *new_columns]],
            on="cell_id",
            how="left",
            validate="one_to_one",
            sort=False,
        )

    for key in CRITERIA:
        result[f"score_{key}"] = pd.to_numeric(
            result[f"score_{key}"], errors="coerce"
        )
        result[f"nearest_distance_{key}_m"] = pd.to_numeric(
            result[f"nearest_distance_{key}_m"], errors="coerce"
        )

    for profile, weights in PROFILE_WEIGHTS.items():
        result[f"comfort_index_{profile}"] = result.apply(
            lambda row: calculate_index(
                {key: row[f"score_{key}"] for key in CRITERIA},
                weights,
            ),
            axis=1,
        )

    return result
