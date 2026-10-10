"""Risk scoring agent: score a case from intake and enrichment facts."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from agents.model_io import parse_message, render_prompt
from model.base import ModelAdapter

Tier = Literal["low", "medium", "high"]
TIERS = ("low", "medium", "high")


class RiskMessage(BaseModel):
    """Score the orchestrator passes to recommendation."""

    risk_score: float | None = None
    risk_factors: list[str] = []
    tier: Tier | None = None

    @field_validator("risk_score", mode="before")
    @classmethod
    def score(cls, value: object) -> float | None:
        """Keep a number from 0 to 100."""
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None
        if not isinstance(value, (int, float, str)):
            return None
        try:
            number = float(value)
        except ValueError:
            return None
        if 0 <= number <= 100:
            return number
        return None

    @field_validator("risk_factors", mode="before")
    @classmethod
    def factors(cls, value: object) -> list[str]:
        """Keep the field names that moved the score."""
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @field_validator("tier", mode="before")
    @classmethod
    def normalize_tier(cls, value: object) -> object:
        """Keep a known tier and drop anything else."""
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if lowered in TIERS:
            return lowered
        return None


@dataclass(frozen=True)
class RiskResult:
    """Risk message plus token counts for the trace."""

    message: RiskMessage
    input_tokens: int
    output_tokens: int


def risk_agent(case: dict[str, Any], model: ModelAdapter) -> RiskResult:
    """Score ``case`` with one model call."""
    generation = model.generate(render_prompt("risk.v1.md", case))
    return RiskResult(
        message=parse_message(generation.text, RiskMessage, "risk"),
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
    )
