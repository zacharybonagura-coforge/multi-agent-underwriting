"""Live eval run compared with the golden set."""

from pathlib import Path

import pytest

from compare_eval import GOLDEN, _diffs, _load
from run_eval import main
from settings.config import Settings

pytestmark = pytest.mark.integration


def test_live_eval_matches_the_golden_set() -> None:
    """Run every application and require every golden field to match."""
    settings = Settings.from_env()
    main()
    latest = max(Path(settings.runs_dir).glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    golden = {row["run_id"]: row["expected"] for row in _load(GOLDEN)}
    ran = {row["run_id"]: row for row in _load(latest)}
    failures: list[str] = []
    for run_id, expected in golden.items():
        row = ran.get(run_id)
        if row is None:
            failures.append(f"{run_id}: missing from the eval run")
            continue
        diffs = _diffs(
            {
                "intake": row.get("intake"),
                "enrichment": row.get("enrichment"),
                "risk": row.get("risk"),
                "recommendation": row.get("recommendation"),
                "final_decision": row.get("final_decision"),
            },
            expected,
            run_id,
        )
        if diffs:
            failures.append("\n".join(diffs))
    assert not failures, "\n\n".join(failures)