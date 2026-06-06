"""Anonymization + PII stripping (runs in the Bronze -> Silver step).

Implemented in Phase 1. This module enforces a NON-NEGOTIABLE ground rule:
raw usernames and direct identifiers must NOT survive past Bronze.

Planned behavior:
  * hash_author(author_ref): salted SHA-256 of the author id, using the salt
    from .env (MENTALPULSE_HASH_SALT). Returns a stable pseudonymous id.
  * scrub_text(text): regex-strip emails, phone numbers, @handles, and URLs
    from free text bodies/titles.
  * anonymize_frame(df): drop raw author/author_fullname columns, add a hashed
    author column, and scrub text columns — the single entry point used by the
    Bronze->Silver transform.

A verification check (zero raw usernames in Silver) is part of the Phase 1
acceptance criteria.
"""

from __future__ import annotations

# Patterns to be finalized in Phase 1 (documented here so intent is reviewable).
# Conservative by design; better to over-redact than to leak an identifier.
PII_PATTERNS_TODO = {
    "email": r"...",       # name@domain.tld
    "phone": r"...",       # common phone formats
    "handle": r"...",      # @username mentions
    "url": r"...",         # http(s):// and www. links
}


def hash_author(author_ref: str | None, *, salt: str) -> str | None:
    """Return a salted SHA-256 hash of an author id (None passes through).

    Implemented in Phase 1.
    """
    raise NotImplementedError("Implemented in Phase 1.")


def scrub_text(text: str | None) -> str | None:
    """Strip emails/phones/@handles/URLs from free text. Implemented in Phase 1."""
    raise NotImplementedError("Implemented in Phase 1.")


def anonymize_frame(df, *, salt: str):
    """Drop raw identifiers, hash author, and scrub text columns.

    The single entry point used by the Bronze->Silver transform. Implemented in
    Phase 1.
    """
    raise NotImplementedError("Implemented in Phase 1.")
