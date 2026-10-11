"""Unit tests for the risk scoring agent."""

import json
from typing import Any

import pytest

from agents.risk import risk_agent
from model.base import Generation


class FakeModel:
    provider = "fake"
    model_id = "fake"

    def __init__(self, text: str, input_tokens: int = 11, output_tokens: int = 7) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> Generation:
        self.prompts.append(prompt)
        return Generation(
            text=self.text,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


def _score(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "risk_score": 42,
        "risk_factors": ["credit_band", "prior_claims_count"],
        "tier": "medium",
    }
    payload.update(overrides)
    return payload


def _case() -> dict[str, Any]:
    return {
        "product": "auto",
        "coverage_amount": 50000.0,
        "stated_income": 120000.0,
        "credit_band": "good",
        "prior_claims_count": 1,
        "asset_facts": "2018 Honda Civic",
        "missing_fields": [],
    }


def test_risk_reads_a_complete_reply() -> None:
    model = FakeModel(json.dumps(_score()))
    result = risk_agent(_case(), model)
    assert result.message.risk_score == 42
    assert result.message.risk_factors == ["credit_band", "prior_claims_count"]
    assert result.message.tier == "medium"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert "{{payload}}" not in model.prompts[0]
    assert "credit_band" in model.prompts[0]
    assert "JSON only" in model.prompts[0]


@pytest.mark.parametrize("score", [0, "100", 33.5])
def test_risk_accepts_a_score_from_0_to_100(score: str | float) -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_score=score))))
    assert result.message.risk_score == float(score)


def test_risk_reads_json_wrapped_in_prose() -> None:
    text = "Score:\n" + json.dumps(_score()) + "\nDone."
    result = risk_agent(_case(), FakeModel(text))
    assert result.message.tier == "medium"


@pytest.mark.parametrize("score", [-1, 101, "hi", True, ""])
def test_unusable_score_becomes_null(score: object) -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_score=score))))
    assert result.message.risk_score is None


def test_blank_factors_become_an_empty_list() -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_factors=["", "  "]))))
    assert result.message.risk_factors == []


def test_a_single_factor_string_is_kept() -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_factors="credit_band"))))
    assert result.message.risk_factors == ["credit_band"]


def test_model_text_without_json_raises() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        risk_agent(_case(), FakeModel("I could not score this case."))


def test_broken_json_raises() -> None:
    with pytest.raises(ValueError, match="unusable response"):
        risk_agent(_case(), FakeModel("{not json}"))


def test_omitted_fields_are_empty() -> None:
    result = risk_agent(_case(), FakeModel("{}"))
    assert result.message.risk_score is None
    assert result.message.risk_factors == []
    assert result.message.tier is None


def test_non_numeric_score_becomes_null() -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_score=["42"]))))
    assert result.message.risk_score is None


def test_non_list_factors_become_an_empty_list() -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_factors=None))))
    assert result.message.risk_factors == []


@pytest.mark.parametrize(("score", "tier"), [(0, "low"), (33, "low"), (34, "medium"), (66, "medium"), (67, "high"), (100, "high")])
def test_tier_comes_from_the_score(score: float, tier: str) -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_score=score, tier="high"))))
    assert result.message.tier == tier


def test_missing_required_field_is_high() -> None:
    case = _case()
    case["stated_income"] = None
    result = risk_agent(case, FakeModel(json.dumps(_score(risk_score=10, tier="low"))))
    assert result.message.tier == "high"


def test_null_score_has_null_tier() -> None:
    result = risk_agent(_case(), FakeModel(json.dumps(_score(risk_score=None, tier="high"))))
    assert result.message.tier is None
