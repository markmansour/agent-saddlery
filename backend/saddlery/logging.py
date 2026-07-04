"""Structured logging configuration for Agent Saddlery.

Uses structlog for context binding and structured output.
Logs to file by default; respects environment variables for format and output.
"""

from __future__ import annotations

import os

import structlog


def configure_logging() -> None:
    """Configure structlog for file and console output.

    Environment variables:
    - SADDLERY_LOG_FORMAT: 'json' (default) or 'dev' for format
    - SADDLERY_LOG_OUTPUT: 'file' (default) or 'console'
    - SADDLERY_LOG_FILE: path to log file (default: 'core.log')
    """
    log_format = os.getenv("SADDLERY_LOG_FORMAT", "json").lower()
    log_output = os.getenv("SADDLERY_LOG_OUTPUT", "file").lower()
    log_file = os.getenv("SADDLERY_LOG_FILE", "core.log")

    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Set up logger: file (default) or console
    if log_output == "console":
        logger_factory = structlog.PrintLoggerFactory()
    else:  # "file" (default)
        file_out = open(log_file, "a")  # noqa: SIM115
        logger_factory = structlog.PrintLoggerFactory(file=file_out)

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )
