"""Unit tests for the underwriting pipeline."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

import pipeline
from model.base import Generation, ModelTimeoutError
from observability import configure_tracing

_INTAKE = json.dumps({
    "applicant_name": "Ada Lovelace",
    "applicant_email": "ada.lovelace@coforge.com",
    "date_of_birth": "1815-12-10",
    "address": "12 St James's Square, London SW1Y 4LE, United Kingdom",
    "product": "auto",
    "coverage_amount": 16000.46,
    "stated_income": 120000,
})
_ENRICH = json.dumps({
    "credit_band": "good",
    "prior_claims_count": 1,
    "asset_facts": "2018 Honda Civic",
})
_RISK_LOW = json.dumps({"risk_score": 20, "risk_factors": ["credit_band"], "tier": "low"})
_RISK_HIGH = json.dumps({"risk_score": 80, "risk_factors": ["credit_band"], "tier": "high"})
_RISK_MED = json.dumps({"risk_score": 45, "risk_factors": ["credit_band"], "tier": "medium"})
_APPROVE = json.dumps({"decision": "approve", "rationale": "the tier is low"})
_DENY = json.dumps({"decision": "deny", "rationale": "the tier is high"})
_ESCALATE = json.dumps({"decision": "escalate", "rationale": "the tier is medium"})
_NO_DECISION = json.dumps({"decision": None, "rationale": None})


def _gen(text: str) -> Generation:
    return Generation(text=text, input_tokens=1, output_tokens=1)


def _agent(prompt: str) -> str:
    if prompt.startswith("Normalize"):
        return "intake"
    if prompt.startswith("Add underwriting"):
        return "enrichment"
    if prompt.startswith("Score"):
        return "risk"
    if prompt.startswith("Decide"):
        return "recommendation"
    raise AssertionError(prompt)


class FakeModel:
    provider = "fake"
    model_id = "fake"

    def __init__(self, **queues: Sequence[Generation | BaseException]) -> None:
        defaults: dict[str, list[Generation | BaseException]] = {
            "intake": [_gen(_INTAKE)],
            "enrichment": [_gen(_ENRICH)],
            "risk": [_gen(_RISK_LOW)],
            "recommendation": [_gen(_APPROVE)],
        }
        self._queues = {name: list(queues.get(name, items)) for name, items in defaults.items()}
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> Generation:
        self.prompts.append(prompt)
        item = self._queues[_agent(prompt)].pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class MemoryStore:
    def load(self) -> list[dict[str, Any]]:
        return [{
            "applicant_email": "ada.lovelace@coforge.com",
            "product": "auto",
            "credit_file": "good",
            "claims": ["2019 collision"],
            "asset": "2018 Honda Civic",
        }]

    def save(self, payload: Any) -> None:
        return None


@pytest.fixture
def reviews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "human-review.jsonl"
    monkeypatch.setattr(pipeline, "_REVIEW_FILE", path)
    monkeypatch.setattr(pipeline, "_MAX_RETRIES", 1)
    return path


def _raw() -> dict[str, Any]:
    return {
        "applicant_name": "Ada Lovelace",
        "applicant_email": "ada.lovelace@coforge.com",
        "date_of_birth": "1815-12-10",
        "address": "12 St James's Square, London SW1Y 4LE, United Kingdom",
        "product": "auto",
        "coverage_amount": "16000.456",
        "stated_income": "120000",
    }


def _run(model: FakeModel, tracer: Any = ...) -> pipeline.PipelineResult:
    kwargs: dict[str, Any] = {"raw_application": _raw(), "model": model, "store": MemoryStore()}
    if tracer is not ...:
        kwargs["tracer"] = tracer
    return pipeline.run(**kwargs)


def _review_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_run_approves_a_low_risk_application(reviews: Path) -> None:
    result = _run(FakeModel(), configure_tracing())
    assert result.final_decision == "approve"
    assert result.intake is not None
    assert result.intake.message.applicant_email == "ada.lovelace@coforge.com"
    assert result.enrichment is not None
    assert result.enrichment.message.credit_band == "good"
    assert result.risk is not None
    assert result.risk.message.tier == "low"
    assert result.recommendation is not None
    assert result.recommendation.message.decision == "approve"
    assert _review_rows(reviews) == []


def test_run_denies_a_high_risk_application(reviews: Path) -> None:
    model = FakeModel(risk=[_gen(_RISK_HIGH)], recommendation=[_gen(_DENY)])
    result = _run(model, configure_tracing())
    assert result.final_decision == "deny"
    assert _review_rows(reviews) == []


def test_run_uses_configure_tracing_when_tracer_is_omitted(reviews: Path) -> None:
    result = _run(FakeModel())
    assert result.final_decision == "approve"


def test_run_escalates_a_medium_tier_and_writes_review(reviews: Path) -> None:
    model = FakeModel(risk=[_gen(_RISK_MED)], recommendation=[_gen(_ESCALATE)])
    result = _run(model, configure_tracing())
    assert result.final_decision == "escalate"
    rows = _review_rows(reviews)
    assert rows[0]["reason"] == "the tier is medium"
    assert rows[0]["final_decision"] == "escalate"


def test_run_escalates_when_recommendation_has_no_decision(reviews: Path) -> None:
    model = FakeModel(recommendation=[_gen(_NO_DECISION)])
    result = _run(model, configure_tracing())
    assert result.final_decision == "escalate"
    assert _review_rows(reviews)[0]["reason"] == "recommendation did not produce a decision"


def test_run_stops_when_email_is_missing(reviews: Path) -> None:
    intake = json.loads(_INTAKE)
    intake["applicant_email"] = None
    result = _run(FakeModel(intake=[_gen(json.dumps(intake))]), configure_tracing())
    assert result.final_decision == "escalate"
    assert result.enrichment is None
    assert _review_rows(reviews)[0]["reason"] == "applicant_email is missing or invalid"


def test_run_stops_when_email_is_invalid(reviews: Path) -> None:
    intake = json.loads(_INTAKE)
    intake["applicant_email"] = "not-an-email"
    result = _run(FakeModel(intake=[_gen(json.dumps(intake))]), configure_tracing())
    assert result.final_decision == "escalate"
    assert result.enrichment is None


def test_run_stops_when_enrichment_is_incomplete(reviews: Path) -> None:
    empty = json.dumps({"credit_band": None, "prior_claims_count": None, "asset_facts": None})
    result = _run(FakeModel(enrichment=[_gen(empty)]), configure_tracing())
    assert result.final_decision == "escalate"
    assert result.risk is None
    assert _review_rows(reviews)[0]["reason"] == "enrichment record is incomplete"


def test_run_retries_intake_then_succeeds(reviews: Path) -> None:
    model = FakeModel(intake=[ValueError("no JSON object"), _gen(_INTAKE)])
    result = _run(model, configure_tracing())
    assert result.final_decision == "approve"
    assert "previous response failed" in model.prompts[1]
    assert "ValueError: no JSON object" in model.prompts[1]


def test_run_passes_null_date_of_birth_into_enrichment(reviews: Path) -> None:
    intake = json.loads(_INTAKE)
    intake["date_of_birth"] = None
    model = FakeModel(intake=[_gen(json.dumps(intake))])
    result = _run(model, configure_tracing())
    assert result.intake is not None
    assert result.intake.message.date_of_birth is None
    assert '"date_of_birth": null' in model.prompts[1]


@pytest.mark.parametrize(
    ("agent", "error", "reason"),
    [
        ("intake", ValueError("no JSON object"), "intake failed after retries"),
        ("enrichment", ModelTimeoutError("timed out"), "enrichment failed after retries"),
        ("risk", ModelTimeoutError("timed out"), "risk scoring failed after retries"),
        ("recommendation", ValueError("unusable response"), "recommendation failed after retries"),
    ],
)
def test_run_escalates_when_an_agent_fails_after_retries(
    reviews: Path, agent: str, error: BaseException, reason: str
) -> None:
    failures: list[Generation | BaseException] = [
        error,
        type(error)(str(error)),
    ]
    result = _run(FakeModel(**{agent: failures}), configure_tracing())
    assert result.final_decision == "escalate"
    rows = _review_rows(reviews)
    assert rows[0]["reason"] == reason
    if agent == "intake":
        assert rows[0]["intake"] is None


def test_run_escalates_when_there_are_no_attempts(
    reviews: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "_MAX_RETRIES", -1)
    result = _run(FakeModel(), configure_tracing())
    assert result.final_decision == "escalate"
    assert result.intake is None
    assert _review_rows(reviews)[0]["reason"] == "intake failed after retries"
    