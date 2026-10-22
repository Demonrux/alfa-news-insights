"""Optional machine-learning utilities for multilingual news retrieval."""

from .retrieval import (
    BGEEmbedder,
    BGEReranker,
    Candidate,
    MLDependencyError,
    NewsRetriever,
    RankedCandidate,
)

__all__ = [
    "BGEEmbedder",
    "BGEReranker",
    "Candidate",
    "MLDependencyError",
    "NewsRetriever",
    "RankedCandidate",
]
