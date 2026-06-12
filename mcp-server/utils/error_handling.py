from __future__ import annotations

import logging
import traceback

logger = logging.getLogger(__name__)


def format_tool_error(tool: str, exc: Exception, args: dict | None = None) -> dict:
    logger.error("Tool %s failed with args %s: %s", tool, args, exc)
    logger.debug(traceback.format_exc())
    return {
        "status": "error",
        "tool": tool,
        "error": str(exc),
        "error_type": type(exc).__name__,
    }
