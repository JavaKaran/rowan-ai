import logging
import os
import sys

import structlog


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)


def mask_value(value: str | None, visible_prefix: int = 3) -> str | None:
    if value is None:
        return None

    if len(value) <= visible_prefix:
        return "***"

    return f"{value[:visible_prefix]}***"
