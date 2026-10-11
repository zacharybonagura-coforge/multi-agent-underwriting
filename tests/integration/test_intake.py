"""One live call to the intake agent."""

from datetime import date

import pytest

from agents.intake import intake_agent
from settings.config import Settings
from settings.factory import build_model

pytestmark = pytest.mark.integration


def test_intake_normalizes_a_live_application() -> None:
    """A slash date, a padded product, and extra cents come back normalized."""
    raw = {
        "applicant_name": "Ada Lovelace",
        "date_of_birth": "1815/12/10",
        "address": "12 St James Square, London",
        "product": "  AUTO  ",
        "coverage_amount": "16000.456",
        "stated_income": "120000",
    }
    result = intake_agent(raw, build_model(Settings.from_env()))
    assert result.message.applicant_name == "Ada Lovelace"
    assert result.message.date_of_birth == date(1815, 12, 10)
    assert result.message.address == "12 St James Square, London"
    assert result.message.product == "auto"
    assert result.message.coverage_amount == 16000.46
    assert result.message.stated_income == 120000
    assert result.missing_fields == []
    assert result.input_tokens > 0
    assert result.output_tokens > 0