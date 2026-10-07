"""Enrichment agent: add credit, claims, and asset facts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from agents.model_io import parse_message, render_prompt
from model.base import ModelAdapter
from store.base import Store
from store.json import JsonStore

CreditBand = Literal["excellent", "good", "fair", "poor"]
BANDS = ("excellent", "good", "fair", "poor")
_STORE = JsonStore(Path(__file__).resolve().parents[2] / "data" / "applicants.json")

class EnrichmentMessage(BaseModel):
    """Facts the orchestrator passes to risk scoring."""

    credit_band: CreditBand | None
    prior_claims_count: int | None
    asset_facts: str | None

    @field_validator("credit_band", mode="before")
    @classmethod
    def normalize_band(cls, value: object) -> object:
        """Keep a known band and drop anything else."""
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if lowered in BANDS:
            return lowered
        return None

    @field_validator("prior_claims_count", mode="before")
    @classmethod
    def whole_count(cls, value: object) -> int | None:
        """Keep a non-negative whole number."""
        if isinstance(value, str):
            number = value.strip()
        elif isinstance(value, int) and not isinstance(value, bool):
            number = str(value)
        elif isinstance(value, float) and value.is_integer():
            number = str(int(value))
        else:
            return None
        if not number.isdigit():
            return None
        return int(number)

    @field_validator("asset_facts", mode="before")
    @classmethod
    def blank_facts(cls, value: object) -> object:
        """Treat an empty description as missing."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@dataclass(frozen=True)
class EnrichmentResult:
    """Enrichment message plus token counts for the trace."""

    message: EnrichmentMessage
    input_tokens: int
    output_tokens: int


def lookup_applicant(
    name: str | None,
    product: str | None,
    store: Store = _STORE,
) -> dict[str, Any] | None:
    """Return the stored record for this name and product."""
    if name is None or product is None:
        return None
    for record in store.load():
        if record["applicant_name"] == name and record["product"] == product:
            return record
    return None


def enrichment_agent(lookup: dict[str, Any], model: ModelAdapter) -> EnrichmentResult:
    """Add credit, claims, and asset facts from the applicant store."""
    records = lookup_applicant(lookup.get("applicant_name"), lookup.get("product"))
    generation = model.generate(
        render_prompt("enrichment.v1.md", {**lookup, "records": records})
    )
    return EnrichmentResult(
        message=parse_message(generation.text, EnrichmentMessage, "enrichment"),
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
    )