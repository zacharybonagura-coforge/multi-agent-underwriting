"""One live call to the risk agent."""

import pytest

from agents.risk import risk_agent
from settings.config import Settings
from settings.factory import build_model

pytestmark = pytest.mark.integration


def test_risk_bands_a_live_score() -> None:
    """A complete auto case returns a score, and the tier follows that score."""
    case = {
        "product": "auto",
        "coverage_amount": 16000.46,
        "stated_income": 120000.0,
        "missing_fields": [],
        "credit_band": "good",
        "prior_claims_count": 1,
        "asset_facts": "2018 Honda Civic LX sedan, 42,000 miles, garaged, personal use",
    }
    result = risk_agent(case, build_model(Settings.from_env()))
    score = result.message.risk_score
    assert score is not None
    assert 0 <= score <= 100
    if score < 34:
        assert result.message.tier == "low"
    elif score < 67:
        assert result.message.tier == "medium"
    else:
        assert result.message.tier == "high"
    assert result.input_tokens > 0
    assert result.output_tokens > 0