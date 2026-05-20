from __future__ import annotations

import logging
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from s390x_kb_search.config import (
    BUILD_GUIDE_INTENT_TOKENS,
    BUILD_SCRIPT_INTENT_TOKENS,
    DISTANCE_THRESHOLD,
    DISTRO_TOKENS,
    FIX_INTENT_TOKENS,
    K_RESULTS,
    PORTING_INTENT_TOKENS,
    RRF_K,
    S390X_STOPWORDS,
    SEARCH_TOKEN_PATTERN,
)
from s390x_kb_search.resources import SearchResources

logger = logging.getLogger(__name__)


def tokenize(text: str) -> list[str]:
    return SEARCH_TOKEN_PATTERN.findall(text.lower())


def salient_tokens(query: str) -> set[str]:
    tokens = set(tokenize(query))
    return tokens - S390X_STOPWORDS


def embedding_search(
    query: str,
    resources: SearchResources,
    k: int = K_RESULTS,
) -> list[tuple[int, float]]:
    if resources.usearch_index is None or resources.embedding_model is None:
        return []

    query_embedding = resources.embedding_model.encode(query)
    search_k = max(k * 20, 100)

    results = resources.usearch_index.search(query_embedding, search_k)

    candidates = []
    for key, distance in zip(results.keys, results.distances):
        if distance <= DISTANCE_THRESHOLD:
            candidates.append((int(key), float(distance)))

    return candidates


def bm25_search(
    query: str,
    resources: SearchResources,
    k: int = K_RESULTS,
) -> list[tuple[int, float]]:
    if resources.bm25_index is None:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scores = resources.bm25_index.get_scores(query_tokens)
    search_k = max(k * 20, 100)

    top_indices = np.argsort(scores)[::-1][:search_k]
    candidates = []
    for idx in top_indices:
        score = float(scores[idx])
        if score > 0:
            candidates.append((int(idx), score))

    return candidates


def reciprocal_rank_fusion(
    dense_results: list[tuple[int, float]],
    sparse_results: list[tuple[int, float]],
) -> dict[int, float]:
    fused_scores: dict[int, float] = {}

    for rank, (idx, _) in enumerate(dense_results):
        fused_scores[idx] = fused_scores.get(idx, 0) + 1.0 / (RRF_K + rank + 1)

    for rank, (idx, _) in enumerate(sparse_results):
        fused_scores[idx] = fused_scores.get(idx, 0) + 1.0 / (RRF_K + rank + 1)

    return fused_scores


def _token_overlap(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / max(len(tokens_a), 1)


def _detect_intent(query_tokens: set[str]) -> str | None:
    if query_tokens & BUILD_GUIDE_INTENT_TOKENS:
        return "Build Guide"
    if query_tokens & FIX_INTENT_TOKENS:
        return "Fix Entry"
    if query_tokens & BUILD_SCRIPT_INTENT_TOKENS:
        return "Build Script"
    if query_tokens & PORTING_INTENT_TOKENS:
        return "Fix Entry"
    return None


def _detect_distro(query_tokens: set[str]) -> str | None:
    for token in query_tokens:
        if token in DISTRO_TOKENS:
            return token
    return None


def rerank_candidates(
    candidates: dict[int, float],
    query: str,
    resources: SearchResources,
    dense_results: list[tuple[int, float]],
    sparse_results: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    query_tokens = salient_tokens(query)
    intent = _detect_intent(set(tokenize(query)))
    distro = _detect_distro(set(tokenize(query)))

    dense_set = {idx for idx, _ in dense_results}
    sparse_set = {idx for idx, _ in sparse_results}

    scored: list[tuple[int, float]] = []

    for idx, rrf_score in candidates.items():
        if idx >= len(resources.metadata):
            continue

        entry = resources.metadata[idx]
        title_tokens = set(tokenize(entry.get("title", "")))
        heading_tokens = set(tokenize(entry.get("heading", "")))
        text_tokens = set(tokenize(entry.get("search_text", entry.get("original_text", ""))))
        product_tokens = set(tokenize(entry.get("product", "")))

        text_overlap = _token_overlap(query_tokens, text_tokens)
        title_overlap = _token_overlap(query_tokens, title_tokens)
        heading_overlap = _token_overlap(query_tokens, heading_tokens)
        entity_overlap = _token_overlap(query_tokens, product_tokens)

        dense_bonus = 0.15 if idx in dense_set else 0.0
        sparse_bonus = 0.15 if idx in sparse_set else 0.0

        exact_entity_bonus = 0.0
        if query_tokens & title_tokens:
            exact_entity_bonus = 0.18

        doc_type_bonus = 0.0
        doc_type = entry.get("doc_type", "")
        if intent and doc_type == intent:
            doc_type_bonus = 0.30 if intent == "Build Guide" else 0.25

        distro_bonus = 0.0
        if distro:
            entry_distros = entry.get("distros", [])
            entry_text_lower = entry.get("original_text", "").lower()
            if any(distro in d.lower() for d in entry_distros) or distro in entry_text_lower:
                distro_bonus = 0.15

        final_score = (
            rrf_score
            + 0.35 * text_overlap
            + 0.20 * title_overlap
            + 0.15 * heading_overlap
            + 0.20 * entity_overlap
            + dense_bonus
            + sparse_bonus
            + exact_entity_bonus
            + doc_type_bonus
            + distro_bonus
        )

        scored.append((idx, final_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def deduplicate_urls(
    results: list[tuple[int, float]],
    resources: SearchResources,
    max_per_url: int = 1,
) -> list[tuple[int, float]]:
    seen_urls: dict[str, int] = {}
    deduped = []

    for idx, score in results:
        if idx >= len(resources.metadata):
            continue
        url = resources.metadata[idx].get("url", "")
        if url not in seen_urls:
            seen_urls[url] = 0
        seen_urls[url] += 1
        if seen_urls[url] <= max_per_url:
            deduped.append((idx, score))

    return deduped


def hybrid_search(
    query: str,
    resources: SearchResources,
    k: int = K_RESULTS,
) -> list[dict[str, Any]]:
    dense_results = embedding_search(query, resources, k)
    sparse_results = bm25_search(query, resources, k)

    if not dense_results and not sparse_results:
        return []

    fused = reciprocal_rank_fusion(dense_results, sparse_results)
    reranked = rerank_candidates(fused, query, resources, dense_results, sparse_results)
    deduped = deduplicate_urls(reranked, resources)

    results = []
    for idx, score in deduped[:k]:
        entry = resources.metadata[idx]
        results.append({
            "url": entry.get("url", ""),
            "title": entry.get("title", ""),
            "heading": entry.get("heading", ""),
            "snippet": (entry.get("original_text", ""))[:500],
            "doc_type": entry.get("doc_type", ""),
            "product": entry.get("product", ""),
            "version": entry.get("version", ""),
            "score": round(score, 4),
        })

    return results
