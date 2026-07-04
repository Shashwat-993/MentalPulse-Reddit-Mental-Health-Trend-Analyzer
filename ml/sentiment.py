"""Model A — transformer sentiment scorer (Phase 2).

Scores every Silver post with a pretrained social-media sentiment model
(``ml.sentiment_model`` in config; default
``cardiffnlp/twitter-roberta-base-sentiment-latest``, 3-class neg/neu/pos).
This is feature generation with a pretrained model, not training from scratch.

Outputs, written back into ``gold_posts_features``:
    sentiment_score  P(positive) − P(negative) ∈ [−1, 1]
    sentiment_label  argmax class: negative | neutral | positive

The run is MLflow-tracked (params: model/batch/truncation; metrics: rows
scored, label shares, mean score; artifact: per-subreddit weekly means).

Run:
    python -m ml.sentiment                 # full Silver scoring (CPU: ~1–2 h)
    python -m ml.sentiment --limit 2000    # smoke run on a sample
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.loader import Config, load_config

logger = logging.getLogger(__name__)

LABELS = ("negative", "neutral", "positive")


@dataclass
class SentimentResult:
    """Per-post scores aligned to the input frame's ``post_id``."""

    frame: pd.DataFrame  # post_id, sentiment_score, sentiment_label


class SentimentScorer:
    """Batched, truncating wrapper around the configured HF classifier."""

    def __init__(
        self,
        model_name: str,
        *,
        batch_size: int = 64,
        max_length: int = 512,
        device: str = "cpu",
        quantize: bool = True,
    ) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = device
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device).eval()
        self.quantized = False
        if quantize and device == "cpu":
            # Dynamic int8 quantization of the Linear layers: ~2-3x faster CPU
            # inference for a small accuracy cost — logged as a run param.
            self.model = torch.ao.quantization.quantize_dynamic(
                self.model, {torch.nn.Linear}, dtype=torch.qint8
            )
            self.quantized = True
        # Map the model's own label order to ours rather than assuming it.
        id2label = {i: l.lower() for i, l in self.model.config.id2label.items()}
        self._order = [
            next(i for i, l in id2label.items() if l.startswith(prefix))
            for prefix in LABELS
        ]

    def score_texts(self, texts: list[str]) -> np.ndarray:
        """Return an (n, 3) array of [P(neg), P(neu), P(pos)] rows."""
        torch = self._torch
        probs: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                enc = self.tokenizer(
                    batch,
                    truncation=True,
                    max_length=self.max_length,
                    padding=True,
                    return_tensors="pt",
                ).to(self.device)
                logits = self.model(**enc).logits
                p = torch.softmax(logits, dim=-1).cpu().numpy()
                probs.append(p[:, self._order])
        return np.vstack(probs) if probs else np.empty((0, 3))


def score_frame(
    posts: pd.DataFrame,
    scorer: SentimentScorer,
    *,
    text_column: str = "text",
    log_every: int = 20,
) -> pd.DataFrame:
    """Score a Silver-shaped frame; returns post_id + sentiment columns.

    Texts are scored in length-sorted order so each batch pads to similar
    lengths (mixed-length batches waste most of their compute on padding),
    then results are restored to input order.
    """
    texts = posts[text_column].fillna("").astype(str).tolist()
    n = len(texts)
    order = np.argsort([len(t) for t in texts], kind="stable")
    sorted_texts = [texts[i] for i in order]

    scores_sorted = np.empty(n, dtype=np.float64)
    labels_sorted = np.empty(n, dtype=object)
    t0 = time.time()
    chunk = scorer.batch_size * log_every
    for start in range(0, n, chunk):
        probs = scorer.score_texts(sorted_texts[start : start + chunk])
        end = start + len(probs)
        scores_sorted[start:end] = probs[:, 2] - probs[:, 0]
        labels_sorted[start:end] = [LABELS[i] for i in probs.argmax(axis=1)]
        rate = end / max(time.time() - t0, 1e-9)
        eta_min = (n - end) / max(rate, 1e-9) / 60
        logger.info("scored %d/%d posts (%.1f posts/s, ~%.0f min left)", end, n, rate, eta_min)

    out_scores = np.empty(n, dtype=np.float64)
    out_labels = np.empty(n, dtype=object)
    out_scores[order] = scores_sorted
    out_labels[order] = labels_sorted
    return pd.DataFrame(
        {
            "post_id": posts["post_id"].to_numpy(),
            "sentiment_score": np.round(out_scores, 4),
            "sentiment_label": pd.array(list(out_labels), dtype="string"),
        }
    )


def apply_scores_to_gold(gold_posts: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Merge sentiment columns into gold_posts_features by post_id."""
    out = gold_posts.drop(columns=["sentiment_score", "sentiment_label"]).merge(
        scores, on="post_id", how="left"
    )
    out["sentiment_score"] = out["sentiment_score"].astype("Float64")
    out["sentiment_label"] = out["sentiment_label"].astype("string")
    return out[gold_posts.columns]


def main() -> None:
    import mlflow

    from ingestion.transforms import gold_subreddit_weekly

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="score only the first N posts")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--max-length",
        type=int,
        default=256,
        help="token truncation (the model is Twitter-trained; sentiment is "
        "established early in a post, and 256 roughly halves CPU time vs 512)",
    )
    parser.add_argument("--no-quantize", action="store_true")
    args = parser.parse_args()

    cfg: Config = load_config()
    model_name = cfg.ml.sentiment_model
    silver = pd.read_parquet(cfg.path("silver") / "posts.parquet")
    gold_path = cfg.path("gold") / "gold_posts_features.parquet"
    gold_posts = pd.read_parquet(gold_path)
    if args.limit:
        silver = silver.head(args.limit)

    # Checkpointed scoring: partial results land in data/cache so a killed
    # multi-hour run resumes where it stopped instead of starting over.
    ckpt_path = cfg.repo_root / "data" / "cache" / "sentiment_scores.parquet"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    done = (
        pd.read_parquet(ckpt_path)
        if ckpt_path.exists()
        else pd.DataFrame(columns=["post_id", "sentiment_score", "sentiment_label"])
    )
    todo = silver[~silver["post_id"].isin(done["post_id"])]
    logger.info("checkpoint: %d already scored, %d to go", len(done), len(todo))

    mlflow.set_experiment("mentalpulse")
    with mlflow.start_run(run_name="sentiment-scorer"):
        scorer = SentimentScorer(
            model_name,
            batch_size=args.batch_size,
            max_length=args.max_length,
            quantize=not args.no_quantize,
        )
        mlflow.log_params(
            {
                "model": model_name,
                "batch_size": args.batch_size,
                "max_length": args.max_length,
                "quantized_int8": scorer.quantized,
                "n_input_posts": len(silver),
                "n_from_checkpoint": len(done),
                "limit": args.limit or 0,
            }
        )
        shard_size = 10_000
        for start in range(0, len(todo), shard_size):
            shard = todo.iloc[start : start + shard_size]
            done = pd.concat([done, score_frame(shard, scorer)], ignore_index=True)
            done.to_parquet(ckpt_path, index=False)
            logger.info("checkpoint saved: %d/%d scored", len(done), len(silver))
        scores = done

        gold_posts = apply_scores_to_gold(gold_posts, scores)
        gold_posts.to_parquet(gold_path, index=False)
        weekly = gold_subreddit_weekly(gold_posts)
        weekly.to_parquet(cfg.path("gold") / "gold_subreddit_weekly.parquet", index=False)

        scored = gold_posts["sentiment_score"].notna()
        shares = gold_posts.loc[scored, "sentiment_label"].value_counts(normalize=True)
        mlflow.log_metrics(
            {
                "n_scored": int(scored.sum()),
                "mean_sentiment": float(gold_posts.loc[scored, "sentiment_score"].mean()),
                **{f"share_{k}": float(v) for k, v in shares.items()},
            }
        )
        trend = weekly.pivot_table(index="week", columns="subreddit", values="sentiment")
        trend_path = cfg.path("gold") / "weekly_sentiment_trend.csv"
        trend.to_csv(trend_path)
        mlflow.log_artifact(str(trend_path))
        print(f"scored {int(scored.sum()):,} posts -> {gold_path}")
        print(trend.tail(6).round(3).to_string())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
