import pytest

from src.scoring import calculate_comfort_index


def test_calculate_comfort_index():
    scores = {"transport": 80, "parks": 60}
    weights = {"transport": 0.75, "parks": 0.25}

    assert calculate_comfort_index(scores, weights) == pytest.approx(75)


def test_rejects_negative_weights():
    with pytest.raises(ValueError):
        calculate_comfort_index(
            {"transport": 80},
            {"transport": -1},
        )


def test_rejects_mismatched_criteria():
    with pytest.raises(ValueError):
        calculate_comfort_index(
            {"transport": 80},
            {"parks": 1},
        )
