"""Recommendation agent: approve, deny, or escalate a scored case."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from agents.model_io import parse_message, render_prompt
from model.base import ModelAdapter

Decision = Literal["approve", "deny", "escalate"]
DECISIONS = ("approve", "deny", "escalate")


class RecommendationMessage(BaseModel):
    """Decision the pipeline returns for one application."""

    decision: Decision | None = None
    rationale: str | None = None

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, value: object) -> object:
        """Keep a known decision and drop anything else."""
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if lowered in DECISIONS:
            return lowered
        return None

    @field_validator("rationale", mode="before")
    @classmethod
    def blank_rationale(cls, value: object) -> object:
        """Treat an empty rationale as missing."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@dataclass(frozen=True)
class RecommendationResult:
    """Recommendation message plus token counts for the trace."""

    message: RecommendationMessage
    input_tokens: int
    output_tokens: int


def recommendation_agent(case: dict[str, Any], model: ModelAdapter) -> RecommendationResult:
    """Decide ``case`` with one model call."""
    generation = model.generate(render_prompt("recommendation.v1.md", case))
    return RecommendationResult(
        message=parse_message(generation.text, RecommendationMessage, "recommendation"),
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
    )