from __future__ import annotations

import logging

import requests

from utils.config import DOCKER_REGISTRY_TIMEOUT, TARGET_ARCHITECTURES

logger = logging.getLogger(__name__)

DOCKER_AUTH_URL = "https://auth.docker.io/token"
DOCKER_REGISTRY_URL = "https://registry-1.docker.io/v2"

MANIFEST_ACCEPT_HEADERS = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


def _parse_image_spec(image: str) -> tuple[str, str]:
    if ":" in image:
        repo, tag = image.rsplit(":", 1)
    else:
        repo, tag = image, "latest"

    if "/" not in repo:
        repo = f"library/{repo}"

    return repo, tag


def _get_auth_token(repository: str) -> str:
    resp = requests.get(
        DOCKER_AUTH_URL,
        params={
            "service": "registry.docker.io",
            "scope": f"repository:{repository}:pull",
        },
        timeout=DOCKER_REGISTRY_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def _get_manifest(repository: str, tag: str, token: str) -> dict:
    resp = requests.get(
        f"{DOCKER_REGISTRY_URL}/{repository}/manifests/{tag}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": MANIFEST_ACCEPT_HEADERS,
        },
        timeout=DOCKER_REGISTRY_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_architectures(manifest: dict) -> list[str]:
    architectures = []

    if "manifests" in manifest:
        for entry in manifest["manifests"]:
            platform = entry.get("platform", {})
            arch = platform.get("architecture", "")
            if arch and arch != "unknown":
                os_name = platform.get("os", "linux")
                architectures.append(f"{os_name}/{arch}")
    else:
        config = manifest.get("config", {})
        if config:
            architectures.append("linux/amd64")

    return sorted(set(architectures))


def check_docker_image_architectures(image: str) -> dict:
    repository, tag = _parse_image_spec(image)

    try:
        token = _get_auth_token(repository)
        manifest = _get_manifest(repository, tag, token)
        architectures = _extract_architectures(manifest)

        arch_names = [a.split("/")[-1] for a in architectures]
        s390x_supported = "s390x" in arch_names

        return {
            "status": "success",
            "image": image,
            "repository": repository,
            "tag": tag,
            "architectures": architectures,
            "s390x_supported": s390x_supported,
            "message": (
                f"Image {image} {'supports' if s390x_supported else 'does NOT support'} s390x. "
                f"Available architectures: {', '.join(architectures)}"
            ),
        }
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {
                "status": "error",
                "image": image,
                "error": f"Image not found: {image}",
                "s390x_supported": False,
            }
        return {
            "status": "error",
            "image": image,
            "error": f"Registry API error: {e}",
            "s390x_supported": False,
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "image": image,
            "error": f"Network error: {e}",
            "s390x_supported": False,
        }
