from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_invocation_reason(tool: str, reason: str | None = None, args: dict | None = None) -> None:
    if reason:
        logger.info("Tool %s invoked: %s (args: %s)", tool, reason, args)
    else:
        logger.info("Tool %s invoked (args: %s)", tool, args)
