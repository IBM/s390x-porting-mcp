from __future__ import annotations

from utils.cli_utils import run_command


def skopeo_inspect(image: str, transport: str = "docker", raw: bool = False) -> dict:
    cmd = ["skopeo", "inspect"]
    if raw:
        cmd.append("--raw")
    cmd.append(f"{transport}://{image}")
    return run_command(cmd)


def skopeo_help() -> dict:
    return run_command(["skopeo", "--help"])
