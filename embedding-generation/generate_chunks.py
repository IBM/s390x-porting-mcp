"""Orchestrator: fetch all sources, generate chunks, output YAML."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(__file__))

from fetch_build_scripts import build_script_index
from fetch_build_scripts import generate_chunks as gen_script_chunks
from fetch_wiki_pages import generate_chunks as gen_wiki_chunks

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate chunks from all knowledge sources")
    parser.add_argument("--wiki-dir", help="Path to cloned docs.wiki.git")
    parser.add_argument("--scripts-dir", help="Path to cloned scripts repo")
    parser.add_argument("--output-dir", default="output", help="Output directory for chunk files")
    parser.add_argument("--script-index-output", help="Path to write script_index.json")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    all_chunks = []

    if args.wiki_dir:
        logger.info("Loading wiki pages from %s", args.wiki_dir)
        wiki_chunks = gen_wiki_chunks(args.wiki_dir)
        all_chunks.extend(wiki_chunks)
        logger.info("  -> %d chunks from wiki", len(wiki_chunks))

    if args.scripts_dir:
        logger.info("Loading build scripts from %s", args.scripts_dir)
        script_chunks = gen_script_chunks(args.scripts_dir)
        all_chunks.extend(script_chunks)
        logger.info("  -> %d chunks from scripts", len(script_chunks))

        if args.script_index_output:
            index = build_script_index(args.scripts_dir)
            with open(args.script_index_output, "w") as f:
                json.dump(index, f, indent=2)
            logger.info("Wrote script index to %s (%d packages)", args.script_index_output, len(index))

    chunks_path = os.path.join(args.output_dir, "chunks.yaml")
    with open(chunks_path, "w") as f:
        yaml.dump(all_chunks, f, default_flow_style=False, allow_unicode=True)

    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(all_chunks, f, indent=2)

    logger.info("Total: %d chunks written to %s and %s", len(all_chunks), chunks_path, metadata_path)


if __name__ == "__main__":
    main()
