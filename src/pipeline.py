"""Underwriting pipeline. Intake, enrichment, then risk scoring."""

from dataclasses import dataclass
from typing import Any

from opentelemetry import trace

from agents.enrichment import EnrichmentMessage, EnrichmentResult, enrichment_agent
from agents.intake import IntakeResult, intake_agent
from agents.risk import RiskResult, risk_agent
from model.base import ModelAdapter
from observability import configure_tracing, traced_step


@dataclass(frozen=True)
class PipelineResult:
    """Results for one application."""

    intake: IntakeResult
    enrichment: EnrichmentResult
    human_review: bool
    risk: RiskResult | None = None


def run(
    raw_application: dict[str, Any],
    model: ModelAdapter,
    tracer: trace.Tracer | None = None,
) -> PipelineResult:
    """Run intake, enrichment, and risk scoring."""
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
        if _enrichment_failed(enrichment.message):
            print("Enrichment failed. This application must go to human review.")
            return PipelineResult(intake=intake, enrichment=enrichment, human_review=True)
        risk_input = _risk_input(intake, enrichment)
        risk = traced_step(
            tracer,
            "risk",
            risk_input,
            lambda: risk_agent(risk_input, model),
            lambda result: result.message.model_dump(mode="json"),
        )
        return PipelineResult(
            intake=intake,
            enrichment=enrichment,
            human_review=False,
            risk=risk,
        )


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


def _risk_input(intake: IntakeResult, enrichment: EnrichmentResult) -> dict[str, Any]:
    return {
        "product": intake.message.product,
        "coverage_amount": intake.message.coverage_amount,
        "stated_income": intake.message.stated_income,
        "missing_fields": intake.missing_fields,
        "credit_band": enrichment.message.credit_band,
        "prior_claims_count": enrichment.message.prior_claims_count,
        "asset_facts": enrichment.message.asset_facts,
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
    if result.risk is not None:
        print(result.risk.message.model_dump(mode="json"))