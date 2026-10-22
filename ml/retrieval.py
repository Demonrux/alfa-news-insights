"""Multilingual dense retrieval and reranking for news and company profiles.

Install the optional dependencies with ``pip install -e ".[ml]"``. Models are
loaded lazily, so importing the backend does not download ML weights.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Iterable, Sequence


class MLDependencyError(RuntimeError):
    """Raised when the optional embedding or reranking dependency is missing."""


@dataclass(frozen=True)
class Candidate:
    """A searchable item. ``text`` should contain title plus useful context."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: float
    dense_score: float


class BGEEmbedder:
    """Create normalized multilingual vectors using BAAI/bge-m3."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name or os.getenv("ML_EMBEDDING_MODEL", "BAAI/bge-m3")
        self.device = device or os.getenv("ML_DEVICE")
        self.batch_size = batch_size

    @cached_property
    def _model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise MLDependencyError(
                'ML dependencies are missing. Install them with: pip install -e ".[ml]"'
            ) from exc
        kwargs = {"device": self.device} if self.device else {}
        return SentenceTransformer(self.model_name, **kwargs)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one L2-normalized vector for each input text."""
        if not texts:
            return []
        clean_texts = [text.strip() for text in texts]
        if any(not text for text in clean_texts):
            raise ValueError("texts must not contain empty strings")
        vectors = self._model.encode(
            clean_texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


class BGEReranker:
    """Rerank query/text pairs with the multilingual BGE cross-encoder."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str | None = None,
        batch_size: int = 16,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name or os.getenv(
            "ML_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
        )
        self.device = device or os.getenv("ML_DEVICE")
        self.batch_size = batch_size

    @cached_property
    def _model(self):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise MLDependencyError(
                'ML dependencies are missing. Install them with: pip install -e ".[ml]"'
            ) from exc
        kwargs = {"device": self.device} if self.device else {}
        return CrossEncoder(self.model_name, **kwargs)

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Return one relevance score per text, preserving input order."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("texts must not contain empty strings")
        scores = self._model.predict(
            [(query, text) for text in texts],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return [float(score) for score in scores]


class NewsRetriever:
    """Retrieve candidates by cosine similarity, then rerank the shortlist.

    This is intentionally stateless: callers can build candidate lists from
    PostgreSQL or files and choose their own vector cache/index.
    """

    def __init__(
        self,
        embedder: BGEEmbedder | None = None,
        reranker: BGEReranker | None = None,
    ) -> None:
        self.embedder = embedder or BGEEmbedder()
        self.reranker = reranker or BGEReranker()

    def search(
        self,
        query: str,
        candidates: Iterable[Candidate],
        *,
        top_k: int = 10,
        rerank_k: int | None = None,
    ) -> list[RankedCandidate]:
        """Return up to ``top_k`` results sorted by reranker score."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        items = [item for item in candidates if item.text.strip()]
        if not items:
            return []

        vectors = self.embedder.encode([query, *(item.text for item in items)])
        query_vector, item_vectors = vectors[0], vectors[1:]
        dense_scores = [
            sum(a * b for a, b in zip(query_vector, vector))
            for vector in item_vectors
        ]
        shortlist_size = min(len(items), max(top_k, rerank_k or top_k))
        shortlist_indices = sorted(
            range(len(items)), key=lambda index: dense_scores[index], reverse=True
        )[:shortlist_size]
        shortlist = [items[index] for index in shortlist_indices]
        rerank_scores = self.reranker.score(query, [item.text for item in shortlist])
        ranked = [
            RankedCandidate(items[index], score, dense_scores[index])
            for index, score in zip(shortlist_indices, rerank_scores)
        ]
        ranked.sort(key=lambda result: result.score, reverse=True)
        return ranked[:top_k]
