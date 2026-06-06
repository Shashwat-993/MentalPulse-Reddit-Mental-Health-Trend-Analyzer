"""Ragas evaluation of the MentalPulse agent (Phase 4).

Builds a small hand-written eval set (~15 Q&A with reference answers/contexts)
and runs Ragas for faithfulness, answer relevancy, and context
precision/recall. Runs for BOTH retriever backends (LanceDB vs Cortex) and saves
a scored comparison report — a key interview artifact (the dual-deployment story).

Status: stub — implemented in Phase 4.
"""

from __future__ import annotations

from config.loader import Config


def run_eval(cfg: Config, backend: str) -> dict:
    """Run Ragas for one retriever backend; return scored metrics. Phase 4."""
    raise NotImplementedError("Implemented in Phase 4.")


def compare_backends(cfg: Config) -> None:
    """Run the eval for both backends and write the comparison report. Phase 4."""
    raise NotImplementedError("Implemented in Phase 4.")


if __name__ == "__main__":
    raise SystemExit("ragas_eval is implemented in Phase 4.")
