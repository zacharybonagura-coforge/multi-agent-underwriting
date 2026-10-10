"""Underwriting pipeline. Intake, enrichment, risk scoring, then recommendation."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import InvalidOperation
from typing import Any, Protocol

import httpx
from opentelemetry import trace

from agents.enrichment import EnrichmentMessage, EnrichmentResult, enrichment_agent
from agents.intake import IntakeResult, intake_agent
from agents.recommendation import RecommendationResult, recommendation_agent
from agents.risk import RiskResult, risk_agent
from model.base import Generation, ModelAdapter, ModelTimeoutError
from observability import configure_tracing


@dataclass(frozen=True)
class PipelineResult:
    """Results for one application."""

    final_decision: str
    intake: IntakeResult | None = None
    enrichment: EnrichmentResult | None = None
    risk: RiskResult | None = None
    recommendation: RecommendationResult | None = None


class _ErrorPrompt:
    """Append the previous agent error to the next prompt."""

    def __init__(self, model: ModelAdapter) -> None:
        self._model = model
        self._error: str | None = None
        self.provider = model.provider
        self.model_id = model.model_id

    def remember(self, error: Exception) -> None:
        """Keep ``error`` for the retry prompt."""
        self._error = f"{type(error).__name__}: {error}"

    def generate(self, prompt: str) -> Generation:
        """Generate from ``prompt``, including the last error on a retry."""
        if self._error is not None:
            prompt = (
                f"{prompt}\n\n"
                f"Your previous response failed with this error: {self._error}\n"
                "Correct that error and reply with JSON only."
            )
            self._error = None
        return self._model.generate(prompt)


def run(
    raw_application: dict[str, Any],
    model: ModelAdapter,
    tracer: trace.Tracer | None = None,
) -> PipelineResult:
    """Run intake, enrichment, risk scoring, and recommendation."""
    tracer = tracer or configure_tracing()
    wrapped = _ErrorPrompt(model)
    with tracer.start_as_current_span("underwriting"):
        intake = _run_agent(
            tracer,
            wrapped,
            "intake",
            raw_application,
            lambda: intake_agent(raw_application, wrapped),
            lambda result: {
                "message": result.message.model_dump(mode="json"),
                "missing_fields": result.missing_fields,
            },
        )
        if intake is None:
            return _stop()
        enrich_input = _enrichment_input(intake)
        enrichment = _run_agent(
            tracer,
            wrapped,
            "enrichment",
            enrich_input,
            lambda: enrichment_agent(enrich_input, wrapped),
            lambda result: result.message.model_dump(mode="json"),
        )
        if enrichment is None:
            return _stop(intake)
        if _enrichment_failed(enrichment.message):
            print("Enrichment failed. This application must go to human review.")
            return _stop(intake, enrichment)
        risk_input = _risk_input(intake, enrichment)
        risk = _run_agent(
            tracer,
            wrapped,
            "risk",
            risk_input,
            lambda: risk_agent(risk_input, wrapped),
            lambda result: result.message.model_dump(mode="json"),
        )
        if risk is None:
            return _stop(intake, enrichment)
        recommend_input = _recommendation_input(risk)
        recommendation = _run_agent(
            tracer,
            wrapped,
            "recommendation",
            recommend_input,
            lambda: recommendation_agent(recommend_input, wrapped),
            lambda result: result.message.model_dump(mode="json"),
        )
        if recommendation is None:
            return _stop(intake, enrichment, risk)

        return PipelineResult(
            final_decision=_final_decision(recommendation),
            intake=intake,
            enrichment=enrichment,
            risk=risk,
            recommendation=recommendation,
        )


class _TracedResult(Protocol):
    """Agent result that carries token counts for the span."""

    @property
    def input_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...


_AGENT_ERRORS = (ValueError, ModelTimeoutError, InvalidOperation, httpx.HTTPError)


def _run_agent[ResultT: _TracedResult](
    tracer: trace.Tracer,
    model: _ErrorPrompt,
    agent: str,
    received: Any,
    call: Callable[[], ResultT],
    output_of: Callable[[ResultT], Any],
) -> ResultT | None:
    """Call ``agent`` once, then once more with the error appended to the prompt."""
    try:
        return _traced_call(tracer, agent, received, call, output_of)
    except _AGENT_ERRORS as exc:
        model.remember(exc)
        try:
            return _traced_call(tracer, agent, received, call, output_of)
        except _AGENT_ERRORS:
            print(f"{agent} failed after one retry. This application must go to human review.")
            return None


def _traced_call[ResultT: _TracedResult](
    tracer: trace.Tracer,
    agent: str,
    received: Any,
    call: Callable[[], ResultT],
    output_of: Callable[[ResultT], Any],
) -> ResultT:
    """Run ``call`` and record the span, including a failed attempt."""
    with tracer.start_as_current_span(agent) as span:
        span.set_attribute("agent", agent)
        span.set_attribute("input", json.dumps(received, default=str))
        started = time.perf_counter()
        try:
            result = call()
        except Exception as exc:
            span.set_attribute("output", json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
            span.set_attribute("input_tokens", 0)
            span.set_attribute("output_tokens", 0)
            raise
        else:
            span.set_attribute("output", json.dumps(output_of(result), default=str))
            span.set_attribute("input_tokens", result.input_tokens)
            span.set_attribute("output_tokens", result.output_tokens)
            return result
        finally:
            span.set_attribute("duration_ms", round((time.perf_counter() - started) * 1000, 3))


def _stop(
    intake: IntakeResult | None = None,
    enrichment: EnrichmentResult | None = None,
    risk: RiskResult | None = None,
) -> PipelineResult:
    """Keep finished agents and escalate the rest."""
    return PipelineResult(
        final_decision="escalate",
        intake=intake,
        enrichment=enrichment,
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


def _recommendation_input(risk: RiskResult) -> dict[str, Any]:
    return {
        "risk_score": risk.message.risk_score,
        "risk_factors": risk.message.risk_factors,
        "tier": risk.message.tier,
    }


def _final_decision(recommendation: RecommendationResult) -> str:
    """Use the recommendation decision, or escalate when it is missing."""
    if recommendation.message.decision is None:
        return "escalate"
    return recommendation.message.decision


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
    if result.intake is not None:
        print(result.intake.message.model_dump(mode="json"))
        print("missing:", result.intake.missing_fields)
    if result.enrichment is not None:
        print(result.enrichment.message.model_dump(mode="json"))
    if result.risk is not None:
        print(result.risk.message.model_dump(mode="json"))
    if result.recommendation is not None:
        print(result.recommendation.message.model_dump(mode="json"))
    print("final_decision:", result.final_decision)