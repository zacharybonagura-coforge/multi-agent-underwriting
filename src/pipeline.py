"""Underwriting pipeline. Intake hands off to enrichment."""

from dataclasses import dataclass
from typing import Any

from opentelemetry import trace

from agents.enrichment import EnrichmentMessage, EnrichmentResult, enrichment_agent
from agents.intake import IntakeResult, intake_agent
from model.base import ModelAdapter
from observability import configure_tracing, traced_step


@dataclass(frozen=True)
class PipelineResult:
    """Intake and enrichment results for one application."""

    intake: IntakeResult
    enrichment: EnrichmentResult
    human_review: bool


def run(
    raw_application: dict[str, Any],
    model: ModelAdapter,
    tracer: trace.Tracer | None = None,
) -> PipelineResult:
    """Run intake and enrichment, and flag a case enrichment could not complete."""
    tracer = tracer or configure_tracing()
    with tracer.start_as_current_span("underwriting"):
        intake = traced_step(
            tracer,
            "intake",
            raw_application,
            lambda: intake_agent(raw_application, model),
            lambda result: {
                "message": result.message.model_dump(mode="json"),
                "missing_fields": result.missing_fields,
            },
        )
        enrich_input = _enrichment_input(intake)
        enrichment = traced_step(
            tracer,
            "enrichment",
            enrich_input,
            lambda: enrichment_agent(enrich_input, model),
            lambda result: result.message.model_dump(mode="json"),
        )
        human_review = _enrichment_failed(enrichment.message)
        if human_review:
            print("Enrichment failed. This application must go to human review.")
        return PipelineResult(intake=intake, enrichment=enrichment, human_review=human_review)


def _enrichment_input(intake: IntakeResult) -> dict[str, Any]:
    message = intake.message
    birth = message.date_of_birth.isoformat() if message.date_of_birth else None
    return {
        "applicant_name": message.applicant_name,
        "date_of_birth": birth,
        "address": message.address,
        "product": message.product,
        "missing_fields": intake.missing_fields,
    }


def _enrichment_failed(message: EnrichmentMessage) -> bool:
    return (
        message.credit_band is None
        or message.prior_claims_count is None
        or message.asset_facts is None
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
    print(result.intake.message.model_dump(mode="json"))
    print("missing:", result.intake.missing_fields)
    print(result.enrichment.message.model_dump(mode="json"))