"""
utils/logging.py

Structured logging setup using structlog + JSON for production observability.

Integrates nicely with LangSmith when enabled.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog


def setup_logging(observability_cfg: Dict[str, Any], logs_dir: Path) -> None:
    log_level = observability_cfg.get("log_level", "INFO").upper()
    json_logs = observability_cfg.get("log_structured", True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level, logging.INFO),
    )

    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also log to file
    logs_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(logs_dir / "daily_x_posts.log")
    file_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(file_handler)
