"""Tests for the anonymization module — the non-negotiable Phase 1 guardrail."""
from __future__ import annotations

import pandas as pd
import pytest

from ingestion.anonymize import (
    anonymize_frame,
    assert_anonymized,
    hash_author,
    scrub_text,
)

SALT = "test-salt-not-secret"


# --- hash_author ---------------------------------------------------------------


def test_hash_is_stable_and_pseudonymous():
    h1 = hash_author("some_redditor", salt=SALT)
    h2 = hash_author("some_redditor", salt=SALT)
    assert h1 == h2
    assert len(h1) == 64 and int(h1, 16) is not None  # sha256 hex
    assert "some_redditor" not in h1


def test_hash_differs_across_salts_and_authors():
    assert hash_author("a", salt=SALT) != hash_author("a", salt="other")
    assert hash_author("a", salt=SALT) != hash_author("b", salt=SALT)


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA, ""])
def test_hash_passes_missing_through(missing):
    assert hash_author(missing, salt=SALT) is None


def test_hash_rejects_empty_salt():
    with pytest.raises(ValueError, match="salt"):
        hash_author("someone", salt="")


# --- scrub_text ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,leaked",
    [
        ("mail me at jane.doe+reddit@example.co.uk please", "jane.doe"),
        ("see https://example.com/profile/jane for more", "example.com"),
        ("see www.example.com/jane too", "www.example"),
        ("thanks u/some_redditor for the advice", "some_redditor"),
        ("thanks /u/Some-Redditor!", "Some-Redditor"),
        ("ping @janedoe42 about it", "@janedoe42"),
        ("call me on +1 (555) 123-4567 tonight", "555"),
        ("call 555-123-4567", "555"),
    ],
)
def test_scrub_removes_pii(text, leaked):
    out = scrub_text(text)
    assert leaked not in out
    assert "[REDACTED:" in out


def test_scrub_preserves_ordinary_text():
    text = "I have been anxious for 3 weeks, maybe 10 days more than usual."
    assert scrub_text(text) == text


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA])
def test_scrub_passes_missing_through(missing):
    assert scrub_text(missing) is None


# --- anonymize_frame -------------------------------------------------------------


def _bronze_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "post_id": ["p1", "p2"],
            "author": ["jane_doe", "john_roe"],
            "author_fullname": ["t2_abc", "t2_def"],
            "post": ["email me a@b.com", "all fine here"],
        }
    )


def test_anonymize_frame_drops_and_hashes():
    out = anonymize_frame(_bronze_frame(), salt=SALT)
    assert "author" not in out.columns
    assert "author_fullname" not in out.columns
    assert out["author_hash"].notna().all()
    assert not set(out["author_hash"]) & {"jane_doe", "john_roe"}
    assert "a@b.com" not in out.loc[0, "post"]


def test_anonymize_frame_does_not_mutate_input():
    df = _bronze_frame()
    anonymize_frame(df, salt=SALT)
    assert "author" in df.columns
    assert "a@b.com" in df.loc[0, "post"]


# --- assert_anonymized ------------------------------------------------------------


def _clean_silver() -> pd.DataFrame:
    return anonymize_frame(_bronze_frame(), salt=SALT)


def test_assert_anonymized_accepts_clean_frame():
    assert_anonymized(
        _clean_silver(), raw_authors={"jane_doe", "john_roe"}, text_columns=("post",)
    )


def test_assert_anonymized_catches_surviving_column():
    with pytest.raises(AssertionError, match="column"):
        assert_anonymized(_bronze_frame(), text_columns=())


def test_assert_anonymized_catches_unhashed_author():
    silver = _clean_silver()
    silver.loc[0, "author_hash"] = "jane_doe"  # hashing "accidentally" skipped
    with pytest.raises(AssertionError, match="author_hash"):
        assert_anonymized(silver, raw_authors={"jane_doe"}, text_columns=("post",))


def test_assert_anonymized_catches_unscrubbed_text():
    silver = _clean_silver()
    silver.loc[1, "post"] = "contact me: leak@example.com"
    with pytest.raises(AssertionError, match="email"):
        assert_anonymized(silver, text_columns=("post",))
