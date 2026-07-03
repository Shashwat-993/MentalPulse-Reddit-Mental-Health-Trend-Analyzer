"""Anonymization + PII stripping (runs in the Bronze -> Silver step).

This module enforces a NON-NEGOTIABLE ground rule: raw usernames and direct
identifiers must NOT survive past Bronze. It matters more than the scaffold
assumed — inspection of the research corpus (2026-07-03) showed the ``author``
column contains RAW Reddit usernames, so this step is where de-identification
actually happens, not merely where it is re-verified.

Entry points:
  * :func:`hash_author` — salted SHA-256 of an author id; stable pseudonym.
  * :func:`scrub_text` — strip emails, phone numbers, u/ and @ handles, and
    URLs from free text (replaced with ``[REDACTED:<kind>]`` markers).
  * :func:`anonymize_frame` — drop raw identifier columns, add ``author_hash``,
    scrub text columns; the single entry point used by Bronze->Silver.
  * :func:`assert_anonymized` — the verification used by the pipeline and the
    Databricks Silver notebook: proves zero raw usernames survived.

Patterns are conservative by design: better to over-redact a false positive
than to leak an identifier.
"""

from __future__ import annotations

import hashlib
import re

import pandas as pd

# Order matters: URLs before handles so "example.com/u/name" is consumed as a
# URL, and emails before handles so "a@b.com" is consumed as an email.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    # name@domain.tld (permissive local part; requires a dotted domain)
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # http(s):// and www. links
    "url": re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE),
    # reddit user references: u/name or /u/name
    "handle": re.compile(r"(?<![\w/])/?u/[A-Za-z0-9_-]+", re.IGNORECASE),
    # @username mentions (not part of an email — emails are consumed first)
    "mention": re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}"),
    # phone numbers: 7+ digits with optional +, separators, and parentheses
    "phone": re.compile(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)"),
}

REDACTION_TEMPLATE = "[REDACTED:{kind}]"

# Raw identifier columns that must not survive past Bronze.
DROP_COLUMNS = ["author", "author_fullname"]


def _is_missing(value) -> bool:
    """True for None, NaN, and pd.NA — any scalar pandas treats as missing."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def hash_author(author_ref: str | None, *, salt: str) -> str | None:
    """Return a salted SHA-256 hash of an author id (None/empty pass through).

    The salt comes from the environment (``MENTALPULSE_HASH_SALT``) and must
    stay stable across runs so the pseudonym is consistent. An empty salt is
    rejected — an unsalted hash of a public username is trivially reversible
    by dictionary attack.
    """
    if not salt:
        raise ValueError("hash_author requires a non-empty salt (MENTALPULSE_HASH_SALT)")
    if _is_missing(author_ref):
        return None
    text = str(author_ref)
    if not text:
        return None
    return hashlib.sha256(f"{salt}:{text}".encode("utf-8")).hexdigest()


def scrub_text(text: str | None) -> str | None:
    """Strip emails/URLs/handles/@mentions/phone numbers from free text."""
    if _is_missing(text):
        return None
    scrubbed = str(text)
    for kind, pattern in PII_PATTERNS.items():
        scrubbed = pattern.sub(REDACTION_TEMPLATE.format(kind=kind), scrubbed)
    return scrubbed


def anonymize_frame(
    df: pd.DataFrame,
    *,
    salt: str,
    author_column: str = "author",
    text_columns: tuple[str, ...] = ("post",),
) -> pd.DataFrame:
    """Drop raw identifiers, add ``author_hash``, and scrub text columns.

    Returns a new frame; the input is not modified. The raw author column and
    every column in :data:`DROP_COLUMNS` are removed unconditionally.
    """
    out = df.copy()
    if author_column in out.columns:
        out["author_hash"] = out[author_column].map(
            lambda a: hash_author(a, salt=salt)
        )
    for col in {author_column, *DROP_COLUMNS}:
        if col in out.columns:
            out = out.drop(columns=col)
    for col in text_columns:
        if col in out.columns:
            out[col] = out[col].map(scrub_text)
    return out


def assert_anonymized(
    silver: pd.DataFrame,
    *,
    raw_authors: set[str] | None = None,
    text_columns: tuple[str, ...] = ("post",),
) -> None:
    """Prove no raw identifiers survived into a Silver frame; raise otherwise.

    Checks, in order of directness:
      1. no raw identifier column (``author``/``author_fullname``) exists;
      2. no raw author value appears in ``author_hash`` (i.e. hashing wasn't
         accidentally skipped) — requires ``raw_authors`` from Bronze;
      3. no PII pattern (email/URL/u-handle/@mention/phone) matches any text
         column — i.e. scrubbing actually ran over every row.
    """
    leaked_cols = [c for c in DROP_COLUMNS if c in silver.columns]
    if leaked_cols:
        raise AssertionError(f"Raw identifier column(s) survived: {leaked_cols}")

    if raw_authors and "author_hash" in silver.columns:
        hashes = set(silver["author_hash"].dropna().unique())
        collisions = hashes & {str(a) for a in raw_authors}
        if collisions:
            raise AssertionError(
                f"{len(collisions)} raw author value(s) present in author_hash"
            )

    for col in text_columns:
        if col not in silver.columns:
            continue
        texts = silver[col].dropna()
        for kind, pattern in PII_PATTERNS.items():
            mask = texts.str.contains(pattern, regex=True)
            hits = int(mask.sum())
            if hits:
                raise AssertionError(
                    f"{hits} unscrubbed {kind} pattern(s) remain in column {col!r}"
                )
