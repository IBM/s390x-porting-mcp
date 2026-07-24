from __future__ import annotations

from utils.cli_utils import run_command

ALLOWED_TRANSPORTS = frozenset({"docker"})


def skopeo_inspect(image: str, transport: str = "docker", raw: bool = False) -> dict:
    if transport not in ALLOWED_TRANSPORTS:
        return {
            "status": "error",
            "error": f"Unsupported transport: {transport}. Only 'docker' is supported.",
        }
    cmd = ["skopeo", "inspect"]
    if raw:
        cmd.append("--raw")
    cmd.append(f"{transport}://{image}")
    return run_command(cmd)


def skopeo_help() -> dict:
    return run_command(["skopeo", "--help"])
