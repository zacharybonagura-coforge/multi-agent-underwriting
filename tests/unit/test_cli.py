"""Unit tests for the interactive CLI."""

from typing import Any, Literal

import pytest

import cli
from agents.recommendation import RecommendationMessage, RecommendationResult
from pipeline import PipelineResult

Decision = Literal["approve", "deny", "escalate"]


def _answers(*values: str):
    lines = iter(values)

    def fake_input(prompt: str) -> str:
        return next(lines)

    return fake_input


def _complete() -> tuple[str, ...]:
    return (
        "Ada Lovelace",
        "ada.lovelace@coforge.com",
        "1815-12-10",
        "12 St James's Square, London SW1Y 4LE, United Kingdom",
        "AUTO",
        "16000.456",
        "120000",
    )


def _result(
    *,
    decision: Decision = "approve",
    rationale: str | None = "the tier is low",
) -> PipelineResult:
    recommendation = None
    if rationale is not None:
        recommendation = RecommendationResult(
            message=RecommendationMessage(decision=decision, rationale=rationale),
            input_tokens=1,
            output_tokens=1,
        )
    return PipelineResult(final_decision=decision, recommendation=recommendation)


def _stub_pipeline(monkeypatch: pytest.MonkeyPatch, result: PipelineResult | None = None) -> list[dict[str, Any]]:
    ran: list[dict[str, Any]] = []
    monkeypatch.setattr(cli, "build_model", lambda settings: object())
    monkeypatch.setattr(cli, "build_store", lambda settings: object())
    monkeypatch.setattr(cli, "configure_tracing", lambda: object())
    monkeypatch.setattr(
        cli,
        "run",
        lambda application, model, store, tracer: ran.append(application) or (result or _result()),
    )
    return ran


def test_read_request_returns_a_normalized_application(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", _answers(*_complete()))
    assert cli.read_request() == {
        "applicant_name": "Ada Lovelace",
        "applicant_email": "ada.lovelace@coforge.com",
        "date_of_birth": "1815-12-10",
        "address": "12 St James's Square, London SW1Y 4LE, United Kingdom",
        "product": "auto",
        "coverage_amount": 16000.46,
        "stated_income": 120000.0,
    }


def test_print_decision_includes_the_rationale(capsys: pytest.CaptureFixture[str]) -> None:
    cli.print_decision(_result())
    out = capsys.readouterr().out
    assert "Final Answer: approve" in out
    assert "Rationale: the tier is low" in out


def test_loop_runs_one_application_then_stops(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", _answers(*_complete(), "quit"))
    ran = _stub_pipeline(monkeypatch)
    cli.loop()
    out = capsys.readouterr().out
    assert ran[0]["applicant_email"] == "ada.lovelace@coforge.com"
    assert "=== Ada Lovelace auto ===" in out
    assert "Final Answer: approve" in out
    assert "bye" in out


def test_main_prints_usage_then_runs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "loop", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert "Type quit at any prompt to exit." in out
    assert "date_of_birth must be YYYY-MM-DD" in out


@pytest.mark.parametrize("product", ["auto", "HOME", "  life  "])
def test_product_accepts_each_product(product: str) -> None:
    assert cli._product(product) == product.strip().lower()


def test_money_rounds_to_cents() -> None:
    assert cli._money("16000.456") == 16000.46


def test_date_keeps_an_iso_date() -> None:
    assert cli._date("1815-12-10") == "1815-12-10"


def test_text_keeps_a_name() -> None:
    assert cli._text("Ada Lovelace") == "Ada Lovelace"


@pytest.mark.parametrize("value", ["quit", "QUIT", " Quit "])
def test_ask_returns_none_on_quit(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: value)
    assert cli._ask("applicant_name") is None


def test_ask_returns_none_on_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert cli._ask("applicant_name") is None


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_text_is_missing(value: str) -> None:
    assert cli._text(value) is None


@pytest.mark.parametrize("value", ["", "   ", "December 10, 1815", "1815/12/10"])
def test_unusable_date_is_missing(value: str) -> None:
    assert cli._date(value) is None


@pytest.mark.parametrize("value", ["boat", "", "   ", "renters"])
def test_unusable_product_is_missing(value: str) -> None:
    assert cli._product(value) is None


@pytest.mark.parametrize("value", ["", "   ", "hi"])
def test_unusable_money_is_missing(value: str) -> None:
    assert cli._money(value) is None


@pytest.mark.parametrize("quit_after", range(7))
def test_read_request_returns_none_when_the_user_quits(
    monkeypatch: pytest.MonkeyPatch, quit_after: int
) -> None:
    answers = list(_complete()[:quit_after]) + ["quit"]
    monkeypatch.setattr("builtins.input", _answers(*answers))
    assert cli.read_request() is None


def test_read_request_treats_blank_fields_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", _answers("", "", "", "", "boat", "", "hi"))
    assert cli.read_request() == {
        "applicant_name": None,
        "applicant_email": None,
        "date_of_birth": None,
        "address": None,
        "product": None,
        "coverage_amount": None,
        "stated_income": None,
    }


def test_print_decision_skips_rationale_without_recommendation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.print_decision(PipelineResult(final_decision="escalate"))
    out = capsys.readouterr().out
    assert "Final Answer: escalate" in out
    assert "Rationale:" not in out


def test_main_prints_bye_on_ctrl_c(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "loop", boom)
    cli.main()
    assert "bye" in capsys.readouterr().out