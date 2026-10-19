"""One live call to the enrichment agent."""

import pytest

from agents.enrichment import enrichment_agent
from settings.config import Settings
from settings.factory import build_model, build_store

pytestmark = pytest.mark.integration


def test_enrichment_copies_a_live_record() -> None:
    """Ada's auto record comes back as good credit and one claim."""
    settings = Settings.from_env()
    lookup = {
        "applicant_name": "Ada Lovelace",
        "applicant_email": "ada.lovelace@coforge.com",
        "date_of_birth": "1815-12-10",
        "address": "12 St James Square, London",
        "product": "auto",
        "missing_fields": [],
    }
    result = enrichment_agent(lookup, build_model(settings), build_store(settings))
    assert result.message.credit_band == "good"
    assert result.message.prior_claims_count == 1
    assert result.message.asset_facts
    assert result.input_tokens > 0
    assert result.output_tokens > 0