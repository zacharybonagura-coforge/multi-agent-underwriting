Decide this insurance application. Reply with JSON only.

Use only the risk score, risk factors, and tier in the case. Do not invent facts that are not written there.
decision must be "approve", "deny", or "escalate".
Approve when tier is "low". Deny when tier is "high". Escalate when tier is "medium".
If risk_score or tier is null, decision must be "escalate".
rationale must be one plain sentence a person would say. Explain why this score and these factors lead to the decision. Say the factors in ordinary words, such as "a prior claim" for prior_claims_count and "the coverage amount" for coverage_amount. Do not list the raw field names. Use null when you cannot explain the decision.

Fields: decision, rationale.

Case:
{{payload}}