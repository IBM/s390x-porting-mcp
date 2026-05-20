from __future__ import annotations

import logging
import os
import sys
from typing import Any

from utils.config import DATA_DIR, METADATA_PATH, MODEL_NAME, USEARCH_INDEX_PATH

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_search_resources = None


def _get_search_resources():
    global _search_resources
    if _search_resources is not None:
        return _search_resources

    import s390x_kb_search

    if not os.path.exists(METADATA_PATH):
        logger.warning("Knowledge base not found at %s. Search will return empty results.", DATA_DIR)
        from s390x_kb_search.resources import SearchResources
        _search_resources = SearchResources(metadata=[], embedding_model=None)
        return _search_resources

    _search_resources = s390x_kb_search.load_search_resources(
        metadata_path=METADATA_PATH,
        usearch_index_path=USEARCH_INDEX_PATH,
        model_name=MODEL_NAME,
    )
    return _search_resources


def search_knowledge_base(query: str, k: int = 5) -> list[dict[str, Any]]:
    import s390x_kb_search

    resources = _get_search_resources()
    return s390x_kb_search.search(query, resources, k=k)
