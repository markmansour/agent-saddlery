"""Structured logging configuration for Agent Saddlery.

Uses structlog for context binding and structured output.
Logs go to stderr (safe for subprocess communication where stdout = event JSON).
Respects environment variables for format and file output.
"""

from __future__ import annotations

import os
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog to write logs to stderr.

    This ensures stdout remains pure AG-UI event JSON for subprocess communication.

    Environment variables:
    - SADDLERY_LOG_FORMAT: 'json' (default) or 'dev' for format
    - SADDLERY_LOG_FILE: if set, also write logs to this file (in addition to stderr)

    Logs always go to stderr by default. If SADDLERY_LOG_FILE is set, also write to file.
    """
    log_format = os.getenv("SADDLERY_LOG_FORMAT", "json").lower()
    log_file = os.getenv("SADDLERY_LOG_FILE", "")

    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Logs go to stderr by default (safe for subprocess communication)
    # If SADDLERY_LOG_FILE is set, also write to file
    if log_file:
        file_out = open(log_file, "a")  # noqa: SIM115

        class DualWriter:
            def write(self, msg: str) -> None:
                sys.stderr.write(msg)
                file_out.write(msg)
                file_out.flush()

            def flush(self) -> None:
                sys.stderr.flush()
                file_out.flush()

        logger_factory = structlog.PrintLoggerFactory(file=sys.stderr)
    else:
        logger_factory = structlog.PrintLoggerFactory(file=sys.stderr)

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )
