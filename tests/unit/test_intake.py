"""Unit tests for the intake agent."""

import json
from datetime import date
from decimal import InvalidOperation

import pytest

from agents.intake import FIELDS, intake_agent
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


def _application(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "applicant_name": "Ada Lovelace",
        "date_of_birth": "1815-12-10",
        "address": "12 St James Square, London",
        "product": "auto",
        "coverage_amount": "50000.00",
        "stated_income": "120000.12",
    }
    payload.update(overrides)
    return payload


def test_intake_normalizes_a_complete_application() -> None:
    raw = {
        "applicant_name": "Ada Lovelace",
        "date_of_birth": "1815-12-10",
        "address": "12 St James Square, London",
        "product": "AUTO",
        "coverage_amount": "50000",
        "stated_income": "120000.12",
    }
    model = FakeModel(json.dumps(_application(product="AUTO")))
    result = intake_agent(raw, model)

    assert result.message.applicant_name == "Ada Lovelace"
    assert result.message.date_of_birth == date(1815, 12, 10)
    assert result.message.address == "12 St James Square, London"
    assert result.message.product == "auto"
    assert result.message.coverage_amount == 50000.00
    assert result.message.stated_income == 120000.12
    assert result.missing_fields == []
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert "{{payload}}" not in model.prompts[0]
    assert "Ada Lovelace" in model.prompts[0]
    assert "JSON only" in model.prompts[0]


@pytest.mark.parametrize("product", ["auto", "HOME", "  life  "])
def test_intake_accepts_each_product(product: str) -> None:
    result = intake_agent({}, FakeModel(json.dumps(_application(product=product))))
    assert result.message.product == product.strip().lower()
    assert result.missing_fields == []


def test_intake_rounds_amounts_to_cents() -> None:
    text = json.dumps(_application(coverage_amount="50000.126", stated_income="10.005"))
    result = intake_agent({}, FakeModel(text))
    assert result.message.coverage_amount == 50000.13
    assert result.message.stated_income == 10.01


def test_intake_reads_json_wrapped_in_prose() -> None:
    text = "Normalized application:\n" + json.dumps(_application()) + "\nDone."
    result = intake_agent({}, FakeModel(text))
    assert result.message.applicant_name == "Ada Lovelace"
    assert result.missing_fields == []


@pytest.mark.parametrize("field", FIELDS)
def test_null_field_is_recorded_as_missing(field: str) -> None:
    result = intake_agent({}, FakeModel(json.dumps(_application(**{field: None}))))
    assert getattr(result.message, field) is None
    assert result.missing_fields == [field]


def test_all_null_fields_are_missing() -> None:
    result = intake_agent({}, FakeModel(json.dumps(_application(**{field: None for field in FIELDS}))))
    assert result.missing_fields == list(FIELDS)


@pytest.mark.parametrize("product", ["boat", "", "   ", 12])
def test_unusable_product_is_missing(product: object) -> None:
    result = intake_agent({}, FakeModel(json.dumps(_application(product=product))))
    assert result.message.product is None
    assert result.missing_fields == ["product"]


@pytest.mark.parametrize("field", ["applicant_name", "address"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_text_is_missing(field: str, value: str) -> None:
    result = intake_agent({}, FakeModel(json.dumps(_application(**{field: value}))))
    assert getattr(result.message, field) is None
    assert result.missing_fields == [field]


def test_model_text_without_json_raises() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        intake_agent({}, FakeModel("I could not normalize this application."))


def test_broken_json_raises() -> None:
    with pytest.raises(ValueError, match="unusable response"):
        intake_agent({}, FakeModel("{not json}"))


def test_omitted_fields_raise() -> None:
    with pytest.raises(ValueError, match="unusable response"):
        intake_agent({}, FakeModel("{}"))


def test_unconverted_date_raises() -> None:
    text = json.dumps(_application(date_of_birth="December 10, 1815"))
    with pytest.raises(ValueError, match="unusable response"):
        intake_agent({}, FakeModel(text))


def test_unusable_amount_raises() -> None:
    text = json.dumps(_application(coverage_amount="hi"))
    with pytest.raises(InvalidOperation):
        intake_agent({}, FakeModel(text))
