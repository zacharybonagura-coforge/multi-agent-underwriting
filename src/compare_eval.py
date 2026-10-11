"""Compare an eval run with the golden expectations."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden" / "golden.jsonl"
EVAL_RUN = ROOT / "docs" / "eval-run.jsonl"


def _load(path: Path) -> list[dict[str, Any]]:
    """Read one JSON object from each non-blank line."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _diffs(actual: object, expected: object, path: str) -> list[str]:
    """Return the golden fields that do not match."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: {actual!r} != {expected!r}"]
        found: list[str] = []
        for key, value in expected.items():
            if key == "asset_facts":
                continue
            found.extend(_diffs(actual.get(key), value, f"{path}.{key}"))
        return found
    if isinstance(expected, float) and isinstance(actual, (int, float)) \
        and not isinstance(actual, bool) and round(float(actual), 2) == round(expected, 2):
            return []
    if actual != expected:
        return [f"{path}: {actual!r} != {expected!r}"]
    return []


def main() -> None:
    """Print each mismatch, then the pass and fail counts."""
    golden = {row["run_id"]: row["expected"] for row in _load(GOLDEN)}
    ran = {row["run_id"]: row for row in _load(EVAL_RUN)}
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
    passed = len(golden) - len(failures)
    if failures:
        print("\n\n".join(failures))
        print()
    print(f"{passed} passed, {len(failures)} failed, {len(golden)} expected")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()