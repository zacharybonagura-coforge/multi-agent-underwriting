Score this insurance application. Reply with JSON only.

Use only the fields in the case. Do not invent facts that are not written there.
risk_score must be a number from 0 to 100, or null.
risk_factors must be a list of the input field names that moved the score.
tier must be "low" when the score is 0 to 33, "medium" when it is 34 to 66, and "high" when it is 67 to 100, or null.
If product, coverage_amount, stated_income, or credit_band is null, include "missing_fields" in risk_factors and set tier to "high".

Fields: risk_score, risk_factors, tier.

Case:
{{payload}}