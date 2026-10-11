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
    ("ada-lovelace-auto", {"applicant_name": "Ada Lovelace", "applicant_email": "ada.lovelace@coforge.com", "date_of_birth": "1815/12/10", "address": "12 St James's Square, London SW1Y 4LE, United Kingdom", "product": "  AUTO  ", "coverage_amount": "16000.456", "stated_income": "120000"}),
    ("ada-lovelace-home", {"applicant_name": "Ada Lovelace", "applicant_email": "ada.lovelace@coforge.com", "date_of_birth": "1815-12-10", "address": "12 St James's Square, London SW1Y 4LE, United Kingdom", "product": "HOME", "coverage_amount": "350000", "stated_income": "120000"}),
    ("katherine-johnson-auto", {"applicant_name": "Katherine Johnson", "applicant_email": "katherine.johnson@coforge.com", "date_of_birth": "1918-08-26", "address": "36 North King Street, Hampton, VA 23669", "product": "AUTO", "coverage_amount": "25000", "stated_income": "90000"}),
    ("katherine-johnson-home", {"applicant_name": "Katherine Johnson", "applicant_email": "katherine.johnson@coforge.com", "date_of_birth": "1918-08-26", "address": "36 North King Street, Hampton, VA 23669", "product": "HOME", "coverage_amount": "280000"}),
    ("margaret-hamilton-life", {"applicant_name": "Margaret Hamilton", "applicant_email": "margaret.hamilton@coforge.com", "date_of_birth": "1936-08-17", "address": "77 Massachusetts Avenue, Cambridge, MA 02139", "product": "LIFE", "coverage_amount": "500000", "stated_income": "150000"}),
    ("alan-turing-auto", {"applicant_name": "Alan Turing", "applicant_email": "alan.turing@coforge.com", "date_of_birth": "1912-06-23", "address": "Oxford Road, Manchester M13 9PL, United Kingdom", "product": "AUTO", "coverage_amount": "40000", "stated_income": "55000"}),
    ("alan-turing-home", {"applicant_name": "Alan Turing", "applicant_email": "alan.turing@coforge.com", "date_of_birth": "1912-06-23", "address": "Oxford Road, Manchester M13 9PL, United Kingdom", "product": "HOME", "stated_income": "55000"}),
    ("dorothy-vaughan-life", {"applicant_name": "Dorothy Vaughan", "applicant_email": "dorothy.vaughan@coforge.com", "date_of_birth": "1910-09-20", "address": "1000 Settlers Landing Road, Hampton, VA 23669", "product": "LIFE", "coverage_amount": "200000", "stated_income": "70000"}),
    ("hedy-lamarr-auto", {"applicant_name": "Hedy Lamarr", "applicant_email": "hedy.lamarr@coforge.com", "date_of_birth": "1914-11-09", "address": "512 N Maple Drive, Beverly Hills, CA 90210", "product": "AUTO", "coverage_amount": "60000", "stated_income": "110000"}),
    ("hedy-lamarr-home", {"applicant_name": "Hedy Lamarr", "applicant_email": "hedy.lamarr@coforge.com", "date_of_birth": "11/09/1914", "address": "  512 N Maple Drive, Beverly Hills, CA 90210  ", "product": " Home ", "coverage_amount": "900000", "stated_income": "210000.2"}),
    ("grace-hopper-auto", {"applicant_name": "Grace Hopper", "applicant_email": "grace.hopper@coforge.com", "date_of_birth": "1906-12-09", "address": "17 Hillhouse Avenue, New Haven, CT 06511", "product": "AUTO", "coverage_amount": "30000", "stated_income": "95000"}),
    ("grace-hopper-life", {"applicant_name": "Grace Hopper", "applicant_email": "grace.hopper@coforge.com", "date_of_birth": "1906-12-09", "address": "17 Hillhouse Avenue, New Haven, CT 06511", "product": "LIFE", "coverage_amount": "250000", "stated_income": "90000"}),
    ("john-von-neumann-life", {"applicant_name": "John von Neumann", "applicant_email": "john.vonneumann@coforge.com", "date_of_birth": "1903-12-28", "address": "1 Einstein Drive, Princeton, NJ 08540", "product": "LIFE", "coverage_amount": "1000000", "stated_income": "80000"}),
    ("john-von-neumann-home", {"applicant_name": "John von Neumann", "applicant_email": "john.vonneumann@coforge.com", "date_of_birth": "1903-12-28", "address": "1 Einstein Drive, Princeton, NJ 08540", "product": "HOME", "coverage_amount": "750000", "stated_income": "80000"}),
    ("mary-jackson-auto", {"applicant_name": "Mary Jackson", "applicant_email": "mary.jackson@coforge.com", "date_of_birth": "1921-04-09", "address": "90 LaSalle Avenue, Hampton, VA 23669", "product": "AUTO", "coverage_amount": "20000", "stated_income": "85000"}),
    ("mary-jackson-life", {"applicant_name": "Mary Jackson", "applicant_email": "mary.jackson@coforge.com", "date_of_birth": "1921-04-09", "address": "90 LaSalle Avenue, Hampton, VA 23669", "product": "LiFe", "coverage_amount": "300000.129", "stated_income": "92000.999"}),
    ("claude-shannon-home", {"applicant_name": "Claude Shannon", "applicant_email": "claude.shannon@coforge.com", "date_of_birth": "1916-04-30", "address": "77 Massachusetts Avenue, Cambridge, MA 02139", "product": "HOME", "coverage_amount": "400000", "stated_income": "130000"}),
    ("claude-shannon-auto", {"applicant_name": "Claude Shannon", "applicant_email": "claude.shannon@coforge.com", "date_of_birth": "1916-04-30", "address": "77 Massachusetts Avenue, Cambridge, MA 02139", "product": "AUTO", "coverage_amount": "70000", "stated_income": "60000"}),
    ("radia-perlman-life", {"applicant_name": "Radia Perlman", "applicant_email": "radia.perlman@coforge.com", "date_of_birth": "1951-12-18", "address": "1 Boston Place, Boston, MA 02108", "product": "LIFE", "coverage_amount": "400000", "stated_income": "160000"}),
    ("edsger-dijkstra-life", {"applicant_name": "Edsger Dijkstra", "applicant_email": "edsger.dijkstra@coforge.com", "date_of_birth": "1930-05-11", "address": "Den Dolech 2, 5612 AZ Eindhoven, Netherlands", "product": "LIFE", "coverage_amount": "250000", "stated_income": "100000"}),
    ("barbara-liskov-auto", {"applicant_name": "Barbara Liskov", "applicant_email": "barbara.liskov@coforge.com", "date_of_birth": "1939-11-07", "address": "32 Vassar Street, Cambridge, MA 02139", "product": "AUTO", "coverage_amount": "45000", "stated_income": "100000"}),
    ("barbara-liskov-home", {"applicant_name": "Barbara Liskov", "applicant_email": "barbara.liskov@coforge.com", "date_of_birth": "1939-11-07", "address": "32 Vassar Street, Cambridge, MA 02139", "product": "HOME", "coverage_amount": "400000", "stated_income": "100000"}),
    ("leslie-lamport-home", {"applicant_name": "Leslie Lamport", "applicant_email": "leslie.lamport@coforge.com", "date_of_birth": "1941-02-07", "address": "333 Ravenswood Avenue, Menlo Park, CA 94025", "product": "HOME", "coverage_amount": "320000", "stated_income": "140000"}),
    ("frances-allen-auto", {"applicant_name": "Frances Allen", "applicant_email": "frances.allen@coforge.com", "date_of_birth": "1932-08-04", "address": "1101 Kitchawan Road, Yorktown Heights, NY 10598", "product": "AUTO", "coverage_amount": "18000", "stated_income": "75000"}),
    ("tim-berners-lee-auto", {"applicant_name": "Tim Berners-Lee", "applicant_email": "tim.bernerslee@coforge.com", "date_of_birth": "1955-06-08", "address": "32 Vassar Street, Cambridge, MA 02139", "product": "AUTO", "coverage_amount": "30000", "stated_income": "120000"}),
    ("vint-cerf-home", {"applicant_name": "Vint Cerf", "applicant_email": "vint.cerf@coforge.com", "date_of_birth": "1943-06-23", "address": "1875 Explorer Street, Reston, VA 20190", "product": "HOME", "coverage_amount": "500000", "stated_income": "150000"}),
    ("bob-kahn-life", {"applicant_name": "Bob Kahn", "applicant_email": "bob.kahn@coforge.com", "date_of_birth": "1938-12-23", "address": "1895 Preston White Drive, Reston, VA 20191", "product": "LIFE", "coverage_amount": "300000", "stated_income": "140000"}),
    ("donald-knuth-auto", {"applicant_name": "Donald Knuth", "applicant_email": "donald.knuth@coforge.com", "date_of_birth": "1938-01-10", "address": "353 Jane Stanford Way, Stanford, CA 94305", "product": "AUTO", "coverage_amount": "20000", "stated_income": "110000"}),
    ("adele-goldberg-life", {"applicant_name": "Adele Goldberg", "applicant_email": "adele.goldberg@coforge.com", "date_of_birth": "1945-07-07", "address": "3333 Coyote Hill Road, Palo Alto, CA 94304", "product": "LIFE", "coverage_amount": "200000", "stated_income": "90000"}),
    ("barbara-liskov-life", {"applicant_name": "Barbara Liskov", "applicant_email": "barbara.liskov@coforge.com", "date_of_birth": "1939-11-07", "address": "32 Vassar Street, Cambridge, MA 02139", "product": "LIFE", "coverage_amount": "250000", "stated_income": "100000"}),
    ("guido-van-rossum-renters", {"applicant_name": "Guido van Rossum", "applicant_email": "guido.vanrossum@coforge.com", "date_of_birth": "1956-01-31", "address": "188 King Street, San Francisco, CA 94107", "product": "RENTERS", "coverage_amount": "50000", "stated_income": "80000"}),
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
