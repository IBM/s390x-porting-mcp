from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi


@dataclass
class SearchResources:
    metadata: list[dict[str, Any]]
    embedding_model: Any
    usearch_index: Any | None = None
    bm25_index: BM25Okapi | None = None
    bm25_corpus_tokens: list[list[str]] = field(default_factory=list)
    default_k: int = 5
