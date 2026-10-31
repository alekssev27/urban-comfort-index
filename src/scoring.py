"""Scoring utilities for the urban comfort prototype."""
import math
import pandas as pd

CRITERIA = {
    "transport": "Транспорт",
    "education": "Образование",
    "medical": "Медицина",
    "green": "Зелёные зоны",
    "daily": "Повседневная инфраструктура",
    "leisure": "Досуг",
}

PROFILE_WEIGHTS = {
    "student": {"transport": 25, "education": 25, "medical": 10, "green": 10, "daily": 20, "leisure": 10},
    "couple": {"transport": 20, "education": 5, "medical": 10, "green": 20, "daily": 20, "leisure": 25},
    "family": {"transport": 15, "education": 25, "medical": 20, "green": 20, "daily": 10, "leisure": 10},
}


def distance_score(distance_m, threshold_m):
    """Convert distance to a provisional linear 0-100 score."""
    if threshold_m <= 0 or not math.isfinite(float(threshold_m)):
        raise ValueError("threshold_m должен быть конечным и больше нуля.")
    if pd.isna(distance_m):
        return float("nan")
    return max(0.0, min(100.0, 100.0 * (1.0 - float(distance_m) / float(threshold_m))))


def calculate_index(row, weights):
    """Weighted score; missing criteria are excluded and remaining weights renormalized."""
    available = [(key, weights[key]) for key in CRITERIA if key in weights and key in row and weights[key] > 0 and pd.notna(row[key])]
    total_weight = sum(weight for _, weight in available)
    if total_weight == 0:
        return float("nan")
    return sum(float(row[key]) * weight for key, weight in available) / total_weight
