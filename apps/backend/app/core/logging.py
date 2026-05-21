from __future__ import annotations

import logging
import sys

import structlog
<<<<<<< HEAD
from opentelemetry import trace


def add_opentelemetry_spans(logger: logging.Logger, log_method: str, event_dict: dict) -> dict:
    span = trace.get_current_span()
    if not span.is_recording():
        return event_dict

    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = f"{ctx.trace_id:032x}"
        event_dict["span_id"] = f"{ctx.span_id:016x}"
    return event_dict
=======
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818


def configure_logging(level: str) -> None:
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
<<<<<<< HEAD
            add_opentelemetry_spans,
=======
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
