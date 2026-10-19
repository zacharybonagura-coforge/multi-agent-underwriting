"""One live call to the recommendation agent."""

import pytest

from agents.recommendation import recommendation_agent
from settings.config import Settings
from settings.factory import build_model

pytestmark = pytest.mark.integration


def test_recommendation_approves_a_live_low_tier() -> None:
    """A low tier is approved, with a rationale."""
    case = {
        "risk_score": 25,
        "risk_factors": ["prior_claims_count"],
        "tier": "low",
    }
    result = recommendation_agent(case, build_model(Settings.from_env()))
    assert result.message.decision == "approve"
    assert result.message.rationale
    assert result.input_tokens > 0
    assert result.output_tokens > 0