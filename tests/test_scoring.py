import pytest
from src.scoring import CRITERIA, calculate_index


def test_calculate_weighted_index():
    scores = {"transport": 80, "education": 60, "medical": 70, "green": 50, "daily": 90, "leisure": 40}
    weights = {"transport": 3, "education": 1, "medical": 0, "green": 0, "daily": 0, "leisure": 0}
    assert calculate_index(scores, weights) == pytest.approx(80)


def test_zero_weights_return_zero():
    scores = {key: 50 for key in CRITERIA}
    assert calculate_index(scores, {key: 0 for key in CRITERIA}) == 0.0


def test_current_criteria_are_used():
    assert set(CRITERIA) == {"transport", "education", "medical", "green", "daily", "leisure"}


def test_scores_are_weighted_by_weight_sum():
    scores = {key: 50 for key in CRITERIA}
    weights = {key: 1 for key in CRITERIA}
    scores["transport"] = 100
    assert calculate_index(scores, weights) == pytest.approx(350 / 6)
