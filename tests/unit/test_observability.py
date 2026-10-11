"""Unit tests for span logging."""

import logging
from types import SimpleNamespace
from typing import cast

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from observability import LoggingSpanExporter, configure_tracing, traced_step


def _span(**fields: object) -> ReadableSpan:
    return cast(ReadableSpan, SimpleNamespace(**fields))


class _Tokens:
    input_tokens = 3
    output_tokens = 5


def test_export_logs_a_span_without_input(caplog) -> None:
    caplog.set_level(logging.INFO, logger="underwriting")
    span = _span(name="underwriting", attributes={}, start_time=1_000_000, end_time=4_000_000)
    result = LoggingSpanExporter().export([span])
    assert result is SpanExportResult.SUCCESS
    assert "agent=underwriting" in caplog.text
    assert "duration_ms=3.000" in caplog.text


def test_export_logs_a_span_with_tokens(caplog) -> None:
    caplog.set_level(logging.INFO, logger="underwriting")
    span = _span(
        name="intake",
        attributes={
            "duration_ms": 12.5,
            "input_tokens": 10,
            "output_tokens": 4,
            "input": "{}",
            "output": "{}",
        },
        start_time=None,
        end_time=None,
    )
    LoggingSpanExporter().export([span])
    assert "agent=intake" in caplog.text
    assert "input_tokens=10" in caplog.text
    assert "output_tokens=4" in caplog.text


def test_export_uses_zero_when_timestamps_are_missing(caplog) -> None:
    caplog.set_level(logging.INFO, logger="underwriting")
    span = _span(name="underwriting", attributes=None, start_time=None, end_time=None)
    LoggingSpanExporter().export([span])
    assert "duration_ms=0.000" in caplog.text


def test_shutdown_returns_none() -> None:
    LoggingSpanExporter().shutdown()


def test_traced_step_records_tokens_and_returns_the_result() -> None:
    tracer = configure_tracing()
    result = traced_step(
        tracer,
        "intake",
        {"product": "auto"},
        lambda: _Tokens(),
        lambda value: {"ok": True},
    )
    assert result is not None
    assert result.input_tokens == 3
    assert result.output_tokens == 5