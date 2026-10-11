"""Unit tests for the risk-timeout demo."""

import json

import pytest

import show_failure
from model.base import Generation, ModelTimeoutError

_INTAKE = json.dumps({
    "applicant_name": "Ada Lovelace",
    "applicant_email": "ada.lovelace@coforge.com",
    "date_of_birth": "1815-12-10",
    "address": "12 St James Square, London",
    "product": "auto",
    "coverage_amount": 16000,
    "stated_income": 120000,
})
_ENRICH = json.dumps({
    "credit_band": "good",
    "prior_claims_count": 1,
    "asset_facts": "2018 Honda Civic",
})


class InnerModel:
    provider = "fake"
    model_id = "fake"

    def generate(self, prompt: str) -> Generation:
        if prompt.startswith("Normalize"):
            return Generation(text=_INTAKE, input_tokens=1, output_tokens=1)
        if prompt.startswith("Add underwriting"):
            return Generation(text=_ENRICH, input_tokens=1, output_tokens=1)
        raise AssertionError(prompt)


class MemoryStore:
    def load(self) -> list[dict[str, object]]:
        return [{
            "applicant_email": "ada.lovelace@coforge.com",
            "product": "auto",
            "credit_file": "good",
            "claims": ["2019 collision"],
            "asset": "2018 Honda Civic",
        }]

    def save(self, payload: object) -> None:
        return None


def test_timeout_raises_on_a_risk_prompt() -> None:
    wrapped = show_failure.TimeoutOnRisk(InnerModel())
    with pytest.raises(ModelTimeoutError, match="risk scoring timed out"):
        wrapped.generate("Score this insurance application. Reply with JSON only.")
    assert wrapped.prompts[0].startswith("Score this")


def test_timeout_delegates_non_risk_prompts() -> None:
    wrapped = show_failure.TimeoutOnRisk(InnerModel())
    generation = wrapped.generate("Normalize this insurance application. Reply with JSON only.")
    assert "Ada Lovelace" in generation.text
    