from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def load_metadata(metadata_path: str) -> list[dict[str, Any]]:
    if not os.path.exists(metadata_path):
        logger.warning("Metadata file not found: %s", metadata_path)
        return []

    with open(metadata_path) as f:
        data = json.load(f)

    logger.info("Loaded %d metadata entries from %s", len(data), metadata_path)
    return data


def load_usearch_index(index_path: str, ndim: int = 384):
    if not os.path.exists(index_path):
        logger.warning("USearch index not found: %s", index_path)
        return None

    try:
        from usearch.index import Index

        index = Index(ndim=ndim, metric="l2sq", dtype="f32")
        index.load(index_path)
        logger.info("Loaded USearch index with %d vectors from %s", len(index), index_path)
        return index
    except ImportError:
        logger.warning("usearch not installed, semantic search disabled")
        return None
    except Exception as e:
        logger.error("Failed to load USearch index: %s", e)
        return None
