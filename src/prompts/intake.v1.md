Normalize this insurance application. Reply with JSON only.

Use null for a field that is absent or unusable.
product must be "auto", "home", or "life", or null.
date_of_birth must be YYYY-MM-DD, or null.
coverage_amount and stated_income must be float, or null.

Fields: applicant_name, date_of_birth, address, product, coverage_amount, stated_income.

Application:
{{payload}}