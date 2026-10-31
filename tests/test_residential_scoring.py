import pandas as pd
import pytest

from scripts.score_residential_cells import score_residential_cells
from src.scoring import distance_score


def test_distance_score_linear_scale():
    assert distance_score(0, 1000) == 100
    assert distance_score(250, 1000) == 75
    assert distance_score(1000, 1000) == 0
    assert distance_score(1500, 1000) == 0


def test_p90_thresholds_fit_only_residential_cells():
    rows = []
    for i, distance in enumerate([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]):
        row = {"cell_id": f"r{i}", "has_residential_building": True}
        for category in ("transport", "education", "medical", "green", "daily", "leisure"):
            row[f"nearest_distance_{category}_m"] = distance
        rows.append(row)
    non_residential = {"cell_id": "nonres", "has_residential_building": False}
    for category in ("transport", "education", "medical", "green", "daily", "leisure"):
        non_residential[f"nearest_distance_{category}_m"] = 100000
    rows.append(non_residential)

    scores, thresholds = score_residential_cells(pd.DataFrame(rows))
    assert len(scores) == 10
    assert "nonres" not in set(scores["cell_id"])
    assert thresholds.iloc[0]["threshold_m"] == pytest.approx(910)
    assert scores["score_transport"].max() <= 100
    assert scores["score_transport"].min() >= 0
    assert scores["comfort_index_student"].notna().all()


def test_requires_residential_cells():
    data = pd.DataFrame({"cell_id": ["a"], "has_residential_building": [False]})
    with pytest.raises(ValueError, match="жилыми зданиями"):
        score_residential_cells(data)
