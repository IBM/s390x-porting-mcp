"""Load structured fix entries from s390x-oss-kb repository."""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def load_fixes(fixes_dir: str) -> list[dict[str, Any]]:
    if not os.path.isdir(fixes_dir):
        logger.warning("Fixes directory not found: %s", fixes_dir)
        return []

    fixes = []
    for filename in sorted(os.listdir(fixes_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(fixes_dir, filename)
        with open(filepath) as f:
            fix = json.load(f)
        fixes.append(fix)

    logger.info("Loaded %d fix entries from %s", len(fixes), fixes_dir)
    return fixes


def load_packages(packages_path: str) -> dict[str, Any]:
    if not os.path.exists(packages_path):
        logger.warning("Packages index not found: %s", packages_path)
        return {}

    with open(packages_path) as f:
        packages = json.load(f)

    logger.info("Loaded %d packages from %s", len(packages), packages_path)
    return packages


def chunk_fix(fix: dict[str, Any]) -> list[dict[str, Any]]:
    chunks = []
    fix_id = fix.get("id", str(uuid.uuid4()))
    package = fix.get("package", "unknown")
    version = fix.get("version", "")
    category = fix.get("category", "")
    wiki_url = fix.get("wiki_url", "")

    summary = fix.get("fix_summary", "")
    root_cause = fix.get("root_cause", "")
    if summary:
        summary_text = f"{package} s390x fix: {summary}"
        if root_cause:
            summary_text += f"\n\nRoot cause: {root_cause}"

        search_text = f"{package} {version} {category} s390x fix {summary} {root_cause}"

        chunks.append({
            "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fix:{fix_id}:summary")),
            "chunk_uuid": f"fix_{fix_id}_summary",
            "url": wiki_url,
            "original_text": summary_text,
            "title": f"{package} - s390x Fix",
            "heading": summary[:100],
            "heading_path": [package, "Fix", summary[:60]],
            "doc_type": "Fix Entry",
            "product": package,
            "version": version,
            "category": category,
            "distros": [],
            "keywords": f"{package} {category} s390x fix port",
            "search_text": search_text,
        })

    fix_detail = fix.get("fix_detail", "")
    diff = fix.get("diff", "")
    if fix_detail or diff:
        detail_text = ""
        if fix_detail:
            detail_text += fix_detail
        if diff:
            detail_text += f"\n\nPatch:\n{diff}"

        search_text = f"{package} {version} {category} fix detail {fix_detail} {diff}"

        chunks.append({
            "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fix:{fix_id}:detail")),
            "chunk_uuid": f"fix_{fix_id}_detail",
            "url": wiki_url,
            "original_text": detail_text,
            "title": f"{package} - Fix Detail",
            "heading": f"Fix: {summary[:80]}",
            "heading_path": [package, "Fix Detail"],
            "doc_type": "Fix Entry",
            "product": package,
            "version": version,
            "category": category,
            "distros": [],
            "keywords": f"{package} {category} fix patch detail",
            "search_text": search_text,
        })

    return chunks


def generate_chunks(fixes_dir: str, packages_path: str | None = None) -> list[dict[str, Any]]:
    fixes = load_fixes(fixes_dir)

    packages = {}
    if packages_path:
        packages = load_packages(packages_path)

    all_chunks = []
    for fix in fixes:
        package = fix.get("package", "")
        if package in packages:
            pkg_data = packages[package]
            fix.setdefault("wiki_url", pkg_data.get("wiki_url", ""))

        chunks = chunk_fix(fix)
        all_chunks.extend(chunks)

    logger.info("Generated %d chunks from %d fixes", len(all_chunks), len(fixes))
    return all_chunks
