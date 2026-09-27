# Restore integrity: independent refutation — 2026-09-27

**NOTHING FOUND within the bounded offline catalog-contract scope.**

Reviewed exact commit `a300f7f89f7d6a7bcfde792290215378cd38d255`:

| Source | SHA-256 |
| --- | --- |
| `rebuild/ops/integrity_contract.py` | `41223ecc3821f1a9e99265c32674038dd95d5cee040b9c524060664ba4a09585` |
| `rebuild/ops/production_restore_check.py` | `2233d7e3ed7a0451eb628f43402bc468bc9e7daa151c36584ef6104370f11dc6` |

The exact parent checker and all 23 migration-source files were preserved beside
these snapshots. No source edits were made.

## Evidence

Independent extraction from migration literal SQL agrees with the contract's
**17 table/trigger/event/function definitions and 10 exact function-body hashes**.
The extraction did not import migrations or query a database.

**38 pure catalog configurations** met their predeclared outcomes:

- Four positives: migration-bound baseline, reversed row order, always-enabled
  triggers, and schema-qualified spelling of the same functions.
- Thirty-four negatives: equal-count table/trigger/function replacement;
  same-body function relocation; event/timing changes; added `WHEN` and column
  restrictions; disabled/replica-only state; changed/no-op bodies; argument,
  language, return, security-definer, configuration, strictness, volatility and
  parallel changes; additional core/quillmd guards; missing-plus-extra, duplicate
  and malformed rows; wrong schema/session role; empty/extra context; boolean,
  string and legacy declared counts.

All evaluator outputs contain fixed count/boolean fields and no migration
table/function names or bodies. Socket/process operations were disabled and no
forbidden operation was attempted.

The watched catalog at `integrity_contract.py:17` is public, noninternal triggers
on core-prefixed tables **or** using quillmd-prefixed functions. A renamed
function does not hide a trigger on a core table. This is not a watch of all
functions, all schemas, or internal PostgreSQL constraints.

The `sql_function` spelling used at `:44` is not its only identity proof:
`:46` also fixes the function name, schema and zero-argument identity, and `:51`
binds its body hash. A fabricated row whose joined identity columns disagree
with its printed identity was not promoted into a live PostgreSQL finding.

AST comparison with parent `0b0395a0922f81f5a38526802136197a4bb74b28` confirms
that `require`, `drill_target`, `_file_sha256`, `connect`, `main`, and the check's
entire nontrigger logic are unchanged. This preserves the existing live-target,
TLS/read-only connection, filesystem and invariant checks at source level.

## Limits and handoff

No database connection, fresh-PostgreSQL test, actual restore, role-default
validation, provider operation, Word operation, corpus read, or full suite was
performed. The author's fresh-migration PostgreSQL result was read as reported
evidence; this review does not claim to have repeated it. `public/origin` checks
the current connection context, not every role/default or privileged-owner
threat. The legacy count-only backup instrument remains unchanged.

Private runtime:
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/ops-integrity-a300f7f8-20260927/`.
It retains source identities, migration snapshots, all 38 inputs, raw results
and the probe. The append-only delta seal is
`metadata/059-OPS-INTEGRITY-REFUTATION-DELTA-SEAL.json` under the custody root.
