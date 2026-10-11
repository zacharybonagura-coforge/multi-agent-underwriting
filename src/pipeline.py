"""Underwriting pipeline. Intake, enrichment, risk scoring, then recommendation."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
from settings.config import Settings
from store.base import Store

settings = Settings.from_env()
_MAX_RETRIES = settings.max_retries
_REVIEW_FILE = settings.reviews_path

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
    store: Store,
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
            return _review(_stop(), "intake failed after retries")
        enrich_input = _enrichment_input(intake)
        enrichment = _run_agent(
            tracer,
            wrapped,
            "enrichment",
            enrich_input,
            lambda: enrichment_agent(enrich_input, wrapped, store),
            lambda result: result.message.model_dump(mode="json"),
        )
        if enrichment is None:
            return _review(_stop(intake), "enrichment failed after retries")
        if _enrichment_failed(enrichment.message):
            print("Enrichment failed. This application must go to human review.")
            return _review(_stop(intake, enrichment), "enrichment record is incomplete")
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
            return _review(_stop(intake, enrichment), "risk scoring failed after retries")
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
            return _review(_stop(intake, enrichment, risk), "recommendation failed after retries")
        
        decision = _final_decision(recommendation)
        result = PipelineResult(
            final_decision=decision,
            intake=intake,
            enrichment=enrichment,
            risk=risk,
            recommendation=recommendation,
        )

        if decision == "escalate":
            reason = recommendation.message.rationale or "recommendation did not produce a decision"
            return _review(result, reason)

        return result


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
    """Call ``agent`` once, then retry up to three times with the previous error appended."""
    for attempt in range(_MAX_RETRIES+1):
        try:
            return _traced_call(tracer, agent, received, call, output_of)
        except _AGENT_ERRORS as exc:
            if attempt == _MAX_RETRIES:
                print(f"{agent} failed after {_MAX_RETRIES} retries. This application must go to human review.")
                return None
            model.remember(exc)
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


def _review(result: PipelineResult, reason: str) -> PipelineResult:
    """Append an escalated case to the human-review file."""
    _REVIEW_FILE.parent.mkdir(exist_ok=True)
    intake = None
    if result.intake is not None:
        intake = result.intake.message.model_dump(mode="json")
        intake["missing_fields"] = result.intake.missing_fields
    record = {
        "reviewed_at": datetime.now(UTC).isoformat(),
        "reason": reason,
        "final_decision": result.final_decision,
        "intake": intake,
        "enrichment": None if result.enrichment is None else result.enrichment.message.model_dump(mode="json"),
        "risk": None if result.risk is None else result.risk.message.model_dump(mode="json"),
        "recommendation": None if result.recommendation is None else result.recommendation.message.model_dump(mode="json"),
    }
    with _REVIEW_FILE.open("a") as review_file:
        review_file.write(json.dumps(record) + "\n")
    return result


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
