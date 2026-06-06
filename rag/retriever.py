"""Retriever interface + two interchangeable backends (Phase 3).

A single ``Retriever`` interface with two implementations selectable via config
(``rag.retriever``):

  * ``LanceDBRetriever`` — local, open-source vector store over the anonymized
    corpus using a sentence-transformer embedding model. The cheap/free mirror.
  * ``CortexRetriever`` — Snowflake Cortex Search over the same corpus (the
    enterprise side of the dual-deployment comparison).

Swapping the backend in config must require NO code changes elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from config.loader import Config


@dataclass(frozen=True)
class Passage:
    """A retrieved passage from the anonymized, aggregated corpus."""

    text: str
    score: float
    metadata: dict


class Retriever(ABC):
    """Common interface for all retrieval backends."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[Passage]:
        """Return the top-k passages most relevant to ``query``."""
        raise NotImplementedError


class LanceDBRetriever(Retriever):
    """Local open-source vector store. Implemented in Phase 3."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        raise NotImplementedError("LanceDBRetriever is implemented in Phase 3.")

    def search(self, query: str, top_k: int = 5) -> list[Passage]:
        raise NotImplementedError("Implemented in Phase 3.")


class CortexRetriever(Retriever):
    """Snowflake Cortex Search backend. Implemented in Phase 3."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        raise NotImplementedError("CortexRetriever is implemented in Phase 3.")

    def search(self, query: str, top_k: int = 5) -> list[Passage]:
        raise NotImplementedError("Implemented in Phase 3.")


def get_retriever(cfg: Config) -> Retriever:
    """Factory: return the retriever selected by ``cfg.rag.retriever``.

    Implemented in Phase 3. Dispatches on "lancedb" | "cortex".
    """
    raise NotImplementedError("Implemented in Phase 3.")
