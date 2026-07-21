"""Generate USearch vector index from chunk metadata."""

from __future__ import annotations

import argparse
import json
import logging
import os

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def main():
    parser = argparse.ArgumentParser(description="Generate vector store from metadata")
    parser.add_argument("--metadata", required=True, help="Path to metadata.json")
    parser.add_argument("--output-dir", required=True, help="Output directory for index")
    parser.add_argument("--model", default=EMBEDDING_MODEL, help="SentenceTransformer model name")
    args = parser.parse_args()

    with open(args.metadata) as f:
        metadata = json.load(f)

    logger.info("Loaded %d chunks from %s", len(metadata), args.metadata)

    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model: %s", args.model)
    model = SentenceTransformer(args.model)

    texts = [entry.get("search_text", entry.get("original_text", "")) for entry in metadata]
    logger.info("Encoding %d texts...", len(texts))
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    embeddings = np.array(embeddings, dtype=np.float32)

    logger.info("Embedding shape: %s", embeddings.shape)

    from usearch.index import Index

    index = Index(
        ndim=embeddings.shape[1],
        metric="l2sq",
        dtype="f32",
        connectivity=16,
        expansion_add=128,
        expansion_search=64,
    )

    keys = np.arange(len(embeddings), dtype=np.uint64)
    index.add(keys, embeddings)

    os.makedirs(args.output_dir, exist_ok=True)
    index_path = os.path.join(args.output_dir, "usearch_index.bin")
    index.save(index_path)
    logger.info("Saved USearch index with %d vectors to %s", len(index), index_path)

    metadata_out = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_out, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Copied metadata to %s", metadata_out)


if __name__ == "__main__":
    main()
