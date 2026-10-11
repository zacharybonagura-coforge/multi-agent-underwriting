"""Unit tests for comparing an eval run with golden."""

import json

import pytest

import compare_eval


def _write(path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows) + "\n")


def test_load_skips_blank_lines(tmp_path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"run_id": "a"}\n\n{"run_id": "b"}\n')
    assert [row["run_id"] for row in compare_eval._load(path)] == ["a", "b"]


def test_diffs_skips_asset_facts() -> None:
    expected = {"enrichment": {"credit_band": "good", "asset_facts": "civic"}}
    actual = {"enrichment": {"credit_band": "good", "asset_facts": "other"}}
    assert compare_eval._diffs(actual, expected, "ada") == []


def test_diffs_when_actual_is_not_a_dict() -> None:
    assert compare_eval._diffs(None, {"tier": "low"}, "ada.risk") == [
        "ada.risk: None != {'tier': 'low'}"
    ]


def test_diffs_accepts_floats_to_two_decimals() -> None:
    assert compare_eval._diffs(16000.46, 16000.461, "ada.coverage") == []
    assert compare_eval._diffs(120000, 120000.0, "ada.income") == []


def test_diffs_rejects_a_bool_as_a_float() -> None:
    assert compare_eval._diffs(True, 1.001, "flag") == ["flag: True != 1.001"]


def test_diffs_reports_a_value_mismatch() -> None:
    assert compare_eval._diffs("deny", "approve", "ada.decision") == [
        "ada.decision: 'deny' != 'approve'"
    ]


def test_main_passes_when_every_golden_field_matches(
    tmp_path, monkeypatch, capsys
) -> None:
    golden = tmp_path / "golden.jsonl"
    ran = tmp_path / "run.jsonl"
    _write(golden, [{"run_id": "ada-auto", "expected": {"final_decision": "approve", "risk": {"tier": "low"}}}])
    _write(ran, [{"run_id": "ada-auto", "final_decision": "approve", "risk": {"tier": "low"}}])
    monkeypatch.setattr(compare_eval, "GOLDEN", golden)
    monkeypatch.setattr(compare_eval, "EVAL_RUN", ran)
    compare_eval.main()
    assert capsys.readouterr().out == "1 passed, 0 failed, 1 expected\n"


def test_main_fails_on_a_mismatch_or_a_missing_run(
    tmp_path, monkeypatch, capsys
) -> None:
    golden = tmp_path / "golden.jsonl"
    ran = tmp_path / "run.jsonl"
    _write(
        golden,
        [
            {"run_id": "ada-auto", "expected": {"final_decision": "approve"}},
            {"run_id": "ada-home", "expected": {"final_decision": "deny"}},
        ],
    )
    _write(ran, [{"run_id": "ada-auto", "final_decision": "deny"}])
    monkeypatch.setattr(compare_eval, "GOLDEN", golden)
    monkeypatch.setattr(compare_eval, "EVAL_RUN", ran)
    with pytest.raises(SystemExit) as exited:
        compare_eval.main()
    assert exited.value.code == 1
    out = capsys.readouterr().out
    assert "ada-auto.final_decision: 'deny' != 'approve'" in out
    assert "ada-home: missing from the eval run" in out
    assert "0 passed, 2 failed, 2 expected" in out