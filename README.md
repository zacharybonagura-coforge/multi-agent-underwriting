# Multi-agent underwriting

Insurance applications through a fixed four-agent pipeline. Intake normalizes a messy form, enrichment looks up credit, claims, and asset facts by email and product, risk scores the case into a tier, and recommendation approves, denies, or escalates. The orchestrator passes messages forward, retries a failed agent, and appends a review ticket when the run stops early or the decision is escalate.

Default stack: Ollama `qwen3:8b` and a JSON applicant store at `data/applicants.json`.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com), for the interactive CLI, `run_eval.py`, and the live eval

```bash
ollama pull qwen3:8b
```

## Setup

### Ollama

Start the Ollama app, or run `ollama serve`. Check that it is up:

```bash
curl -s http://localhost:11434/api/tags
```

The app's default `OLLAMA_HOST` is `http://host.docker.internal:11434`, which reaches Ollama on the host from the devcontainer. When you run Python on the host, or on the self-hosted runner, set `OLLAMA_HOST=http://localhost:11434`.

### JSON store

Applicant credit, claims, and assets are one file. There is no database to start.

| File | Contents |
| --- | --- |
| `data/applicants.json` | Lookup rows: `applicant_email`, `product`, `credit_file`, `claims`, `asset` |
| `data/golden/golden.jsonl` | 31 eval cases: expected intake, enrichment, risk tier, recommendation, and `final_decision` |
| `docs/eval-run.jsonl` | Recorded eval run used by `compare_eval.py` |
| `docs/eval-run-logs.jsonl` | Token and latency traces used by `cost_report.py` |
| `docs/cost-latency.md` | Table regenerated from those traces |

Enrichment matches `applicant_email` and `product`. There is no name lookup. A missing email, a malformed email, or a store row with null `credit_file` / `claims` / `asset` stops the pipeline and escalates.

An escalate (or an agent that fails after retries) appends a line to `reviews/human-review.jsonl`. `runs/` and `logs/` hold timestamped eval JSONL. Those three directories are gitignored.

### Python

```bash
uv sync
```

## Run

From the repo root, with `src` on `PYTHONPATH`:

```bash
# Interactive application. Prompts for applicant_name, applicant_email,
# date_of_birth, address, product, coverage_amount, and stated_income.
# Type quit at any prompt to exit.
PYTHONPATH=src uv run python src/cli.py

# 31 mock applications through intake, enrichment, risk, and recommendation.
# Writes runs/<UTC timestamp>.jsonl and logs/<UTC timestamp>.jsonl.
PYTHONPATH=src uv run python src/run_eval.py

# Score docs/eval-run.jsonl against data/golden/golden.jsonl.
PYTHONPATH=src uv run python src/compare_eval.py

# Rebuild docs/cost-latency.md from docs/eval-run-logs.jsonl.
PYTHONPATH=src uv run python src/cost_report.py

# Demo: Ollama for intake and enrichment, then time out risk until the
# orchestrator retries and escalates.
PYTHONPATH=src uv run python src/show_failure.py
```

`runs/`, `logs/`, and `reviews/` are gitignored. Copy a timestamped file into `docs/` if you want it in git. A recorded eval is [docs/eval-run.jsonl](docs/eval-run.jsonl). Token cost and wait time are in [docs/cost-latency.md](docs/cost-latency.md). Message-passing rules are in [docs/state-and-memory.md](docs/state-and-memory.md).

## Changing settings for a run

`Settings.from_env()` reads the process environment when a module imports `config`. Export a variable for the rest of the shell session, or prefix one command. Unset variables fall back to the Environment table below.

```bash
export OLLAMA_HOST=http://localhost:11434
export GENERATION_MODEL=qwen3:8b
export MAX_RETRIES=3
PYTHONPATH=src uv run python src/run_eval.py
```

```bash
OLLAMA_HOST=http://localhost:11434 \
  PYTHONPATH=src uv run python src/cli.py
```

`cli.py` and `pipeline.py` read these values at import. Set them before the process starts.

## Applications

Each application is `applicant_name`, `applicant_email`, `date_of_birth`, `address`, `product`, `coverage_amount`, and `stated_income`. Credit, claims, and asset facts are not on the request. They come from `data/applicants.json`.

`src/run_eval.py` runs these 31 cases. `data/golden/golden.jsonl` scores the same `run_id`s. Golden compares intake (except that `asset_facts` is skipped), enrichment bands and counts, risk `tier`, recommendation `decision`, and `final_decision`.

| Label | Expected | Why |
| --- | --- | --- |
| `ada-lovelace-auto` | escalate | Medium tier (good credit, one claim) |
| `ada-lovelace-home` | approve | Low tier, no claims |
| `katherine-johnson-auto` | approve | Low tier, excellent credit |
| `katherine-johnson-home` | deny | Missing `stated_income`; risk forces high |
| `margaret-hamilton-life` | approve | Low tier, excellent credit |
| `alan-turing-auto` | deny | High tier, fair credit, two claims |
| `alan-turing-home` | deny | Missing `coverage_amount`; risk forces high |
| `dorothy-vaughan-life` | approve | Low tier, no claims |
| `hedy-lamarr-auto` | escalate | Medium tier, one claim |
| `hedy-lamarr-home` | approve | Low tier; messy date is missing, still scored |
| `grace-hopper-auto` | approve | Low tier |
| `grace-hopper-life` | escalate | No life row in the store |
| `john-von-neumann-life` | deny | High tier, smoker, two hospital claims |
| `john-von-neumann-home` | deny | High tier, poor credit, three claims |
| `mary-jackson-auto` | approve | Low tier |
| `mary-jackson-life` | approve | Low tier; messy product and cents normalize |
| `claude-shannon-home` | escalate | Medium tier, one claim |
| `claude-shannon-auto` | deny | High tier, two vehicles, two at-fault claims |
| `radia-perlman-life` | approve | Low tier |
| `edsger-dijkstra-life` | escalate | Email not in the store |
| `barbara-liskov-auto` | escalate | Medium tier, one claim |
| `barbara-liskov-home` | escalate | Medium tier, one claim |
| `leslie-lamport-home` | escalate | Medium tier, one claim |
| `frances-allen-auto` | escalate | Medium tier, one claim |
| `tim-berners-lee-auto` | escalate | Store row has unusable `credit_file` |
| `vint-cerf-home` | escalate | Medium tier, one claim |
| `bob-kahn-life` | escalate | Store `asset` is empty |
| `donald-knuth-auto` | escalate | Store credit and claims are null |
| `adele-goldberg-life` | escalate | Email not in the store |
| `barbara-liskov-life` | escalate | Auto and home rows exist; no life row |
| `guido-van-rossum-renters` | escalate | `RENTERS` is not `auto`, `home`, or `life` |

Covered products: `auto`, `home`, `life`. Lookup is email plus product. Intake treats a blank name, email, or address as missing, keeps ISO dates, and rounds dollars to cents. The orchestrator rejects a missing or malformed email before enrichment.

## Pipeline

`cli.py` and `run_eval.py` share `pipeline.run`. One model, store, and tracer stay open for the process.

1. **Intake.** Fill `intake.v1.md`. Normalize the raw form to JSON. `product` must be `auto`, `home`, or `life`. `date_of_birth` must be `YYYY-MM-DD`. Amounts are floats. Empty email, or an email that does not match `local@domain.tld`, escalates to review and skips the rest.
2. **Enrichment.** Fill `enrichment.v1.md` with the store row for that email and product. `credit_band` is `records.credit_file`. `prior_claims_count` is the length of `records.claims`. `asset_facts` is `records.asset` (a list is joined with `"; "`). A null records object, or any of those three fields still null, escalates as an incomplete enrichment record.
3. **Risk.** Fill `risk.v1.md`. `risk_score` is 0 to 100. The orchestrator overwrites `tier`: 0–33 `low`, 34–66 `medium`, 67–100 `high`. If `product`, `coverage_amount`, `stated_income`, or `credit_band` is null, tier is `high`.
4. **Recommendation.** Fill `recommendation.v1.md`. Approve on `low`, deny on `high`, escalate on `medium` or a null score/tier.
5. **Retry.** Each agent call retries up to `MAX_RETRIES` (default 3), appending the previous error to the next prompt. Exhausted retries escalate with the agents that already finished.
6. **Review.** Escalate (including a medium-tier approve path that still escalates) appends one JSON line to `reviews/human-review.jsonl`.

Ollama is called at `{OLLAMA_HOST}/api/generate` with temperature 0, seed 42, `think: false`, and `stream: false`. Timeout is 120 seconds.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `GENERATION_PROVIDER` | `ollama` | Generation adapter name. `build_model` constructs `OllamaAdapter` |
| `GENERATION_MODEL` | `qwen3:8b` | Ollama model id |
| `STORE_PROVIDER` | `json` | Store adapter name. `build_store` opens `APPLICANTS_PATH` |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama base URL |
| `MAX_RETRIES` | `3` | Extra attempts after the first agent call fails |
| `APPLICANTS_PATH` | `data/applicants.json` | Credit, claims, and asset rows |
| `RUNS_DIR` | `runs` | JSONL output for `run_eval.py` |
| `LOGS_DIR` | `logs` | Trace JSONL for `run_eval.py` |
| `REVIEWS_PATH` | `reviews/human-review.jsonl` | Escalated cases |

Names are enums in `src/settings/enums.py`. Supported values: `ollama` and `json`. Any other `GENERATION_PROVIDER` or `STORE_PROVIDER` fails when `Settings.from_env()` runs.

## Layout

```text
src/
  pipeline.py                 # intake → enrichment → risk → recommendation
  cli.py                      # interactive application
  run_eval.py                 # 31 mock applications; writes runs/ and logs/
  compare_eval.py             # score docs/eval-run.jsonl against golden.jsonl
  cost_report.py              # write docs/cost-latency.md from eval-run-logs.jsonl
  show_failure.py             # risk timeout demo
  observability.py            # OpenTelemetry spans as INFO logs
  agents/
    intake.py
    enrichment.py
    risk.py
    recommendation.py
    model_io.py               # render_prompt, parse_message
  prompts/
    intake.v1.md
    enrichment.v1.md
    risk.v1.md
    recommendation.v1.md
    repository.py
  model/
    base.py                   # ModelAdapter, Generation, ModelTimeoutError
    ollama.py                 # /api/generate
  store/
    base.py                   # Store protocol
    json.py                   # one JSON file
  settings/
    config.py                 # Settings.from_env()
    enums.py
    factory.py                # build_model, build_store
data/
  applicants.json
  golden/golden.jsonl         # 31 cases
docs/
  state-and-memory.md
  eval-run.jsonl
  eval-run-logs.jsonl
  cost-latency.md
tests/unit/                   # fakes; no Ollama
tests/integration/            # live host, marked integration
.github/workflows/checks_mau.yaml
```

## Checks

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest -m "not integration" --cov --cov-report=term-missing
```

Coverage `fail_under` is 100 on `src`. `src/store/*`, `src/model/*`, and `src/settings/factory.py` are omitted.

`tests/integration/test_eval.py` is marked `integration`. It runs `run_eval.main()` and scores the newest file in `runs/` against `data/golden/golden.jsonl`. Intake, enrichment, risk tier, recommendation decision, and `final_decision` must match on every `run_id`. `asset_facts` is not compared. The other integration modules each make one live call to intake, enrichment, risk, or recommendation.

```bash
OLLAMA_HOST=http://localhost:11434 uv run pytest -m integration
```

CI (`.github/workflows/checks_mau.yaml`) runs on pull requests and on pushes to `main` and `feature/multi-agent-setup`:

- `checks` (GitHub-hosted): `uv sync --frozen`, mypy, ruff, `pytest -m "not integration" --cov`.
- `live-eval` (self-hosted runner): `pytest -m integration` with `OLLAMA_HOST=http://localhost:11434`. The runner machine also needs Ollama serving `qwen3:8b`.
