"""Unit tests for the recommendation agent."""

import json
from typing import Any

import pytest

from agents.recommendation import recommendation_agent
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


def _decision(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": "approve",
        "rationale": "Score 20 and tier low support approval.",
    }
    payload.update(overrides)
    return payload


def _case() -> dict[str, Any]:
    return {
        "risk_score": 20,
        "risk_factors": ["credit_band"],
        "tier": "low",
    }


def test_recommendation_reads_a_complete_reply() -> None:
    model = FakeModel(json.dumps(_decision()))
    result = recommendation_agent(_case(), model)
    assert result.message.decision == "approve"
    assert result.message.rationale == "Score 20 and tier low support approval."
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert "{{payload}}" not in model.prompts[0]
    assert "risk_score" in model.prompts[0]
    assert "JSON only" in model.prompts[0]


@pytest.mark.parametrize("decision", ["approve", "DENY", "  escalate  "])
def test_recommendation_normalizes_decision(decision: str) -> None:
    result = recommendation_agent(_case(), FakeModel(json.dumps(_decision(decision=decision))))
    assert result.message.decision == decision.strip().lower()


def test_recommendation_reads_json_wrapped_in_prose() -> None:
    text = "Decision:\n" + json.dumps(_decision()) + "\nDone."
    result = recommendation_agent(_case(), FakeModel(text))
    assert result.message.decision == "approve"


@pytest.mark.parametrize("decision", ["refer", "", "   ", 1])
def test_unusable_decision_becomes_null(decision: object) -> None:
    result = recommendation_agent(_case(), FakeModel(json.dumps(_decision(decision=decision))))
    assert result.message.decision is None


@pytest.mark.parametrize("rationale", ["", "   "])
def test_blank_rationale_becomes_null(rationale: str) -> None:
    result = recommendation_agent(_case(), FakeModel(json.dumps(_decision(rationale=rationale))))
    assert result.message.rationale is None


def test_model_text_without_json_raises() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        recommendation_agent(_case(), FakeModel("I could not decide this case."))


def test_broken_json_raises() -> None:
    with pytest.raises(ValueError, match="unusable response"):
        recommendation_agent(_case(), FakeModel("{not json}"))


def test_omitted_fields_are_null() -> None:
    result = recommendation_agent(_case(), FakeModel("{}"))
    assert result.message.decision is None
    assert result.message.rationale is None