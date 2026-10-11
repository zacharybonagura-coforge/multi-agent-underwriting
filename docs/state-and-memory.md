# State and memory: message passing

## Decision

This pipeline uses explicit message passing. There is no shared case store. Each agent is a function. Its return value is the next agent's input.

```bash
raw application -> intake_agent -> enrichment_agent -> risk_scoring_agent -> recommendation_agent -> final_recommendation
```

The orchestrator only forwards those return values. Agents do not read or write a common dictionary, file, or database.

## Why

The underwriting flow is a fixed workflow: intake, then enrichment, then risk scoring, then a recommendation. The order does not change per application, and no agent chooses which agent runs next. This is great for message passing, where the handoff is the function call.

Each agent stays testable on its own. A unit test builds one known input message, calls one function, and checks that message's output. Nothing else has to be running.

A timeout is contained. If risk scoring fails after retry, the orchestrator escalates with the intake and enrichment messages it already holds. Recommendation never runs on a missing score, so the pipeline cannot emit an approve or deny from incomplete data.

## Message rule

Each agent returns only the section it computed. The orchestrator keeps those return values and builds the next input from the fields that agent uses.

| Agent | Reads | Produces |
|---|---|---|
| `intake_agent` | Raw application | Normalized application and `missing_fields` |
| `enrichment_agent` | Identity, product, and `missing_fields` | `credit_band`, `prior_claims_count`, `asset_facts` |
| `risk_scoring_agent` | Product, coverage, income, enrichment facts, and `missing_fields` | `risk_score`, `risk_factors`, `tier` |
| `recommendation_agent` | `risk_score`, `risk_factors`, and `tier` | `decision` and `rationale` |

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

Reads `applicant_name`, `applicant_email`, `date_of_birth`, `address`, `product`, and `missing_fields`. These are the lookup keys. Coverage and income are not used here.

Produces:

- `credit_band`
- `prior_claims_count`
- `asset_facts`: vehicle, property, or health facts for the product

### `risk_scoring_agent`

Reads `product`, `coverage_amount`, `stated_income`, `credit_band`, `prior_claims_count`, `asset_facts`, and `missing_fields`. Name, date of birth, and address are not used to score the case.

Produces:

- `risk_score`: number from 0 to 100
- `risk_factors`: the input fields that moved the score
- `tier`: `low`, `medium`, or `high`

### `recommendation_agent`

Reads `risk_score`, `risk_factors`, and `tier`. The factors already name the facts behind the score, so this agent does not read the application or the enrichment record.

Produces:

- `decision`: `approve`, `deny`, or `escalate`
- `rationale`: why that decision follows from the score and the factors

`escalate` means a person should underwrite the case. When risk scoring times out, the orchestrator escalates with the intake and enrichment results it already holds, and this agent does not run.