# Declared delta — recover one synthetic QA provider rejection

Authority: the owner's 2026-10-02 continuation and the existing committed
`quillmd-v1-private-api-testing-standing-20260930` record. This adds no spending
grant. The synthetic QA database is `quillmd_qa_standing_20261002`, served by
`v1-sonnet5-qa-pg` at `127.0.0.1:55731`. Installed production on port55438,
installed services9130/9131, public maintenance and all other campaigns remain
unchanged.

The historical request is attempt003 of campaign
`quillmd-v1-standing-api-testing-20261002`, job
`9c432a90-8d63-4238-b9da-a7f6a1e24c35`. Its preserved provider response is HTTP400
`invalid_request_error`, request `req_011CfcS91wTJvP4v9WqzJt1d`. Original response
SHA256: `9b9d5893f46ddb5d5701165a39bcb4b3009c101d9a1d1e1c22edbd692801b732`.
The transport capture shows one request rejected for schema complexity, with no
message or metered usage response. No invoice or authenticated cost report is
available; this act does not manufacture such evidence.

Before execution, the lead verified the original response hash and read-only QA
rows: one reconciliation job, one held reservation of `$0.374595`, no receipt or
usage for that job, one nonstaff synthetic user, three immutable ledger entries.
Historical attempt/outcome/stage files remain intact, including the failed
qualification and `$0.274703` historical uncertain exposure.

Run only through the declaration gate:

```bash
bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20261002-quillmd-v1-qa-http400-resolution.md -- rebuild/.venv/bin/python -B rebuild/ops/recover_qa_http_rejection.py
```

Expected delta:

- A protected full SQL backup of this exact QA database, before any mutation;
  captured row/financial baseline and original evidence hashes.
- One new synthetic staff account with a confirmed synthetic MFA device and a
  seeding audit, exclusively for this resolution. No welcome credit, membership,
  wallet or payment is created. Its generated credentials live only in a0700
  directory and a0600 file, never argv, chat, logs or reports.
- A temporary admin listener at `127.0.0.1:9162` authenticates by password and
  TOTP, submits the existing application's `release_no_cost` resolution view,
  then stops. No provider credential is made available to this process and no
  provider request or automatic retry occurs.
- The exact reconciliation job becomes failed/resolved with its ended request
  key. Its one reservation becomes released; that wallet's reserved amount
  falls by exactly `$0.374595`. Its balance and all financial ledger entries
  remain unchanged. No Usage, ProviderReceipt, CostReconciliation or PlatformCost
  row is added or modified.
- Existing release and job-resolution audit rows record the act. An append-only
  `reconciliations/003-provider-refusal.json` records the recovered outcome next
  to the retained campaign evidence; original terminal campaign records and
  counters are not rewritten. This request is not repeated.
- The synthetic resolution administrator is deactivated and the temporary
  process stopped, with a retirement audit. Its necessary original protected
  credential/evidence record is retained.

Refuse before mutation if evidence identity, QA server/container/port, job state,
receipt/usage absence, backup, port availability or declaration binding differs.
If authentication or resolution fails after account creation, stop the process,
deactivate the account, retain the failed evidence and diagnose before any next
act. A subsequent attempt needs a fresh declared identity after inspecting the
actual state; no blind rerun.

Judge the final comparison against every expected row and unchanged ledger
claim. No recovered outcome is reported as provider-billed reconciliation.
