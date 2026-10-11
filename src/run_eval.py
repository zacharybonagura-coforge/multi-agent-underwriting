"""Run three mock applications and store the batch result beside its trace."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model.base import ModelAdapter
from model.ollama import OllamaAdapter
from observability import configure_tracing
from pipeline import PipelineResult, run

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
LOGS = ROOT / "logs"

APPLICATIONS = [
    (
        "ada-lovelace-auto",
        {
            "applicant_name": "Ada Lovelace",
            "date_of_birth": "1815-12-10",
            "address": "12 St James Square, London",
            "product": "AUTO",
            "coverage_amount": "50000",
            "stated_income": "120000",
        },
    ),
    (
        "ada-lovelace-home",
        {
            "applicant_name": "Ada Lovelace",
            "date_of_birth": "1815-12-10",
            "address": "12 St James Square, London",
            "product": "HOME",
            "coverage_amount": "350000",
            "stated_income": "120000",
        },
    ),
    (
        "grace-hopper-life",
        {
            "applicant_name": "Grace Hopper",
            "date_of_birth": "1906-12-09",
            "address": "Yale University, New Haven",
            "product": "LIFE",
            "coverage_amount": "250000",
            "stated_income": "90000",
        },
    ),
]


def _result_record(run_id: str, result: PipelineResult) -> dict[str, Any]:
    """One JSON object: the run id and each agent's output."""
    intake = None
    if result.intake is not None:
        intake = result.intake.message.model_dump(mode="json")
        intake["missing_fields"] = result.intake.missing_fields
    enrichment = None
    if result.enrichment is not None:
        enrichment = result.enrichment.message.model_dump(mode="json")
    return {
        "run_id": run_id,
        "intake": intake,
        "enrichment": enrichment,
        "risk": None if result.risk is None else result.risk.message.model_dump(mode="json"),
        "recommendation": (
            None
            if result.recommendation is None
            else result.recommendation.message.model_dump(mode="json")
        ),
        "final_decision": result.final_decision,
    }


def _parse_trace(message: str) -> tuple[str, dict[str, Any]]:
    """Turn one underwriting log line into an agent name and its fields."""
    agent, rest = message.split(" ", 1)
    agent = agent.removeprefix("agent=")
    if " input=" not in rest:
        return agent, {"duration_ms": float(rest.removeprefix("duration_ms="))}
    before, payload = rest.split(" input=", 1)
    raw_input, raw_output = payload.split(" output=", 1)
    parts = dict(item.split("=", 1) for item in before.split(" "))
    return agent, {
        "duration_ms": float(parts["duration_ms"]),
        "input_tokens": int(parts["input_tokens"]),
        "output_tokens": int(parts["output_tokens"]),
        "input": json.loads(raw_input),
        "output": json.loads(raw_output),
    }


class _TraceCapture(logging.Handler):
    """Keep each agent's trace fields for one application."""

    def __init__(self) -> None:
        super().__init__()
        self.agents: dict[str, dict[str, Any]] = {}

    def emit(self, record: logging.LogRecord) -> None:
        agent, fields = _parse_trace(record.getMessage())
        self.agents[agent] = fields


def _log_record(
    run_id: str,
    agents: dict[str, dict[str, Any]],
    final_decision: str,
) -> dict[str, Any]:
    """One JSON object: the run id, each agent's trace, and the final decision."""
    return {
        "run_id": run_id,
        "intake": agents.get("intake"),
        "enrichment": agents.get("enrichment"),
        "risk": agents.get("risk"),
        "recommendation": agents.get("recommendation"),
        "underwriting": agents.get("underwriting"),
        "final_decision": final_decision,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def main(model: ModelAdapter) -> None:
    """Run the three applications and write one timestamped JSONL in each folder."""
    RUNS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    tracer = configure_tracing()
    underwriting = logging.getLogger("underwriting")
    run_rows: list[dict[str, Any]] = []
    log_rows: list[dict[str, Any]] = []
    for name, application in APPLICATIONS:
        capture = _TraceCapture()
        underwriting.addHandler(capture)
        try:
            result = run(application, model, tracer)
        finally:
            underwriting.removeHandler(capture)
        run_rows.append(_result_record(name, result))
        log_rows.append(_log_record(name, capture.agents, result.final_decision))
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    _write_jsonl(RUNS / f"{stamp}.jsonl", run_rows)
    _write_jsonl(LOGS / f"{stamp}.jsonl", log_rows)


if __name__ == "__main__":
    main(OllamaAdapter())
