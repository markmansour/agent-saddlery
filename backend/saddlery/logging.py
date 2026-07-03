"""Structured logging configuration for Agent Saddlery.

Uses structlog for context binding and structured output.
Supports both human-readable console (dev) and JSON (prod) formats.
"""

from __future__ import annotations

import os
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog with environment-appropriate output format.

    Respects SADDLERY_LOG_FORMAT env var:
    - 'json': JSON output (suitable for production/aggregation)
    - 'dev': Human-readable console output (default)
    """
    log_format = os.getenv("SADDLERY_LOG_FORMAT", "dev").lower()

    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()),
            ]
        )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
