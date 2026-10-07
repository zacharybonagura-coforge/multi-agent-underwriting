Add underwriting facts for this applicant. Reply with JSON only.

Use only the records object in the lookup. Do not infer a fact that is not written there.
credit_band must be records.credit_file when it is "excellent", "good", "fair", or "poor". Otherwise null.
prior_claims_count must be the number of items in records.claims, or null.
asset_facts must be records.asset when it is a string.
When records.asset is a list, join the items into one string separated by "; ".
Use null when records.asset is missing or empty.
If records is null, every field is null.

Fields: credit_band, prior_claims_count, asset_facts.

Lookup:
{{payload}}