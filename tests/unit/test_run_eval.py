"""Unit tests for the eval batch runner."""

import json
import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_eval
from agents.enrichment import EnrichmentMessage, EnrichmentResult
from agents.intake import IntakeMessage, IntakeResult
from pipeline import PipelineResult


def _intake() -> IntakeResult:
    return IntakeResult(
        message=IntakeMessage(
            applicant_name="Ada Lovelace",
            applicant_email="ada.lovelace@coforge.com",
            date_of_birth=date(1815, 12, 10),
            address="12 St James's Square, London SW1Y 4LE, United Kingdom",
            product="auto",
            coverage_amount=16000.46,
            stated_income=120000,
        ),
        missing_fields=[],
        input_tokens=1,
        output_tokens=1,
    )


def _enrichment() -> EnrichmentResult:
    return EnrichmentResult(
        message=EnrichmentMessage(
            credit_band="good",
            prior_claims_count=1,
            asset_facts="2018 Honda Civic",
        ),
        input_tokens=1,
        output_tokens=1,
    )


def test_result_record_includes_finished_agents() -> None:
    result = PipelineResult(
        final_decision="approve",
        intake=_intake(),
        enrichment=_enrichment(),
    )
    row = run_eval._result_record("ada-auto", result)
    assert row["run_id"] == "ada-auto"
    assert row["intake"]["applicant_email"] == "ada.lovelace@coforge.com"
    assert row["intake"]["missing_fields"] == []
    assert row["enrichment"]["credit_band"] == "good"
    assert row["risk"] is None
    assert row["recommendation"] is None
    assert row["final_decision"] == "approve"


def test_result_record_keeps_null_agents_when_the_pipeline_stops() -> None:
    row = run_eval._result_record("ada-auto", PipelineResult(final_decision="escalate"))
    assert row["intake"] is None
    assert row["enrichment"] is None
    assert row["risk"] is None
    assert row["recommendation"] is None


def test_parse_trace_reads_a_duration_only_line() -> None:
    agent, fields = run_eval._parse_trace("agent=underwriting duration_ms=12.5")
    assert agent == "underwriting"
    assert fields == {"duration_ms": 12.5}


def test_parse_trace_reads_a_span_with_tokens() -> None:
    message = (
        'agent=intake duration_ms=2.0 input_tokens=10 output_tokens=4 '
        'input={"product": "auto"} output={"ok": true}'
    )
    agent, fields = run_eval._parse_trace(message)
    assert agent == "intake"
    assert fields["input_tokens"] == 10
    assert fields["output_tokens"] == 4
    assert fields["input"] == {"product": "auto"}
    assert fields["output"] == {"ok": True}


def test_parse_trace_raises_when_the_line_has_no_fields() -> None:
    with pytest.raises(ValueError):
        run_eval._parse_trace("agent=intake")


def test_trace_capture_stores_parsed_agents() -> None:
    capture = run_eval._TraceCapture()
    record = logging.LogRecord(
        "underwriting", logging.INFO, __file__, 0,
        "agent=underwriting duration_ms=9.0", None, None,
    )
    capture.emit(record)
    assert capture.agents["underwriting"] == {"duration_ms": 9.0}


def test_log_record_fills_missing_agents_with_none() -> None:
    row = run_eval._log_record("ada-auto", {"underwriting": {"duration_ms": 1.0}}, "approve")
    assert row["run_id"] == "ada-auto"
    assert row["intake"] is None
    assert row["underwriting"] == {"duration_ms": 1.0}
    assert row["final_decision"] == "approve"


def test_write_jsonl_writes_one_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    run_eval._write_jsonl(path, [{"run_id": "a"}, {"run_id": "b"}])
    assert path.read_text() == '{"run_id": "a"}\n{"run_id": "b"}\n'


def test_main_writes_a_run_file_and_a_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    logs = tmp_path / "logs"
    settings = SimpleNamespace(runs_dir=runs, logs_dir=logs)
    monkeypatch.setattr(run_eval.Settings, "from_env", staticmethod(lambda: settings))
    monkeypatch.setattr(run_eval, "APPLICATIONS", [("ada-auto", {"applicant_name": "Ada Lovelace"})])
    monkeypatch.setattr(run_eval, "build_model", lambda settings: object())
    monkeypatch.setattr(run_eval, "build_store", lambda settings: object())
    monkeypatch.setattr(run_eval, "configure_tracing", lambda: object())

    def fake_run(application: object, model: object, store: object, tracer: object) -> PipelineResult:
        logging.getLogger("underwriting").info("agent=underwriting duration_ms=9.0")
        return PipelineResult(final_decision="approve", intake=_intake())

    monkeypatch.setattr(run_eval, "run", fake_run)
    logging.getLogger("underwriting").setLevel(logging.INFO)
    run_eval.main()

    run_file = next(runs.glob("*.jsonl"))
    log_file = next(logs.glob("*.jsonl"))
    run_row = json.loads(run_file.read_text().splitlines()[0])
    log_row = json.loads(log_file.read_text().splitlines()[0])
    assert run_row["run_id"] == "ada-auto"
    assert run_row["final_decision"] == "approve"
    assert run_row["intake"]["applicant_name"] == "Ada Lovelace"
    assert log_row["underwriting"] == {"duration_ms": 9.0}
    assert log_row["final_decision"] == "approve"