"""Score one risk case with whichever model adapter you pass in."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from agents.risk import risk_agent
from model.base import ModelAdapter
from observability import configure_tracing, traced_step

# Fields the orchestrator would pass after intake and enrichment.
# Golden tier for this case is medium: good credit and one prior claim.
DEFAULT_CASE = {
    "product": "auto",
    "coverage_amount": 16000.46,
    "stated_income": 120000.0,
    "missing_fields": [],
    "credit_band": "good",
    "prior_claims_count": 1,
    "asset_facts": "2018 Honda Civic LX sedan, 42,000 miles, garaged, personal use",
}


def load_case(case_path: str | None = None) -> dict[str, Any]:
    """Use a JSON file, then RISK_CASE, then the built-in case."""
    if case_path is not None:
        return json.loads(Path(case_path).read_text())
    raw = os.environ.get("RISK_CASE")
    if raw:
        return json.loads(raw)
    return DEFAULT_CASE


def main(model: ModelAdapter, case_path: str | None = None) -> None:
    """Score one case with ``model`` and print the trace and the result."""
    case = load_case(case_path)
    result = traced_step(
        configure_tracing(),
        "risk",
        case,
        lambda: risk_agent(case, model),
        lambda result: result.message.model_dump(mode="json"),
    )
    print("Risk Result: ")
    print(json.dumps(result.message.model_dump(mode="json"), indent=2))
    print("==================================\n")


def _adapter(name: str) -> ModelAdapter:
    if name == "bedrock":
        from model.bedrock import BedrockAdapter

        return BedrockAdapter()
    if name == "ollama":
        from model.ollama import OllamaAdapter

        return OllamaAdapter(
            model_id=os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        )
    raise SystemExit("usage: risk_main.py bedrock|ollama [case.json]")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: risk_main.py bedrock|ollama [case.json]")
    case_path = sys.argv[2] if len(sys.argv) == 3 else None
    adapter = _adapter(sys.argv[1])
    main(adapter, case_path)
