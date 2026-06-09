from __future__ import annotations

import json
import logging
import os
import re

from utils.config import SCRIPT_INDEX_PATH

logger = logging.getLogger(__name__)

_script_index: dict | None = None


def _load_script_index() -> dict:
    global _script_index
    if _script_index is not None:
        return _script_index

    if not os.path.exists(SCRIPT_INDEX_PATH):
        logger.warning("Script index not found at %s", SCRIPT_INDEX_PATH)
        _script_index = {}
        return _script_index

    with open(SCRIPT_INDEX_PATH) as f:
        _script_index = json.load(f)

    logger.info("Loaded script index with %d packages", len(_script_index))
    return _script_index


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _find_package(software: str) -> tuple[str, dict] | None:
    index = _load_script_index()
    normalized = _normalize_name(software)

    for pkg_name, pkg_data in index.items():
        if _normalize_name(pkg_name) == normalized:
            return pkg_name, pkg_data

    for pkg_name, pkg_data in index.items():
        if normalized in _normalize_name(pkg_name) or _normalize_name(pkg_name) in normalized:
            return pkg_name, pkg_data

    return None


def _distro_matches(ver_data: dict, distro: str) -> bool:
    distro_lower = distro.lower()
    return any(distro_lower in d.lower() for d in ver_data.get("distros", []))


def _find_version(
    pkg_data: dict,
    version: str | None = None,
    distro: str | None = None,
) -> tuple[str, dict] | None:
    versions = pkg_data.get("versions", {})
    if not versions:
        return None

    if version:
        if version in versions:
            return version, versions[version]
        for v, data in versions.items():
            if v.startswith(version):
                return v, data
        return None

    if distro:
        sorted_versions = sorted(versions.keys(), reverse=True)
        for v in sorted_versions:
            if _distro_matches(versions[v], distro):
                return v, versions[v]

    sorted_versions = sorted(versions.keys(), reverse=True)
    latest = sorted_versions[0]
    return latest, versions[latest]


def find_and_return_script(
    software: str,
    version: str | None = None,
    distro: str | None = None,
) -> dict:
    match = _find_package(software)
    if match is None:
        try:
            from utils.kb_search_utils import search_knowledge_base
            kb_results = search_knowledge_base(f"build {software} s390x", k=3)
            if kb_results and isinstance(kb_results, list) and len(kb_results) > 0:
                return {
                    "status": "not_found_in_scripts",
                    "message": f"No build script found for '{software}' in the scripts repository. "
                               f"Found related build guides in the knowledge base.",
                    "related_guides": kb_results,
                }
        except Exception:
            logger.debug("KB search fallback failed for '%s'", software, exc_info=True)

        return {
            "status": "not_found",
            "message": f"No build script or guide found for '{software}'.",
        }

    pkg_name, pkg_data = match
    version_match = _find_version(pkg_data, version, distro)

    if version_match is None:
        available = list(pkg_data.get("versions", {}).keys())
        return {
            "status": "version_not_found",
            "package": pkg_name,
            "message": f"Version '{version}' not found for {pkg_name}.",
            "available_versions": sorted(available, reverse=True),
        }

    ver, ver_data = version_match
    script_url = ver_data.get("script_url", "")
    wiki_url = pkg_data.get("wiki_url", "")

    return {
        "status": "found",
        "package": pkg_name,
        "version": ver,
        "script_url": script_url,
        "wiki_url": wiki_url,
        "distros": ver_data.get("distros", []),
        "script_content": ver_data.get("script_content", ""),
    }
