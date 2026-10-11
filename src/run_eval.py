"""Run three mock applications and store the batch result beside its trace."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from observability import configure_tracing
from pipeline import PipelineResult, run
from settings.config import Settings
from settings.factory import build_model, build_store

APPLICATIONS = [
    ("ada-lovelace-auto", {"applicant_name": "Ada Lovelace", "date_of_birth": "1815/12/10", "address": "12 St James Square, London", "product": "  AUTO  ", "coverage_amount": "16000.456", "stated_income": "120000"}),
    ("ada-lovelace-home", {"applicant_name": "Ada Lovelace", "date_of_birth": "1815-12-10", "address": "12 St James Square, London", "product": "HOME", "coverage_amount": "350000", "stated_income": "120000"}),
    ("katherine-johnson-auto", {"applicant_name": "Katherine Johnson", "date_of_birth": "1918-08-26", "address": "Hampton, Virginia", "product": "AUTO", "coverage_amount": "25000", "stated_income": "90000"}),
    ("katherine-johnson-home", {"applicant_name": "Katherine Johnson", "date_of_birth": "1918-08-26", "address": "Hampton, Virginia", "product": "HOME", "coverage_amount": "280000"}),
    ("margaret-hamilton-life", {"applicant_name": "Margaret Hamilton", "date_of_birth": "1936-08-17", "address": "Cambridge, Massachusetts", "product": "LIFE", "coverage_amount": "500000", "stated_income": "150000"}),
    ("alan-turing-auto", {"applicant_name": "Alan Turing", "date_of_birth": "1912-06-23", "address": "Manchester", "product": "AUTO", "coverage_amount": "40000", "stated_income": "55000"}),
    ("alan-turing-home", {"applicant_name": "Alan Turing", "date_of_birth": "1912-06-23", "address": "Manchester", "product": "HOME", "stated_income": "55000"}),
    ("dorothy-vaughan-life", {"applicant_name": "Dorothy Vaughan", "date_of_birth": "1910-09-20", "address": "Hampton, Virginia", "product": "LIFE", "coverage_amount": "200000", "stated_income": "70000"}),
    ("hedy-lamarr-auto", {"applicant_name": "Hedy Lamarr", "date_of_birth": "1914-11-09", "address": "Los Angeles", "product": "AUTO", "coverage_amount": "60000", "stated_income": "110000"}),
    ("hedy-lamarr-home", {"applicant_name": "Hedy Lamarr", "date_of_birth": "11/09/1914", "address": "  512 Maple Drive, Los Angeles, California  ", "product": " Home ", "coverage_amount": "900000", "stated_income": "210000.2"}),
    ("grace-hopper-auto", {"applicant_name": "Grace Hopper", "date_of_birth": "1906-12-09", "address": "Yale University, New Haven", "product": "AUTO", "coverage_amount": "30000", "stated_income": "95000"}),
    ("grace-hopper-life", {"applicant_name": "Grace Hopper", "date_of_birth": "1906-12-09", "address": "Yale University, New Haven", "product": "LIFE", "coverage_amount": "250000", "stated_income": "90000"}),
    ("john-von-neumann-life", {"applicant_name": "John von Neumann", "date_of_birth": "1903-12-28", "address": "Princeton, New Jersey", "product": "LIFE", "coverage_amount": "1000000", "stated_income": "80000"}),
    ("john-von-neumann-home", {"applicant_name": "John von Neumann", "date_of_birth": "1903-12-28", "address": "Princeton, New Jersey", "product": "HOME", "coverage_amount": "750000", "stated_income": "80000"}),
    ("mary-jackson-auto", {"applicant_name": "Mary Jackson", "date_of_birth": "1921-04-09", "address": "Hampton, Virginia", "product": "AUTO", "coverage_amount": "20000", "stated_income": "85000"}),
    ("mary-jackson-life", {"applicant_name": "Mary Jackson", "date_of_birth": "1921-04-09", "address": "90 LaSalle Avenue, Hampton, Virginia", "product": "LiFe", "coverage_amount": "300000.129", "stated_income": "92000.999"}),
    ("claude-shannon-home", {"applicant_name": "Claude Shannon", "date_of_birth": "1916-04-30", "address": "Massachusetts", "product": "HOME", "coverage_amount": "400000", "stated_income": "130000"}),
    ("claude-shannon-auto", {"applicant_name": "Claude Shannon", "date_of_birth": "1916-04-30", "address": "Massachusetts", "product": "AUTO", "coverage_amount": "70000", "stated_income": "60000"}),
    ("radia-perlman-life", {"applicant_name": "Radia Perlman", "date_of_birth": "1951-12-18", "address": "Boston", "product": "LIFE", "coverage_amount": "400000", "stated_income": "160000"}),
    ("edsger-dijkstra-life", {"applicant_name": "Edsger Dijkstra", "date_of_birth": "1930-05-11", "address": "Eindhoven", "product": "LIFE", "coverage_amount": "250000", "stated_income": "100000"}),
    ("barbara-liskov-auto", {"applicant_name": "Barbara Liskov", "date_of_birth": "1939-11-07", "address": "Boston", "product": "AUTO", "coverage_amount": "45000", "stated_income": "100000"}),
    ("barbara-liskov-home", {"applicant_name": "Barbara Liskov", "date_of_birth": "1939-11-07", "address": "Boston", "product": "HOME", "coverage_amount": "400000", "stated_income": "100000"}),
    ("leslie-lamport-home", {"applicant_name": "Leslie Lamport", "date_of_birth": "1941-02-07", "address": "California", "product": "HOME", "coverage_amount": "320000", "stated_income": "140000"}),
    ("frances-allen-auto", {"applicant_name": "Frances Allen", "date_of_birth": "1932-08-04", "address": "New York", "product": "AUTO", "coverage_amount": "18000", "stated_income": "75000"}),
    ("tim-berners-lee-auto", {"applicant_name": "Tim Berners-Lee", "date_of_birth": "1955-06-08", "address": "Boston", "product": "AUTO", "coverage_amount": "30000", "stated_income": "120000"}),
    ("vint-cerf-home", {"applicant_name": "Vint Cerf", "date_of_birth": "1943-06-23", "address": "Virginia", "product": "HOME", "coverage_amount": "500000", "stated_income": "150000"}),
    ("bob-kahn-life", {"applicant_name": "Bob Kahn", "date_of_birth": "1938-12-23", "address": "Virginia", "product": "LIFE", "coverage_amount": "300000", "stated_income": "140000"}),
    ("donald-knuth-auto", {"applicant_name": "Donald Knuth", "date_of_birth": "1938-01-10", "address": "Stanford", "product": "AUTO", "coverage_amount": "20000", "stated_income": "110000"}),
    ("adele-goldberg-life", {"applicant_name": "Adele Goldberg", "date_of_birth": "1945-07-07", "address": "California", "product": "LIFE", "coverage_amount": "200000", "stated_income": "90000"}),
    ("barbara-liskov-life", {"applicant_name": "Barbara Liskov", "date_of_birth": "1939-11-07", "address": "Boston", "product": "LIFE", "coverage_amount": "250000", "stated_income": "100000"}),
    ("guido-van-rossum-renters", {"applicant_name": "Guido van Rossum", "date_of_birth": "1956-01-31", "address": "California", "product": "RENTERS", "coverage_amount": "50000", "stated_income": "80000"}),
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


def main() -> None:
    """Run the three applications and write one timestamped JSONL in each folder."""
    settings = Settings.from_env()
    settings.runs_dir.mkdir(exist_ok=True)
    settings.logs_dir.mkdir(exist_ok=True)

    tracer = configure_tracing()
    underwriting = logging.getLogger("underwriting")
    run_rows: list[dict[str, Any]] = []
    log_rows: list[dict[str, Any]] = []
    for name, application in APPLICATIONS:
        capture = _TraceCapture()
        underwriting.addHandler(capture)
        try:
            result = run(application, build_model(settings), build_store(settings), tracer)
        finally:
            underwriting.removeHandler(capture)
        run_rows.append(_result_record(name, result))
        log_rows.append(_log_record(name, capture.agents, result.final_decision))
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    _write_jsonl(settings.runs_dir / f"{stamp}.jsonl", run_rows)
    _write_jsonl(settings.logs_dir / f"{stamp}.jsonl", log_rows)


if __name__ == "__main__":
    main()
