# State and memory: message passing

## Decision

This pipeline uses explicit message passing. There is no shared case object that agents mutate. Each agent is a function. The orchestrator keeps its return value and builds the next agent's input from the fields that agent uses.

```text
raw application -> intake_agent -> enrichment_agent -> risk_agent -> recommendation_agent -> final_decision
```

Agents do not read or write a common case dictionary. Enrichment does read a lookup file, `data/applicants.json`, through `Store`. The orchestrator appends escalated cases to `reviews/human-review.jsonl`.

## Why

The underwriting flow is a fixed workflow: intake, then enrichment, then risk scoring, then a recommendation. The order does not change per application, and no agent chooses which agent runs next. This is great for message passing, where the handoff is the function call.

Each agent stays testable on its own. A unit test builds one known input message, calls one function, and checks that message's output. Nothing else has to be running.

A failure is contained. If an agent fails after retries, or the orchestrator rejects its output, later agents do not run. The orchestrator escalates with the messages it already holds, so the pipeline cannot emit an approve or deny from incomplete data.

## Message rule

Each agent returns only the section it computed. The orchestrator keeps those return values, retries a failed call, gates the next step, and builds the next input.

| Agent | Reads | Produces |
|---|---|---|
| `intake_agent` | Raw application | Normalized application and `missing_fields` |
| `enrichment_agent` | Identity, product, and `missing_fields`; looks up by `applicant_email` and `product` | `credit_band`, `prior_claims_count`, `asset_facts` |
| `risk_agent` | Product, coverage, income, enrichment facts, and `missing_fields` | `risk_score`, `risk_factors`, `tier` |
| `recommendation_agent` | `risk_score`, `risk_factors`, and `tier` | `decision` and `rationale` |

## Orchestrator

`pipeline.run` holds the messages. It does not pass the full intake record into every later agent.

It retries each agent up to `MAX_RETRIES` (default 3), appending the previous error to the next prompt. Exhausted retries escalate with whatever agents already finished.

It also stops before later agents when:

- `applicant_email` is missing or does not match `local@domain.tld`
- `credit_band`, `prior_claims_count`, or `asset_facts` is still null
- `recommendation` returns `escalate`, or `decision` is null

Those paths, and a successful `escalate` from recommendation, append one JSON line to `reviews/human-review.jsonl`.

## Data each agent reads and produces

### Raw application

- `applicant_name`
- `applicant_email`
- `date_of_birth`
- `address`
- `product` (`auto`, `home`, or `life`)
- `coverage_amount`
- `stated_income`

### `intake_agent`

Reads the raw application.

Produces:

- `applicant_name`
- `applicant_email`
- `date_of_birth`
- `address`
- `product`
- `coverage_amount`
- `stated_income`
- `missing_fields`: required fields that were absent or unusable

### `enrichment_agent`

Reads `applicant_name`, `applicant_email`, `date_of_birth`, `address`, `product`, and `missing_fields`. Coverage and income are not used here.

The store lookup is `applicant_email` plus `product`. Name, date of birth, address, and `missing_fields` are in the prompt payload. The prompt tells the model to use only the `records` object from the store.

Produces:

- `credit_band`
- `prior_claims_count`
- `asset_facts`: vehicle, property, or health facts for the product

### `risk_agent`

Reads `product`, `coverage_amount`, `stated_income`, `credit_band`, `prior_claims_count`, `asset_facts`, and `missing_fields`. Name, date of birth, and address are not used to score the case.

Produces:

- `risk_score`: number from 0 to 100
- `risk_factors`: the input fields that moved the score
- `tier`: `low`, `medium`, or `high`. The agent overwrites the model's tier: 0–33 `low`, 34–66 `medium`, 67–100 `high`. If `product`, `coverage_amount`, `stated_income`, or `credit_band` is null, tier is `high`.

### `recommendation_agent`

Reads `risk_score`, `risk_factors`, and `tier`. The factors already name the facts behind the score, so this agent does not read the application or the enrichment record.

Produces:

- `decision`: `approve`, `deny`, or `escalate`
- `rationale`: why that decision follows from the score and the factors

`escalate` means a person should underwrite the case. When intake, enrichment, or risk stops the run, this agent does not run. The orchestrator still writes a review line with the messages it holds.
