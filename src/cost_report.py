"""Write a cost and latency table from an eval log."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "eval-run-logs.jsonl"
OUT = ROOT / "docs" / "cost-latency.md"

INPUT_PER_MILLION = 0.18
OUTPUT_PER_MILLION = 0.70
AGENTS = ("intake", "enrichment", "risk", "recommendation")


def _load(path: Path) -> list[dict[str, Any]]:
    """Read one JSON object from each non-blank line."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _case(row: dict[str, Any]) -> tuple[int, int, float, float]:
    """Return input tokens, output tokens, hosted cost, and latency in seconds."""
    input_tokens = 0
    output_tokens = 0
    for name in AGENTS:
        span = row.get(name) or {}
        input_tokens += int(span.get("input_tokens") or 0)
        output_tokens += int(span.get("output_tokens") or 0)
    latency_s = float((row.get("underwriting") or {}).get("duration_ms") or 0) / 1000
    cost = (
        input_tokens / 1_000_000 * INPUT_PER_MILLION
        + output_tokens / 1_000_000 * OUTPUT_PER_MILLION
    )
    return input_tokens, output_tokens, cost, latency_s


def main() -> None:
    """Write the per-case table and the column means."""
    rows = _load(LOG)
    counted = [((row["run_id"],) + _case(row)) for row in rows]
    count = len(counted)
    total_in = sum(item[1] for item in counted)
    total_out = sum(item[2] for item in counted)
    total_cost = sum(item[3] for item in counted)
    total_latency = sum(item[4] for item in counted)
    lines = [
        (
            "Token cost uses Alibaba's international Qwen3-8B rate: "
            f"${INPUT_PER_MILLION:.2f} per million input tokens and "
            f"${OUTPUT_PER_MILLION:.2f} per million output tokens. "
            "Latency is the underwriting span."
        ),
        "",
        "| run_id | input tokens | output tokens | cost | latency |",
        "|---|---:|---:|---:|---:|",
    ]
    for run_id, input_tokens, output_tokens, cost, latency_s in counted:
        lines.append(
            f"| {run_id} | {input_tokens} | {output_tokens} | ${cost:.6f} | {latency_s:.2f}s |"
        )
    lines.append(
        f"| **mean** | **{total_in / count:.0f}** | **{total_out / count:.0f}** | "
        f"**${total_cost / count:.6f}** | **{total_latency / count:.2f}s** |"
    )
    lines.extend([
        "",
        (
            f"The {count} cases used {total_in} input tokens and {total_out} output tokens, "
            f"cost ${total_cost:.4f}, and took {total_latency:.0f} seconds. "
            f"The mean wait is {total_latency / count:.2f}s and the slowest case is "
            f"{max(item[4] for item in counted):.2f}s."
        ),
        "",
    ])
    OUT.write_text("\n".join(lines))


if __name__ == "__main__":
    main()