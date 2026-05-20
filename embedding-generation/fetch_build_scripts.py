"""Fetch build scripts from linux-on-ibm-z/scripts repository."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import uuid
from typing import Any

logger = logging.getLogger(__name__)

SCRIPTS_REPO_URL = "https://github.com/linux-on-ibm-z/scripts.git"
SCRIPTS_BASE_URL = "https://github.com/linux-on-ibm-z/scripts/blob/master"


def clone_scripts(target_dir: str | None = None) -> str:
    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="s390x-scripts-")

    if os.path.exists(os.path.join(target_dir, ".git")):
        logger.info("Scripts already cloned at %s", target_dir)
        return target_dir

    logger.info("Cloning scripts from %s", SCRIPTS_REPO_URL)
    subprocess.run(
        ["git", "clone", "--depth", "1", SCRIPTS_REPO_URL, target_dir],
        check=True,
        capture_output=True,
    )
    return target_dir


def discover_scripts(scripts_dir: str) -> list[dict[str, str]]:
    scripts = []
    for pkg_name in sorted(os.listdir(scripts_dir)):
        pkg_dir = os.path.join(scripts_dir, pkg_name)
        if not os.path.isdir(pkg_dir) or pkg_name.startswith("."):
            continue

        for version in sorted(os.listdir(pkg_dir)):
            version_dir = os.path.join(pkg_dir, version)
            if not os.path.isdir(version_dir):
                continue

            for filename in os.listdir(version_dir):
                if filename.startswith("build_") and filename.endswith(".sh"):
                    filepath = os.path.join(version_dir, filename)
                    url = f"{SCRIPTS_BASE_URL}/{pkg_name}/{version}/{filename}"
                    scripts.append({
                        "package": pkg_name,
                        "version": version,
                        "filename": filename,
                        "filepath": filepath,
                        "url": url,
                    })

    logger.info("Discovered %d build scripts in %s", len(scripts), scripts_dir)
    return scripts


def _extract_distros(content: str) -> list[str]:
    distros = set()
    for match in re.finditer(r'(?:ubuntu|rhel|sles|suse)[\s-]*[\d.]+', content, re.IGNORECASE):
        distros.add(match.group(0).strip())
    return sorted(distros)


def _extract_functions(content: str) -> dict[str, str]:
    functions = {}
    func_pattern = re.compile(r'^function\s+(\w+)\s*\(\)\s*\{|^(\w+)\s*\(\)\s*\{', re.MULTILINE)
    matches = list(func_pattern.finditer(content))

    for i, match in enumerate(matches):
        func_name = match.group(1) or match.group(2)
        start = match.start()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)
        functions[func_name] = content[start:end].strip()

    return functions


def chunk_build_script(script_info: dict[str, str]) -> list[dict[str, Any]]:
    with open(script_info["filepath"]) as f:
        content = f.read()

    package = script_info["package"]
    version = script_info["version"]
    url = script_info["url"]
    distros = _extract_distros(content)

    functions = _extract_functions(content)
    chunks = []

    if not functions:
        search_text = f"{package} {version} s390x build script {content[:1000]}"
        chunks.append({
            "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"script:{url}")),
            "chunk_uuid": f"script_{re.sub(r'[^a-z0-9]', '_', package.lower())}_{version.replace('.', '_')}",
            "url": url,
            "original_text": content[:3000],
            "title": f"{package} {version} Build Script",
            "heading": "Build Script",
            "heading_path": [package, version, "Build Script"],
            "doc_type": "Build Script",
            "product": package,
            "version": version,
            "category": "",
            "distros": distros,
            "keywords": f"{package} build script s390x {' '.join(distros)}",
            "search_text": search_text,
        })
    else:
        for func_name, func_body in functions.items():
            search_text = f"{package} {version} s390x {func_name} {func_body[:800]}"
            chunks.append({
                "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"script:{url}:{func_name}")),
                "chunk_uuid": f"script_{re.sub(r'[^a-z0-9]', '_', package.lower())}_{version.replace('.', '_')}_{func_name}",
                "url": url,
                "original_text": func_body[:2000],
                "title": f"{package} {version} Build Script",
                "heading": func_name,
                "heading_path": [package, version, func_name],
                "doc_type": "Build Script",
                "product": package,
                "version": version,
                "category": "",
                "distros": distros,
                "keywords": f"{package} build script {func_name} s390x",
                "search_text": search_text,
            })

    return chunks


def build_script_index(scripts_dir: str) -> dict[str, Any]:
    scripts = discover_scripts(scripts_dir)
    index: dict[str, Any] = {}

    for script in scripts:
        pkg = script["package"]
        ver = script["version"]

        if pkg not in index:
            index[pkg] = {"wiki_url": "", "versions": {}}

        with open(script["filepath"]) as f:
            content = f.read()

        index[pkg]["versions"][ver] = {
            "script_url": script["url"],
            "distros": _extract_distros(content),
        }

    return index


def generate_chunks(scripts_dir: str | None = None) -> list[dict[str, Any]]:
    if scripts_dir is None:
        scripts_dir = clone_scripts()

    scripts = discover_scripts(scripts_dir)
    all_chunks = []
    for script in scripts:
        chunks = chunk_build_script(script)
        all_chunks.extend(chunks)

    logger.info("Generated %d chunks from %d scripts", len(all_chunks), len(scripts))
    return all_chunks
