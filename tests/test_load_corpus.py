"""Tests for corpus file selection and CSV -> Bronze parsing (no network)."""
from __future__ import annotations

import pandas as pd
import pytest

from ingestion.corpus import CorpusFile, select_files
from ingestion.load_corpus import derive_post_id, parse_corpus_csv


def _catalog() -> list[CorpusFile]:
    keys = [
        "anxiety_pre_features_tfidf_256.csv",
        "anxiety_post_features_tfidf_256.csv",
        "depression_post_features_tfidf_256.csv",
    ]
    return [
        CorpusFile(key=k, url=f"https://zenodo.example/{k}", size=1, md5="0" * 32)
        for k in keys
    ]


def test_select_files_picks_requested_pairs():
    picked = select_files(_catalog(), ["anxiety"], ["pre", "post"])
    assert [f.key.split("_")[1] for f in picked] == ["pre", "post"]
    assert all(f.subreddit == "anxiety" for f in picked)


def test_select_files_fails_loudly_on_missing_combo():
    with pytest.raises(ValueError, match="depression"):
        select_files(_catalog(), ["depression"], ["pre", "post"])


def test_parse_corpus_csv(tmp_path):
    csv = tmp_path / "anxiety_pre_features_tfidf_256.csv"
    pd.DataFrame(
        {
            "subreddit": ["anxiety", "anxiety"],
            "author": ["jane_doe", "john_roe"],
            "date": ["2019/01/07", "2019/01/08"],
            "post": ["first post", "second post"],
            # stand-ins for the ~346 precomputed feature columns
            "flesch_reading_ease": [1.0, 2.0],
            "tfidf_anxious": [0.1, 0.2],
        }
    ).to_csv(csv, index=False)

    frame = parse_corpus_csv(csv, period="pre")

    assert list(frame.columns) == [
        "post_id",
        "subreddit",
        "author",
        "created_date",
        "post",
        "period",
        "source_file",
        "ingested_at",
    ]
    # feature columns are not landed in Bronze
    assert "tfidf_anxious" not in frame.columns
    assert (frame["period"] == "pre").all()
    assert (frame["source_file"] == csv.name).all()
    # post_id is deterministic and content-derived
    assert frame.loc[0, "post_id"] == derive_post_id(
        "anxiety", "jane_doe", "2019/01/07", "first post"
    )
    assert frame["post_id"].is_unique


def test_derive_post_id_is_stable_and_distinct():
    a = derive_post_id("anxiety", "jane", "2019/01/07", "hello")
    assert a == derive_post_id("anxiety", "jane", "2019/01/07", "hello")
    assert a != derive_post_id("anxiety", "jane", "2019/01/07", "hello!")
    assert len(a) == 16


def test_derive_post_id_missing_values_hash_as_empty():
    """Missing fields hash as '' — the same convention as the Spark ingest's
    coalesce(col, ''), so both Bronze loaders derive identical ids."""
    import hashlib

    for missing in (None, float("nan"), pd.NA):
        assert derive_post_id("anxiety", missing, "2019/01/07", "hello") == (
            hashlib.sha1(b"anxiety||2019/01/07|hello").hexdigest()[:16]
        )
