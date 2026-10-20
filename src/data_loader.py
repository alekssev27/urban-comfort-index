from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEMO_SCORES_PATH = DATA_DIR / "demo_scores.csv"

REQUIRED_SCORE_COLUMNS = [
    "name",
    "lat",
    "lon",
    "transport",
    "education",
    "medical",
    "green",
    "daily",
    "leisure",
]


def load_demo_scores() -> pd.DataFrame:
    """Load the synthetic territory scores used by the current prototype."""
    if not DEMO_SCORES_PATH.exists():
        raise FileNotFoundError(
            f"Не найден файл демонстрационных данных: {DEMO_SCORES_PATH}"
        )

    data = pd.read_csv(DEMO_SCORES_PATH, encoding="utf-8-sig")

    missing = [column for column in REQUIRED_SCORE_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(
            "В data/demo_scores.csv отсутствуют обязательные столбцы: "
            + ", ".join(missing)
        )

    if data.empty:
        raise ValueError("Файл data/demo_scores.csv не содержит строк.")

    numeric_columns = [
        "lat", "lon", "transport", "education", "medical",
        "green", "daily", "leisure",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="raise")

    score_columns = [
        "transport", "education", "medical", "green", "daily", "leisure"
    ]
    for column in score_columns:
        if not data[column].between(0, 100).all():
            raise ValueError(
                f"Значения в столбце {column} должны быть в диапазоне от 0 до 100."
            )

    return data
