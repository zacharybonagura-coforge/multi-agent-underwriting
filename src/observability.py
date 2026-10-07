"""OpenTelemetry tracing for one agent step."""

import json
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

logger = logging.getLogger("underwriting")


class LoggingSpanExporter(SpanExporter):
    """Write each finished span as an INFO log line."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            attrs = span.attributes or {}
            if "input" not in attrs:
                start = span.start_time or 0
                end = span.end_time or start
                logger.info("agent=%s duration_ms=%.3f", span.name, (end - start) / 1_000_000)
                continue
            logger.info(
                "agent=%s duration_ms=%s input_tokens=%s output_tokens=%s input=%s output=%s",
                span.name,
                attrs["duration_ms"],
                attrs["input_tokens"],
                attrs["output_tokens"],
                attrs["input"],
                attrs["output"],
            )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """None here since we do not need close any file or network client"""
        return


def configure_tracing() -> trace.Tracer:
    """Print each finished span to the terminal."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    provider = TracerProvider(resource=Resource.create({"service.name": "underwriting"}))
    provider.add_span_processor(SimpleSpanProcessor(LoggingSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("underwriting")


def traced_step(
    tracer: trace.Tracer,
    agent: str,
    received: Any,
    call: Callable[[], Any],
    output_of: Callable[[Any], Any],
) -> Any:
    """Run ``call`` and record what the lab requires on the span."""
    with tracer.start_as_current_span(agent) as span:
        span.set_attribute("agent", agent)
        span.set_attribute("input", json.dumps(received, default=str))
        started = time.perf_counter()
        result = call()
        duration_ms = (time.perf_counter() - started) * 1000
        span.set_attribute("output", json.dumps(output_of(result), default=str))
        span.set_attribute("duration_ms", round(duration_ms, 3))
        span.set_attribute("input_tokens", result.input_tokens)
        span.set_attribute("output_tokens", result.output_tokens)
        return result