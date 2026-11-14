import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
from src.data_loader import CRITERIA
from src.map_data import prepare_scores, build_cell_clusters
from src.scoring import calculate_index


def test_vector_scores_match_scalar_with_missing_observations():
    frame = pd.DataFrame({f"score_{key}": [50, None, i * 10] for i, key in enumerate(CRITERIA)})
    frame.loc[0, 'score_transport'] = None
    for weights in ({key: i * 5 for i, key in enumerate(CRITERIA)}, {key: 0 for key in CRITERIA}):
        expected = frame.rename(columns={f'score_{key}': key for key in CRITERIA}).apply(lambda row: calculate_index(row, weights), axis=1)
        actual = prepare_scores(frame, weights)['comfort_index']
        pd.testing.assert_series_equal(actual, expected.sort_values(ascending=False).reset_index(drop=True), check_names=False)


def test_clusters_respect_limit_and_preserve_every_cell():
    frame = gpd.GeoDataFrame({'cell_id': list(range(25)), 'comfort_index': [50.] * 25}, geometry=[box(x*250,y*250,(x+1)*250,(y+1)*250) for x in range(5) for y in range(5)], crs=32640)
    for key in CRITERIA:
        frame[f'score_{key}'] = 50.
        frame[f'nearest_distance_{key}_m'] = 100.
    result = build_cell_clusters(frame)
    assert result.cell_count.max() <= 8
    assert sorted(cell for ids in result.cell_ids for cell in ids) == sorted(str(i) for i in range(25))
    assert build_cell_clusters(frame.iloc[:0]).empty
