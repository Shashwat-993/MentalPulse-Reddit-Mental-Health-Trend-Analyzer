"""Model B — crisis-signal classifier (Phase 2). Weak-supervision BASELINE.

Flags posts whose language suggests acute distress so that AGGREGATE trends
(weekly counts/rates per community) can be reported. It is explicitly NOT a
diagnosis and never surfaces individual posts — see the README disclaimer.

No ground-truth labels exist, so this is weak supervision, documented plainly:

  * Weak labels come from a conservative two-tier distress lexicon:
    one ACUTE-tier phrase, or two distinct SEVERE-tier terms, labels a post 1.
  * The classifier (transparent logistic regression, class-balanced) is
    trained on those labels but does NOT see the acute tier as a feature —
    its features are deliberately broader (severe-term density, first-person
    focus, negations, Model A sentiment, length), so it generalizes the
    heuristic instead of copying it. Coefficients are logged as importances.
  * The corpus samples ~1 post per author per window and has date-level
    timestamps only, so the scaffold's per-author features (sentiment
    velocity, posting frequency, time-of-day) are not computable here;
    they are documented as dropped.

Outputs, written back into ``gold_posts_features``:
    crisis_score  P(crisis-signal) from the classifier ∈ [0, 1]
    crisis_flag   crisis_score ≥ ml.crisis.weak_label_threshold

Run (after ml.sentiment has populated sentiment_score):
    python -m ml.crisis
"""

from __future__ import annotations

import argparse
import logging
import re

import numpy as np
import pandas as pd

from config.loader import Config, load_config

logger = logging.getLogger(__name__)

# Conservative, documented lexicon. ACUTE phrases indicate possible active
# ideation; SEVERE terms indicate serious distress. Chosen to be high-precision
# (better to under-flag a euphemism than to flag ordinary venting); aggregate
# reporting tolerates missed posts far better than noisy flags.
ACUTE_PHRASES = (
    "kill myself",
    "killing myself",
    "end my life",
    "ending my life",
    "want to die",
    "wanted to die",
    "wish i was dead",
    "wish i were dead",
    "better off dead",
    "no reason to live",
    "nothing to live for",
    "end it all",
    "suicidal",
    "suicide",
    "self harm",
    "self-harm",
    "hurt myself",
    "harming myself",
)
SEVERE_TERMS = (
    "hopeless",
    "hopelessness",
    "worthless",
    "unbearable",
    "can't go on",
    "cant go on",
    "can't take it anymore",
    "cant take it anymore",
    "give up on everything",
    "giving up on everything",
    "no way out",
    "empty inside",
    "burden to everyone",
    "crisis",
)

_FIRST_PERSON = re.compile(r"\b(i|me|my|myself|i'm|im|i've|ive)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(no|not|never|can't|cant|won't|wont|nothing|nobody)\b", re.IGNORECASE)

FEATURE_COLUMNS = [
    "severe_density",       # severe-tier hits per 100 words
    "first_person_density", # first-person tokens per 100 words
    "negation_density",     # negation tokens per 100 words
    "sentiment_score",      # Model A output
    "log_n_words",
]


def _count_hits(text: str, terms: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(lower.count(t) for t in terms)


def _distinct_hits(text: str, terms: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for t in terms if t in lower)


def weak_labels(texts: pd.Series) -> pd.Series:
    """1 = crisis-signal per the documented heuristic; 0 otherwise."""
    def label(text) -> int:
        if not isinstance(text, str) or not text:
            return 0
        if _distinct_hits(text, ACUTE_PHRASES) >= 1:
            return 1
        return int(_distinct_hits(text, SEVERE_TERMS) >= 2)

    return texts.map(label).astype("int64")


def build_features(silver: pd.DataFrame, gold_posts: pd.DataFrame) -> pd.DataFrame:
    """Engineered features per post (indexed like silver). Excludes the ACUTE
    tier on purpose — see the module docstring."""
    text = silver["text"].fillna("").astype(str)
    n_words = text.str.split().str.len().clip(lower=1)
    sentiment = (
        silver[["post_id"]]
        .merge(gold_posts[["post_id", "sentiment_score"]], on="post_id", how="left")
        ["sentiment_score"]
        .astype("float64")
    )
    if sentiment.isna().all():
        raise RuntimeError(
            "sentiment_score is empty — run `python -m ml.sentiment` first"
        )
    return pd.DataFrame(
        {
            "post_id": silver["post_id"].to_numpy(),
            "severe_density": [
                100 * _count_hits(t, SEVERE_TERMS) / w for t, w in zip(text, n_words)
            ],
            "first_person_density": 100 * text.str.count(_FIRST_PERSON) / n_words,
            "negation_density": 100 * text.str.count(_NEGATION) / n_words,
            "sentiment_score": sentiment.fillna(0.0).to_numpy(),
            "log_n_words": np.log1p(n_words),
        }
    )


def train_and_score(
    features: pd.DataFrame, labels: pd.Series, *, threshold: float, seed: int = 7
):
    """Train the transparent classifier; return (scores_frame, report_dict)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = features[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = labels.to_numpy()
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed),
    )
    model.fit(X_tr, y_tr)

    p_te = model.predict_proba(X_te)[:, 1]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_te, p_te >= threshold, average="binary", zero_division=0
    )
    logit = model.named_steps["logisticregression"]
    coefficients = dict(zip(FEATURE_COLUMNS, np.round(logit.coef_[0], 4)))
    report = {
        "holdout_auc": float(roc_auc_score(y_te, p_te)),
        "holdout_precision": float(precision),
        "holdout_recall": float(recall),
        "holdout_f1": float(f1),
        "weak_label_rate": float(y.mean()),
        "coefficients": coefficients,
    }

    p_all = model.predict_proba(X)[:, 1]
    scores = pd.DataFrame(
        {
            "post_id": features["post_id"].to_numpy(),
            "crisis_score": np.round(p_all, 4),
            "crisis_flag": p_all >= threshold,
        }
    )
    return scores, report


def apply_scores_to_gold(gold_posts: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    out = gold_posts.drop(columns=["crisis_score", "crisis_flag"]).merge(
        scores, on="post_id", how="left"
    )
    out["crisis_score"] = out["crisis_score"].astype("Float64")
    out["crisis_flag"] = out["crisis_flag"].astype("boolean")
    return out[gold_posts.columns]


def main() -> None:
    import json

    import mlflow

    from ingestion.transforms import gold_subreddit_weekly

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    cfg: Config = load_config()
    threshold = args.threshold or float(cfg.ml.crisis.weak_label_threshold)
    silver = pd.read_parquet(cfg.path("silver") / "posts.parquet")
    gold_path = cfg.path("gold") / "gold_posts_features.parquet"
    gold_posts = pd.read_parquet(gold_path)

    mlflow.set_experiment("mentalpulse")
    with mlflow.start_run(run_name="crisis-classifier"):
        labels = weak_labels(silver["text"])
        features = build_features(silver, gold_posts)
        scores, report = train_and_score(features, labels, threshold=threshold)

        mlflow.log_params(
            {
                "classifier": "logistic_regression(balanced)",
                "threshold": threshold,
                "n_acute_phrases": len(ACUTE_PHRASES),
                "n_severe_terms": len(SEVERE_TERMS),
                "features": ",".join(FEATURE_COLUMNS),
            }
        )
        coefficients = report.pop("coefficients")
        mlflow.log_metrics({**report, "flag_rate": float(scores["crisis_flag"].mean())})
        mlflow.log_dict(coefficients, "feature_importances.json")

        gold_posts = apply_scores_to_gold(gold_posts, scores)
        gold_posts.to_parquet(gold_path, index=False)
        weekly = gold_subreddit_weekly(gold_posts)
        weekly.to_parquet(cfg.path("gold") / "gold_subreddit_weekly.parquet", index=False)

        print(json.dumps({**report, "flag_rate": float(scores['crisis_flag'].mean())}, indent=2))
        print("feature importances (standardized coefficients):")
        for name, coef in sorted(coefficients.items(), key=lambda kv: -abs(kv[1])):
            print(f"  {name:22s} {coef:+.4f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
