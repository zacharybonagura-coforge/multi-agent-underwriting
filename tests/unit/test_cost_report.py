"""Unit tests for the cost and latency table."""

import json

import cost_report


def test_load_skips_blank_lines(tmp_path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text('{"run_id": "a"}\n\n{"run_id": "b"}\n')
    assert [row["run_id"] for row in cost_report._load(path)] == ["a", "b"]


def test_case_sums_tokens_and_converts_latency() -> None:
    row = {
        "intake": {"input_tokens": 100, "output_tokens": 20},
        "enrichment": {"input_tokens": 50, "output_tokens": 10},
        "risk": {"input_tokens": 30, "output_tokens": 5},
        "recommendation": {"input_tokens": 20, "output_tokens": 5},
        "underwriting": {"duration_ms": 2500},
    }
    input_tokens, output_tokens, cost, latency_s = cost_report._case(row)
    assert input_tokens == 200
    assert output_tokens == 40
    assert latency_s == 2.5
    assert cost == _hosted_cost(200, 40)


def _hosted_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * cost_report.INPUT_PER_MILLION
        + output_tokens / 1_000_000 * cost_report.OUTPUT_PER_MILLION
    )


def test_case_treats_missing_spans_as_zero() -> None:
    input_tokens, output_tokens, cost, latency_s = cost_report._case({"run_id": "ada"})
    assert input_tokens == 0
    assert output_tokens == 0
    assert cost == 0
    assert latency_s == 0


def test_main_writes_the_table_and_the_means(tmp_path, monkeypatch) -> None:
    log = tmp_path / "log.jsonl"
    out = tmp_path / "cost.md"
    rows = [
        {
            "run_id": "fast",
            "intake": {"input_tokens": 100, "output_tokens": 10},
            "underwriting": {"duration_ms": 1000},
        },
        {
            "run_id": "slow",
            "intake": {"input_tokens": 300, "output_tokens": 30},
            "risk": None,
            "recommendation": None,
            "underwriting": {"duration_ms": 3000},
        },
    ]
    log.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(cost_report, "LOG", log)
    monkeypatch.setattr(cost_report, "OUT", out)
    cost_report.main()
    text = out.read_text()
    assert "| fast | 100 | 10 |" in text
    assert "| slow | 300 | 30 |" in text
    assert "| **mean** | **200** | **20** |" in text
    assert "The 2 cases used 400 input tokens and 40 output tokens" in text
    assert "slowest case is 3.00s" in text