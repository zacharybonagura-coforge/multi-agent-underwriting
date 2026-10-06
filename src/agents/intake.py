"""Intake agent: normalize a raw insurance application."""

import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, field_validator

from model.base import ModelAdapter
from prompts.repository import render

Product = Literal["auto", "home", "life"]

FIELDS = (
    "applicant_name",
    "date_of_birth",
    "address",
    "product",
    "coverage_amount",
    "stated_income",
)

class IntakeMessage(BaseModel):
    """Normalized application passed onward by the orchestrator."""

    applicant_name: str | None
    date_of_birth: date | None
    address: str | None
    product: Product | None
    coverage_amount: float | None
    stated_income: float | None

    @field_validator("applicant_name", "address", mode="before")
    @classmethod
    def blank_to_null(cls, value: object) -> object:
        """Treat an empty string as a missing field."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value
        
    @field_validator("product", mode="before")
    @classmethod
    def normalize_product(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if lowered in ("auto", "home", "life"):
            return lowered
        return None

    @field_validator("coverage_amount", "stated_income", mode="before")
    @classmethod
    def two_decimals(cls, value: object) -> Decimal | None:
        """Round a dollar amount to cents."""
        if value is None:
            return None
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class IntakeResult:
    """Intake message plus missing fields, token counts for the trace."""

    message: IntakeMessage
    missing_fields: list[str]
    input_tokens: int
    output_tokens: int



def _prompt(raw_application: dict[str, Any]) -> str:
    payload = json.dumps(raw_application, default=str)
    return render("intake.v1.md", payload=payload)


def _parse(text: str) -> IntakeMessage:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("intake model returned no JSON object")
    try:
        return IntakeMessage.model_validate_json(text[start : end + 1])
    except ValidationError as exc:
        raise ValueError("intake model returned an unusable response") from exc


def intake_agent(raw_application: dict[str, Any], model: ModelAdapter) -> IntakeResult:
    """Normalize ``raw_application`` with one model call."""
    generation = model.generate(_prompt(raw_application))
    message = _parse(generation.text)
    missing = [name for name in FIELDS if getattr(message, name) is None]
    return IntakeResult(
        message=message,
        missing_fields=missing,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
    )
