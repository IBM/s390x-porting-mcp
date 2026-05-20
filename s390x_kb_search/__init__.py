from __future__ import annotations

import logging
from typing import Any

from rank_bm25 import BM25Okapi

from s390x_kb_search.config import K_RESULTS
from s390x_kb_search.loaders import load_metadata, load_usearch_index
from s390x_kb_search.resources import SearchResources
from s390x_kb_search.response import add_disclaimer
from s390x_kb_search.search import hybrid_search, tokenize

logger = logging.getLogger(__name__)


def load_search_resources(
    metadata_path: str,
    usearch_index_path: str,
    model_name: str = "all-MiniLM-L6-v2",
) -> SearchResources:
    metadata = load_metadata(metadata_path)
    usearch_index = load_usearch_index(usearch_index_path)

    embedding_model = None
    try:
        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer(model_name)
        logger.info("Loaded embedding model: %s", model_name)
    except ImportError:
        logger.warning("sentence-transformers not installed, semantic search disabled")

    bm25_index = None
    bm25_corpus_tokens: list[list[str]] = []
    if metadata:
        bm25_corpus_tokens = [
            tokenize(entry.get("search_text", entry.get("original_text", "")))
            for entry in metadata
        ]
        bm25_index = BM25Okapi(bm25_corpus_tokens)
        logger.info("Built BM25 index over %d documents", len(metadata))

    return SearchResources(
        metadata=metadata,
        embedding_model=embedding_model,
        usearch_index=usearch_index,
        bm25_index=bm25_index,
        bm25_corpus_tokens=bm25_corpus_tokens,
    )


def search(
    query: str,
    resources: SearchResources,
    k: int = K_RESULTS,
) -> list[dict[str, Any]]:
    results = hybrid_search(query, resources, k)
    return add_disclaimer(results)
