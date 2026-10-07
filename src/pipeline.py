"""Underwriting pipeline. Intake is the only connected agent."""

from typing import Any

from opentelemetry import trace

from agents.intake import IntakeResult, intake_agent
from model.base import ModelAdapter
from observability import configure_tracing, traced_step


def run(
    raw_application: dict[str, Any],
    model: ModelAdapter,
    tracer: trace.Tracer | None = None,
) -> IntakeResult:
    """Normalize one application and trace the intake step."""
    tracer = tracer or configure_tracing()
    with tracer.start_as_current_span("underwriting"):
        return traced_step(
            tracer,
            "intake",
            raw_application,
            lambda: intake_agent(raw_application, model),
            lambda result: {
                "message": result.message.model_dump(mode="json"),
                "missing_fields": result.missing_fields,
            },
        )


if __name__ == "__main__":
    from model.ollama import OllamaAdapter

    application = {
        "applicant_name": "Ada Lovelace",
        "date_of_birth": "1815-12-10",
        "address": "12 St James Square, London",
        "product": "AUTO",
        "coverage_amount": "50000",
        "stated_income": "120000",
    }
    result = run(application, OllamaAdapter())
    print(result.message.model_dump(mode="json"))
    print("missing:", result.missing_fields)