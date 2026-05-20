import logging
import subprocess

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120


def run_command(
    cmd: list[str],
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | None = None,
) -> dict:
    logger.info("Running command: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": f"Command timed out after {timeout}s",
            "cmd": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error": f"Command not found: {cmd[0]}",
            "cmd": " ".join(cmd),
        }
