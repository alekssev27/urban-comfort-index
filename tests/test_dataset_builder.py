import pandas as pd
import pytest

from src.dataset_builder import build_accessibility_dataset
from src.scoring import CRITERIA


def _frames(cell_ids):
    frames = {}
    for index, key in enumerate(CRITERIA):
        frames[key] = pd.DataFrame({
            "cell_id": cell_ids,
            f"score_{key}": [50 + index] * len(cell_ids),
            f"nearest_distance_{key}_m": [1000.0] * len(cell_ids),
        })
    return frames


def test_builds_three_profile_indices_and_preserves_grid_order():
    grid = pd.DataFrame({"cell_id": ["b", "a"]})
    result = build_accessibility_dataset(grid, _frames(["a", "b"]))

    assert result["cell_id"].tolist() == ["b", "a"]
    assert {
        "comfort_index_student",
        "comfort_index_couple",
        "comfort_index_family",
    }.issubset(result.columns)
    assert result.loc[0, "comfort_index_student"] == pytest.approx(52.5)


def test_missing_criterion_score_is_allowed_and_weights_are_renormalized():
    grid = pd.DataFrame({"cell_id": ["a"]})
    frames = _frames(["a"])
    frames["transport"].loc[0, "score_transport"] = float("nan")

    result = build_accessibility_dataset(grid, frames)

    assert pd.notna(result.loc[0, "comfort_index_student"])
    assert result.loc[0, "comfort_index_student"] == pytest.approx(
        (75 * 25 + 60 * 10 + 55 * 10 + 54 * 20 + 55 * 10) / 75
    )


def test_duplicate_cell_ids_are_rejected():
    grid = pd.DataFrame({"cell_id": ["a", "a"]})
    with pytest.raises(ValueError, match="повторяющиеся"):
        build_accessibility_dataset(grid, _frames(["a"]))


def test_mismatched_cell_sets_are_rejected():
    grid = pd.DataFrame({"cell_id": ["a", "b"]})
    frames = _frames(["a", "c"])
    with pytest.raises(ValueError, match="не совпадает с сеткой"):
        build_accessibility_dataset(grid, frames)


def test_missing_criterion_is_rejected():
    grid = pd.DataFrame({"cell_id": ["a"]})
    frames = _frames(["a"])
    frames.pop("leisure")
    with pytest.raises(ValueError, match="Неверный набор критериев"):
        build_accessibility_dataset(grid, frames)
