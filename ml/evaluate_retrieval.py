"""Evaluate company-to-news ranking against ml/golden_news_company.csv.

Examples from the repository root:
    python -m ml.evaluate_retrieval --method lexical
    python -m ml.evaluate_retrieval --method bge
    python -m ml.evaluate_retrieval --method bge-rerank
    python -m ml.evaluate_retrieval --method all
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from ml.retrieval import BGEEmbedder, BGEReranker, Candidate


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "ml" / "golden_news_company.csv"


def _tokens(text: str) -> set[str]:
    # Lightweight, dependency-free lexical baseline. Short tokens are usually
    # grammatical noise; this is a baseline, not a Russian morphological model.
    return {token for token in re.findall(r"[a-zа-яё0-9]+", text.lower()) if len(token) > 2}


def _load_groups(query_context: bool = False) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    with DATASET.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            group = groups.setdefault(row["company_id"], {
                "query": " ".join(filter(None, (
                    row["company_okved"],
                    row.get("company_search_context", "") if query_context else "",
                ))),
                "candidates": {},
            })
            group["candidates"][row["news_id"]] = {
                "candidate": Candidate(
                    row["news_id"],
                    row["news_text"],
                    {"title": row["news_title"], "category": row["expected_category"]},
                ),
                "relevant": row["relevance"] == "1",
            }
    return groups


def _rank_lexical(query: str, candidates: list[dict]) -> list[tuple[str, float]]:
    query_terms = _tokens(query)
    scored = []
    for index, item in enumerate(candidates):
        terms = _tokens(item["candidate"].text)
        # Overlap normalized by query size rewards sector terms present in a
        # headline/body without letting long articles dominate.
        score = len(query_terms & terms) / max(1, len(query_terms))
        scored.append((item["candidate"].id, score, index))
    return [(item_id, score) for item_id, score, _ in sorted(scored, key=lambda item: -item[1])]


def _rank_bge(query: str, candidates: list[dict], embedder: BGEEmbedder) -> list[tuple[str, float]]:
    texts = [item["candidate"].text for item in candidates]
    vectors = embedder.encode([query, *texts])
    query_vector, candidate_vectors = vectors[0], vectors[1:]
    scores = [sum(a * b for a, b in zip(query_vector, vector)) for vector in candidate_vectors]
    return [(candidates[index]["candidate"].id, scores[index])
            for index in sorted(range(len(scores)), key=lambda i: -scores[i])]


def _rank_reranked(query: str, candidates: list[dict], embedder: BGEEmbedder,
                   reranker: BGEReranker) -> list[tuple[str, float]]:
    dense_ids = _rank_bge(query, candidates, embedder)
    by_id = {item["candidate"].id: item["candidate"] for item in candidates}
    ordered = [by_id[item_id] for item_id, _ in dense_ids]
    scores = reranker.score(query, [item.text for item in ordered])
    return [(item.id, score) for item, score in sorted(zip(ordered, scores), key=lambda pair: -pair[1])]


def _metrics(groups: dict[str, dict], rankings: dict[str, list[tuple[str, float]]], ks: Iterable[int]) -> dict:
    recalls = {k: [] for k in ks}
    reciprocal_ranks = []
    per_company = {}
    for company_id, group in groups.items():
        relevant_ids = {
            item_id for item_id, item in group["candidates"].items() if item["relevant"]
        }
        ranking = rankings[company_id]
        tie_groups: list[list[str]] = []
        tie_scores: list[float] = []
        for item_id, score in ranking:
            if not tie_scores or score != tie_scores[-1]:
                tie_groups.append([])
                tie_scores.append(score)
            tie_groups[-1].append(item_id)

        # Average over permutations within tied scores so source order cannot
        # artificially improve the lexical baseline's MRR or Recall@K.
        rank_before = 0
        expected_rr = 0.0
        first_relevant_tie_seen = False
        expected_hits_at_k = {k: 0.0 for k in ks}
        for tied_ids in tie_groups:
            group_size = len(tied_ids)
            relevant_in_group = sum(item_id in relevant_ids for item_id in tied_ids)
            if relevant_in_group and not first_relevant_tie_seen:
                denominator = math.comb(group_size, relevant_in_group)
                for offset in range(group_size - relevant_in_group + 1):
                    first_relevant_probability = (
                        math.comb(group_size - offset - 1, relevant_in_group - 1)
                        / denominator
                    )
                    expected_rr += first_relevant_probability / (rank_before + offset + 1)
                first_relevant_tie_seen = True
            for k in ks:
                slots_here = max(0, min(group_size, k - rank_before))
                expected_hits_at_k[k] += slots_here * relevant_in_group / group_size
            rank_before += group_size

        reciprocal_ranks.append(expected_rr)
        company_metrics = {"relevant_count": len(relevant_ids)}
        for k in ks:
            recall = expected_hits_at_k[k] / max(1, len(relevant_ids))
            recalls[k].append(recall)
            company_metrics[f"recall@{k}"] = round(recall, 4)
        company_metrics["reciprocal_rank"] = round(reciprocal_ranks[-1], 4)
        per_company[company_id] = company_metrics
    return {
        "queries": len(groups),
        "mrr": round(sum(reciprocal_ranks) / max(1, len(reciprocal_ranks)), 4),
        **{f"recall@{k}": round(sum(values) / max(1, len(values)), 4)
           for k, values in recalls.items()},
        "per_company": per_company,
    }


def evaluate(method: str) -> dict:
    return evaluate_with_models(method)


def evaluate_with_models(
    method: str,
    embedding_model: str | None = None,
    reranker_model: str | None = None,
    query_context: bool = False,
) -> dict:
    groups = _load_groups(query_context=query_context)
    rankings: dict[str, list[tuple[str, float]]] = {}
    embedder = BGEEmbedder(model_name=embedding_model) if method in {"embedding", "embedding-rerank"} else None
    reranker = BGEReranker(model_name=reranker_model) if method == "embedding-rerank" else None
    for company_id, group in groups.items():
        candidates = list(group["candidates"].values())
        if method == "lexical":
            rankings[company_id] = _rank_lexical(group["query"], candidates)
        elif method == "embedding":
            rankings[company_id] = _rank_bge(group["query"], candidates, embedder)
        else:
            rankings[company_id] = _rank_reranked(
                group["query"], candidates, embedder, reranker
            )
    result = _metrics(groups, rankings, ks=(1, 3, 5))
    if method != "lexical":
        result["embedding_model"] = embedding_model or os.getenv("ML_EMBEDDING_MODEL", "BAAI/bge-m3")
    if method == "embedding-rerank":
        result["reranker_model"] = reranker_model or os.getenv(
            "ML_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
        )
    result["query_context"] = query_context
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate news retrieval against the draft labels.")
    parser.add_argument("--method", choices=("lexical", "embedding", "embedding-rerank", "all"), default="lexical")
    parser.add_argument("--embedding-model", help="Override ML_EMBEDDING_MODEL for this run")
    parser.add_argument("--reranker-model", help="Override ML_RERANKER_MODEL for this run")
    parser.add_argument("--hf-home", type=Path, help="Hugging Face cache directory")
    parser.add_argument("--query-context", action="store_true", help="Add manually curated sector synonyms to company queries")
    parser.add_argument("--offline", action="store_true", help="Do not contact Hugging Face Hub")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    if args.hf_home:
        os.environ["HF_HOME"] = str(args.hf_home.resolve())
    methods = ("lexical", "embedding", "embedding-rerank") if args.method == "all" else (args.method,)
    results = {
        method: evaluate_with_models(
            method, args.embedding_model, args.reranker_model, args.query_context
        )
        for method in methods
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
