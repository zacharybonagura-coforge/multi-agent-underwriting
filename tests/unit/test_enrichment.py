"""Unit tests for the enrichment agent."""

import json
from typing import Any

import pytest

from agents.enrichment import enrichment_agent, lookup_applicant
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


class MemoryStore:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def load(self) -> list[dict[str, Any]]:
        return self._records

    def save(self, payload: Any) -> None:
        return None


def _store() -> MemoryStore:
    return MemoryStore([
        {
            "applicant_email": "ada.lovelace@coforge.com",
            "product": "auto",
            "credit_file": "good",
            "claims": ["2019 collision"],
            "asset": "2018 Honda Civic",
        }
    ])

def _facts(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "credit_band": "good",
        "prior_claims_count": 1,
        "asset_facts": "2018 Honda Civic",
    }
    payload.update(overrides)
    return payload


def _lookup(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "applicant_name": "Ada Lovelace",
        "applicant_email": "ada.lovelace@coforge.com",
        "date_of_birth": "1815-12-10",
        "address": "12 St James Square, London",
        "product": "auto",
        "missing_fields": [],
    }
    payload.update(overrides)
    return payload


def test_lookup_returns_the_matching_record() -> None:
    store = MemoryStore([
        {"applicant_email": "ada.lovelace@coforge.com", "product": "auto", "asset": "2018 Honda Civic"},
        {"applicant_email": "ada.lovelace@coforge.com", "product": "home", "asset": "brick house"},
    ])
    assert lookup_applicant("ada.lovelace@coforge.com", "auto", store) == store.load()[0]


def test_lookup_returns_none_for_an_unknown_pair() -> None:
    store = MemoryStore([
        {"applicant_email": "ada.lovelace@coforge.com", "product": "auto", "asset": "2018 Honda Civic"},
    ])
    assert lookup_applicant("ada.lovelace@coforge.com", "life", store) is None


@pytest.mark.parametrize(("email", "product"), [(None, "auto"), ("ada.lovelace@coforge.com", None)])
def test_lookup_returns_none_without_a_key(email: str | None, product: str | None) -> None:
    store = MemoryStore([
        {"applicant_email": "ada.lovelace@coforge.com", "product": "auto", "asset": "2018 Honda Civic"},
    ])
    assert lookup_applicant(email, product, store) is None


def test_enrichment_reads_a_complete_reply() -> None:
    model = FakeModel(json.dumps(_facts()))
    result = enrichment_agent(_lookup(), model, _store())
    assert result.message.credit_band == "good"
    assert result.message.prior_claims_count == 1
    assert result.message.asset_facts == "2018 Honda Civic"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert "{{payload}}" not in model.prompts[0]
    assert "2018 Honda Civic" in model.prompts[0]
    assert "JSON only" in model.prompts[0]


def test_enrichment_puts_null_records_in_the_prompt_for_an_unknown_applicant() -> None:
    model = FakeModel(json.dumps(_facts(
        credit_band=None,
        prior_claims_count=None,
        asset_facts=None,
    )))
    enrichment_agent(_lookup(applicant_email="unknown@coforge.com"), model, _store())
    assert '"records": null' in model.prompts[0]


@pytest.mark.parametrize("band", ["excellent", "GOOD", "  fair  ", "poor"])
def test_enrichment_normalizes_credit_band(band: str) -> None:
    result = enrichment_agent(_lookup(), FakeModel(json.dumps(_facts(credit_band=band))), _store())
    assert result.message.credit_band == band.strip().lower()


@pytest.mark.parametrize("count", [0, "2", 3.0])
def test_enrichment_accepts_a_whole_claims_count(count: str | float) -> None:
    result = enrichment_agent(_lookup(), FakeModel(json.dumps(_facts(prior_claims_count=count))), _store())
    assert result.message.prior_claims_count == int(count)


def test_enrichment_reads_json_wrapped_in_prose() -> None:
    text = "Facts:\n" + json.dumps(_facts()) + "\nDone."
    result = enrichment_agent(_lookup(), FakeModel(text), _store())
    assert result.message.asset_facts == "2018 Honda Civic"


@pytest.mark.parametrize("band", ["prime", "", "   ", 12])
def test_unusable_credit_band_becomes_null(band: object) -> None:
    result = enrichment_agent(_lookup(), FakeModel(json.dumps(_facts(credit_band=band))), _store())
    assert result.message.credit_band is None


@pytest.mark.parametrize("count", ["hi", -1, 2.5, True, ""])
def test_unusable_claims_count_becomes_null(count: object) -> None:
    result = enrichment_agent(_lookup(), FakeModel(json.dumps(_facts(prior_claims_count=count))), _store())
    assert result.message.prior_claims_count is None


@pytest.mark.parametrize("asset", ["", "   "])
def test_blank_asset_facts_become_null(asset: str) -> None:
    result = enrichment_agent(_lookup(), FakeModel(json.dumps(_facts(asset_facts=asset))), _store())
    assert result.message.asset_facts is None


def test_model_text_without_json_raises() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        enrichment_agent(_lookup(), FakeModel("I could not enrich this applicant."), _store())


def test_broken_json_raises() -> None:
    with pytest.raises(ValueError, match="unusable response"):
        enrichment_agent(_lookup(), FakeModel("{not json}"), _store())


def test_omitted_fields_are_null() -> None:
    result = enrichment_agent(_lookup(), FakeModel("{}"), _store())
    assert result.message.credit_band is None
    assert result.message.prior_claims_count is None
    assert result.message.asset_facts is None