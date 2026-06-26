"""Deterministic, AGGREGATE sample data for the MentalPulse dashboard.

Everything here is synthetic. It exists so the dashboard is runnable and
demoable before the real Gold tables exist (Phases 1-2). It is aggregate by
construction — weekly per-subreddit numbers, never individual posts or users —
which keeps the responsible-use guarantees intact even in the demo.

``dashboard.data.get_data_source`` swaps this for real Gold/Snowflake data once
the pipeline produces it; the UI does not change.

The columns mirror the intended Gold schema. ``crisis_rate`` is included as part
of that schema contract (the live source will carry it); the current dashboard
helpers derive crisis metrics from ``crisis_count``.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

import pandas as pd

# Fixed reference point so the sample data is byte-identical on every run
# (no dependence on the current date).
_REFERENCE_WEEK_END = date(2024, 12, 29)
_SEED = 42

_COLUMNS = ["week", "subreddit", "n_posts", "sentiment", "crisis_rate", "crisis_count"]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_weekly_aggregates(
    subreddits, n_weeks: int = 52, seed: int = _SEED
) -> pd.DataFrame:
    """Return a long-form weekly aggregate table for the given subreddits.

    One row per (week, subreddit) with columns:
      * ``week`` — Timestamp (weekly)
      * ``n_posts`` — posts that week (aggregate count)
      * ``sentiment`` — mean sentiment in [-1, 1]
      * ``crisis_rate`` — share of posts flagged as crisis signals in [0, 1]
      * ``crisis_count`` — round(n_posts * crisis_rate) (aggregate count)

    Each community is seeded independently (from a deterministic string seed), so
    a community's series is identical regardless of its position in the input
    list, while the whole table stays byte-identical across runs.
    """
    subreddits = list(subreddits or [])
    if not subreddits:
        return pd.DataFrame(columns=_COLUMNS)

    weeks = [
        pd.Timestamp(_REFERENCE_WEEK_END - timedelta(weeks=(n_weeks - 1 - i)))
        for i in range(n_weeks)
    ]

    rows = []
    for sub in subreddits:
        # Per-community deterministic seed (str seed -> stable across processes
        # and independent of list order).
        rng = random.Random(f"{seed}:{sub}")
        baseline_sentiment = rng.uniform(-0.25, 0.10)
        baseline_posts = rng.uniform(400, 1500)
        baseline_crisis = rng.uniform(0.03, 0.09)
        for w_idx, week in enumerate(weeks):
            seasonal = 0.08 * math.sin(2 * math.pi * w_idx / 52.0)
            drift = -0.10 * (w_idx / n_weeks)  # slight illustrative downward drift
            sentiment = _clip(
                baseline_sentiment + seasonal + drift + rng.gauss(0, 0.05), -1.0, 1.0
            )
            n_posts = int(
                max(
                    50,
                    baseline_posts * (1 + 0.20 * math.sin(2 * math.pi * w_idx / 52.0))
                    + rng.gauss(0, 60),
                )
            )
            # Crisis rate ticks up a little when sentiment is more negative.
            crisis_rate = _clip(
                baseline_crisis + 0.05 * max(0.0, -sentiment) + rng.gauss(0, 0.008),
                0.0,
                1.0,
            )
            rows.append(
                {
                    "week": week,
                    "subreddit": sub,
                    "n_posts": n_posts,
                    "sentiment": round(sentiment, 3),
                    "crisis_rate": round(crisis_rate, 4),
                    "crisis_count": int(round(n_posts * crisis_rate)),
                }
            )
    return pd.DataFrame(rows, columns=_COLUMNS)
