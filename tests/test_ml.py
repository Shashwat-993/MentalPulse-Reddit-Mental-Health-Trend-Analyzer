"""Tests for the Phase 2 scorers — pure logic, no model download, no MLflow.

The transformer itself is exercised by the real scoring run (and its MLflow
record); here we pin the surrounding logic: score mapping, checkpoint-style
merging into Gold, weak labels, feature engineering, and the transparent
classifier's plumbing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml import crisis
from ml.sentiment import LABELS, apply_scores_to_gold, score_frame


# --- sentiment: score_frame with a fake scorer --------------------------------


class FakeScorer:
    """Deterministic stand-in: 'good' → positive, 'bad' → negative, else neutral."""

    batch_size = 4

    def score_texts(self, texts):
        rows = []
        for t in texts:
            if "good" in t:
                rows.append([0.05, 0.15, 0.80])
            elif "bad" in t:
                rows.append([0.80, 0.15, 0.05])
            else:
                rows.append([0.10, 0.80, 0.10])
        return np.array(rows)


def _posts(texts):
    return pd.DataFrame({"post_id": [f"p{i}" for i in range(len(texts))], "text": texts})


def test_score_frame_maps_probs_to_score_and_label():
    frame = score_frame(_posts(["good day", "bad day", "a day"]), FakeScorer())
    by_id = frame.set_index("post_id")
    assert by_id.loc["p0", "sentiment_score"] == pytest.approx(0.75)
    assert by_id.loc["p1", "sentiment_score"] == pytest.approx(-0.75)
    assert by_id.loc["p2", "sentiment_score"] == pytest.approx(0.0)
    assert list(by_id["sentiment_label"]) == ["positive", "negative", "neutral"]
    assert set(frame["sentiment_label"]).issubset(set(LABELS))


def test_score_frame_restores_input_order_despite_length_sorting():
    # Long positive text first, short negative second: length-sorted scoring
    # processes them in reverse — results must still align to post_id.
    texts = ["good " * 200, "bad"]
    frame = score_frame(_posts(texts), FakeScorer())
    assert frame.loc[0, "sentiment_score"] > 0
    assert frame.loc[1, "sentiment_score"] < 0


def _gold(n=3):
    return pd.DataFrame(
        {
            "post_id": [f"p{i}" for i in range(n)],
            "subreddit": "anxiety",
            "week": pd.Timestamp("2019-01-07"),
            "n_words": 5,
            "sentiment_score": pd.array([None] * n, dtype="Float64"),
            "sentiment_label": pd.array([None] * n, dtype="string"),
            "crisis_score": pd.array([None] * n, dtype="Float64"),
            "crisis_flag": pd.array([None] * n, dtype="boolean"),
        }
    )


def test_apply_scores_preserves_schema_and_unscored_rows():
    scores = pd.DataFrame(
        {
            "post_id": ["p0"],
            "sentiment_score": [0.5],
            "sentiment_label": pd.array(["positive"], dtype="string"),
        }
    )
    out = apply_scores_to_gold(_gold(), scores)
    assert list(out.columns) == list(_gold().columns)
    assert out.set_index("post_id").loc["p0", "sentiment_score"] == 0.5
    assert pd.isna(out.set_index("post_id").loc["p2", "sentiment_score"])


# --- crisis: weak labels -------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("i want to die, nothing helps", 1),                  # one acute phrase
        ("everything feels hopeless and unbearable lately", 1),  # two severe terms
        ("feeling hopeless today", 0),                        # one severe term only
        ("rough week at work but managing", 0),
        ("", 0),
    ],
)
def test_weak_labels(text, expected):
    assert crisis.weak_labels(pd.Series([text])).iloc[0] == expected


def test_weak_labels_handle_missing():
    assert crisis.weak_labels(pd.Series([None])).iloc[0] == 0


# --- crisis: features ------------------------------------------------------------


def _silver(texts):
    return pd.DataFrame({"post_id": [f"p{i}" for i in range(len(texts))], "text": texts})


def test_build_features_shape_and_acute_exclusion():
    silver = _silver(["i feel hopeless and worthless", "nice walk outside today"])
    gold = _gold(2)
    gold["sentiment_score"] = pd.array([-0.8, 0.6], dtype="Float64")
    feats = crisis.build_features(silver, gold)
    assert list(feats.columns) == ["post_id"] + crisis.FEATURE_COLUMNS
    # the acute tier must not leak into features (that's the label's job)
    assert not any("acute" in c for c in crisis.FEATURE_COLUMNS)
    assert feats.loc[0, "severe_density"] > 0
    assert feats.loc[1, "severe_density"] == 0
    assert feats.loc[0, "sentiment_score"] == pytest.approx(-0.8)


def test_build_features_requires_sentiment():
    with pytest.raises(RuntimeError, match="ml.sentiment"):
        crisis.build_features(_silver(["hi"]), _gold(1))


# --- crisis: training ----------------------------------------------------------


def test_train_and_score_end_to_end():
    rng = np.random.default_rng(0)
    n = 400
    # Synthetic corpus: distressed posts have high severe density + negative
    # sentiment; the classifier should separate them nearly perfectly.
    distressed = rng.random(n) < 0.25
    feats = pd.DataFrame(
        {
            "post_id": [f"p{i}" for i in range(n)],
            "severe_density": np.where(distressed, 4.0, 0.2) + rng.normal(0, 0.1, n),
            "first_person_density": rng.normal(10, 2, n),
            "negation_density": rng.normal(3, 1, n),
            "sentiment_score": np.where(distressed, -0.8, 0.1) + rng.normal(0, 0.1, n),
            "log_n_words": rng.normal(4, 1, n),
        }
    )
    labels = pd.Series(distressed.astype("int64"))
    scores, report = crisis.train_and_score(feats, labels, threshold=0.5)

    assert len(scores) == n
    assert scores["crisis_score"].between(0, 1).all()
    assert report["holdout_auc"] > 0.95
    assert set(report["coefficients"]) == set(crisis.FEATURE_COLUMNS)
    # severe density and negative sentiment should dominate, in that direction
    assert report["coefficients"]["severe_density"] > 0
    assert report["coefficients"]["sentiment_score"] < 0
    # flags follow the threshold
    assert (scores["crisis_flag"] == (scores["crisis_score"] >= 0.5)).all()
