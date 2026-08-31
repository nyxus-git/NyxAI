"""
core/logging.py

Structured logging for NyxAI using structlog.

All modules in NyxAI should import their logger from here:

    from core.logging import get_logger
    logger = get_logger(__name__)

This ensures consistent, structured, JSON-compatible log output
across every component of the system.
"""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structlog and the standard library logging integration.

    Call this once at application startup (inside FastAPI lifespan).

    Args:
        log_level: Logging level string. One of DEBUG, INFO, WARNING, ERROR.
    """
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_int,
    )

    # Shared processors for both dev (pretty) and prod (JSON) modes
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # In production this would be JSONRenderer; keeping ConsoleRenderer
        # for readability during development. Switch to JSONRenderer for
        # systemd/log-aggregation environments.
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level_int)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a named structlog logger for a module.

    Usage:
        logger = get_logger(__name__)
        logger.info("server_started", host="127.0.0.1", port=8000)

    Args:
        name: Module name, typically __name__.

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
