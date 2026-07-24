from __future__ import annotations

import ipaddress
import re
import socket

from utils.cli_utils import run_command

ALLOWED_TRANSPORTS = frozenset({"docker"})

BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.internal",
})

BLOCKED_IP_NETWORKS = [
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv6Network("fe80::/10"),
]

BLOCKED_IPS = frozenset({
    ipaddress.IPv4Address("0.0.0.0"),
})


_IMAGE_REF_PATTERN = re.compile(
    r"^[a-zA-Z0-9]"
    r"[a-zA-Z0-9._/:@\[\]\-]*"
    r"$"
)


def _validate_image_format(image: str) -> str | None:
    if not image:
        return "Invalid image reference: image must not be empty."
    if not _IMAGE_REF_PATTERN.match(image):
        return f"Invalid image reference: {image!r} contains disallowed characters."
    return None


def _extract_registry_host(image: str) -> str | None:
    """Extract registry hostname from image reference. Returns None if implicit docker.io."""
    first_component = image.split("/")[0]
    # IPv6 address in brackets, e.g. [fe80::1]
    if first_component.startswith("["):
        if "]" in first_component:
            return first_component.split("]")[0].lstrip("[")
        return None
    # Check for host:port pattern where port is numeric (vs image:tag)
    has_port = ":" in first_component and first_component.rsplit(":", 1)[-1].isdigit()
    if "." in first_component or has_port or first_component == "localhost":
        return first_component.split(":")[0]
    return None


def _validate_image_host(image: str) -> str | None:
    """Validate registry host. Returns error message string if blocked, None if OK."""
    host = _extract_registry_host(image)
    if host is None:
        return None

    if host.lower() in BLOCKED_HOSTNAMES:
        return f"Registry host blocked: {host} is a known cloud metadata endpoint."

    try:
        addr = ipaddress.ip_address(host)
        if addr in BLOCKED_IPS:
            return f"Registry host blocked: {host} is not a valid registry address."
        for network in BLOCKED_IP_NETWORKS:
            if addr in network:
                return f"Registry host blocked: {host} is in a restricted IP range."
        return None
    except ValueError:
        pass

    try:
        addrinfos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return f"Registry host blocked: unable to resolve {host}."

    for family, _type, _proto, _canonname, sockaddr in addrinfos:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if addr in BLOCKED_IPS:
            return f"Registry host blocked: {host} resolves to a restricted address."
        for network in BLOCKED_IP_NETWORKS:
            if addr in network:
                return f"Registry host blocked: {host} resolves to a restricted IP range."

    return None


def skopeo_inspect(image: str, transport: str = "docker", raw: bool = False) -> dict:
    if transport not in ALLOWED_TRANSPORTS:
        return {
            "status": "error",
            "error": f"Unsupported transport: {transport}. Only 'docker' is supported.",
        }
    format_error = _validate_image_format(image)
    if format_error:
        return {"status": "error", "error": format_error}
    host_error = _validate_image_host(image)
    if host_error:
        return {"status": "error", "error": host_error}
    cmd = ["skopeo", "inspect"]
    if raw:
        cmd.append("--raw")
    cmd.append(f"{transport}://{image}")
    return run_command(cmd)


def skopeo_help() -> dict:
    return run_command(["skopeo", "--help"])
