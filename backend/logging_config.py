"""Structured logging configuration (P3.2).

Bridges the stdlib logging used across the codebase into structlog's
JSON renderer. Call `configure_logging()` once at startup — every
`logging.getLogger("coupletrip")` call site then emits structured
JSON logs with no per-file changes.
"""

import logging
import sys

import structlog


def configure_logging(json_logs: bool = True) -> None:
    """Configure structlog to render JSON (or pretty console in dev).

    Sets up a stdlib-to-structlog bridge so existing
    `logger = logging.getLogger("coupletrip")` call sites automatically
    produce structured output without code changes.
    """
    # Shared processors for both structlog and stdlib-bridged logs
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            (
                structlog.processors.JSONRenderer()
                if json_logs
                else structlog.dev.ConsoleRenderer()
            ),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Avoid duplicate handlers if configure_logging is called again
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "_structlog", False)
        for h in root.handlers
    ):
        handler._structlog = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Route coupletrip logs through the same formatter
    coupletrip_logger = logging.getLogger("coupletrip")
    coupletrip_logger.handlers.clear()
    coupletrip_logger.addHandler(handler)
    coupletrip_logger.setLevel(logging.INFO)
    coupletrip_logger.propagate = False
