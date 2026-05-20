"""Fetch wiki pages from linux-on-ibm-z/docs.wiki.git repository."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import uuid
from typing import Any

logger = logging.getLogger(__name__)

WIKI_REPO_URL = "https://github.com/linux-on-ibm-z/docs.wiki.git"
WIKI_BASE_URL = "https://github.com/linux-on-ibm-z/docs/wiki"


def clone_wiki(target_dir: str | None = None) -> str:
    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="s390x-wiki-")

    if os.path.exists(os.path.join(target_dir, ".git")):
        logger.info("Wiki already cloned at %s", target_dir)
        return target_dir

    logger.info("Cloning wiki from %s", WIKI_REPO_URL)
    subprocess.run(
        ["git", "clone", "--depth", "1", WIKI_REPO_URL, target_dir],
        check=True,
        capture_output=True,
    )
    return target_dir


def read_wiki_pages(wiki_dir: str) -> list[dict[str, str]]:
    pages = []
    for filename in sorted(os.listdir(wiki_dir)):
        if not filename.endswith(".md"):
            continue
        if filename in ("Home.md", "_Sidebar.md", "_Footer.md"):
            continue

        filepath = os.path.join(wiki_dir, filename)
        with open(filepath) as f:
            content = f.read()

        page_name = filename.replace(".md", "").replace("-", " ")
        url = f"{WIKI_BASE_URL}/{filename.replace('.md', '')}"

        pages.append({
            "filename": filename,
            "page_name": page_name,
            "url": url,
            "content": content,
        })

    logger.info("Read %d wiki pages from %s", len(pages), wiki_dir)
    return pages


def _extract_product_name(page_name: str) -> str:
    name = page_name
    for prefix in ("Building ", "Installing "):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    name = re.sub(r"\s+\d+\.[\dx]+.*$", "", name)
    return name.strip()


def chunk_wiki_page(page: dict[str, str]) -> list[dict[str, Any]]:
    content = page["content"]
    page_name = page["page_name"]
    url = page["url"]
    product = _extract_product_name(page_name)

    sections = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

    chunks = []
    current_heading = page_name
    current_text = ""
    heading_path = [page_name]

    for i, part in enumerate(sections):
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', part)
        if heading_match:
            if current_text.strip():
                chunks.append(_make_chunk(
                    page_name, product, url, current_heading, heading_path, current_text
                ))
            level = len(heading_match.group(1))
            current_heading = heading_match.group(2).strip()
            heading_path = [page_name] + ([current_heading] if level <= 2 else heading_path[1:] + [current_heading])
            current_text = ""
        else:
            current_text += part

    if current_text.strip():
        chunks.append(_make_chunk(
            page_name, product, url, current_heading, heading_path, current_text
        ))

    return chunks


def _make_chunk(
    page_name: str,
    product: str,
    url: str,
    heading: str,
    heading_path: list[str],
    text: str,
) -> dict[str, Any]:
    search_text = f"{product} {page_name} {heading} s390x build {text[:1000]}"
    return {
        "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"wiki:{url}:{heading}")),
        "chunk_uuid": f"wiki_{re.sub(r'[^a-z0-9]', '_', page_name.lower())}_{re.sub(r'[^a-z0-9]', '_', heading.lower()[:40])}",
        "url": url,
        "original_text": text.strip()[:2000],
        "title": page_name,
        "heading": heading,
        "heading_path": heading_path,
        "doc_type": "Build Guide",
        "product": product,
        "version": "",
        "category": "",
        "distros": [],
        "keywords": f"{product} s390x build guide",
        "search_text": search_text,
    }


def generate_chunks(wiki_dir: str | None = None) -> list[dict[str, Any]]:
    if wiki_dir is None:
        wiki_dir = clone_wiki()

    pages = read_wiki_pages(wiki_dir)
    all_chunks = []
    for page in pages:
        chunks = chunk_wiki_page(page)
        all_chunks.extend(chunks)

    logger.info("Generated %d chunks from %d wiki pages", len(all_chunks), len(pages))
    return all_chunks
