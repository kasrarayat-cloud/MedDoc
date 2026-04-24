# Test fixtures

Reference for the named DB rows the automated suite expects in the
target environment. These are NOT created by the tests themselves —
the Playwright specs read them as pre-conditions and skip / fail
loudly if they're missing. Recreate after a DB rebuild or when
adding a new product-matrix scenario.

The QA practice is `qa-practice-audit` (already exists in prod).
Inserts below cascade-safe — they `ON CONFLICT (email) DO UPDATE`
the products array, password hash, and reset the lockout / failed
counters, so re-running the recipe fixes a drifted fixture row
without dropping it.

## Why these specific rows

The product-separation matrix needs one user per `products[]`
combination so each cell is exercised by a stable account whose
state isn't accidentally flipped by another test. Using the same
shared fixtures for ad-hoc probes keeps the audit-evidence
artefacts coherent across runs.

## Users

| `id`                      | `email`                          | `products`                      | role     | practice            |
|---------------------------|----------------------------------|---------------------------------|----------|---------------------|
| `qa-audit-user-unified`   | `qa-audit@quillmd.local`         | `{MEDDOC_PRO,TRANSCRIBE_MD}`    | `DOCTOR` | `qa-practice-audit` |
| `qa-tmd-only`             | `qa-tmd@quillmd.local`           | `{TRANSCRIBE_MD}`               | `DOCTOR` | `qa-practice-audit` |
| `qa-pro-only`             | `qa-pro@quillmd.local`           | `{MEDDOC_PRO}`                  | `DOCTOR` | `qa-practice-audit` |
| `qa-bundle`               | `qa-bundle@quillmd.local`        | `{MEDDOC_PRO,TRANSCRIBE_MD}`    | `DOCTOR` | `qa-practice-audit` |
| `qa-no-product`           | `qa-noprod@quillmd.local`        | `{}`                            | `DOCTOR` | `qa-practice-audit` |

All five share the password `QaTestPassword2024!` (same bcrypt hash
as `qa-audit-user-unified`). The password is also in
`tests/automated/.env.test` as `TEST_APP_PASSWORD`; specs that
already read that var don't need to hardcode it. The matrix spec
hardcodes it as a constant because it tests four credentials in
one file and threading four env vars added more friction than the
shared constant.

## Recipe — recreate / repair

Run inside the postgres container against the prod DB. Idempotent.

```sql
-- Reuses the qa-audit hash so all five users share the same password.
INSERT INTO users (
  id, email, "passwordHash", products, role, "practiceId",
  "isActive", "mfaEnabled", "failedLoginCount", "emailVerified", "updatedAt"
)
VALUES
  ('qa-tmd-only',    'qa-tmd@quillmd.local',    '$2b$10$NrAZJUiWDV.APetyCZ35tefKoh/lIyFfcC1TxVPmDjr9NaaGD1yje', ARRAY['TRANSCRIBE_MD']::"Product"[],            'DOCTOR', 'qa-practice-audit', true, false, 0, NOW(), NOW()),
  ('qa-pro-only',    'qa-pro@quillmd.local',    '$2b$10$NrAZJUiWDV.APetyCZ35tefKoh/lIyFfcC1TxVPmDjr9NaaGD1yje', ARRAY['MEDDOC_PRO']::"Product"[],               'DOCTOR', 'qa-practice-audit', true, false, 0, NOW(), NOW()),
  ('qa-bundle',      'qa-bundle@quillmd.local', '$2b$10$NrAZJUiWDV.APetyCZ35tefKoh/lIyFfcC1TxVPmDjr9NaaGD1yje', ARRAY['MEDDOC_PRO','TRANSCRIBE_MD']::"Product"[], 'DOCTOR', 'qa-practice-audit', true, false, 0, NOW(), NOW()),
  ('qa-no-product',  'qa-noprod@quillmd.local', '$2b$10$NrAZJUiWDV.APetyCZ35tefKoh/lIyFfcC1TxVPmDjr9NaaGD1yje', ARRAY[]::"Product"[],                            'DOCTOR', 'qa-practice-audit', true, false, 0, NOW(), NOW())
ON CONFLICT (email) DO UPDATE SET
  products         = EXCLUDED.products,
  "passwordHash"   = EXCLUDED."passwordHash",
  "isActive"       = true,
  "failedLoginCount" = 0,
  "lockedUntil"    = NULL,
  "emailVerified"  = NOW();
```

Wrap in `docker compose exec postgres psql -U meddoc -d meddoc -c "…"`
and the heredoc-quoted form already in the audit harness if running
from a script.

## Visits referenced by specs

The Rx-override (F5-1) regression also leans on a SIGNED visit
on the QA user with an injected `critical` warning + matching
override row. This row pair is left in place after the F5-1
verification so the data is self-evident in any subsequent audit:

- `transcribe_visits.id = cmocm9jki000601kwxf575d00`
  - `userId = qa-audit-user-unified`
  - `status = SIGNED`
  - `rxDrafts.warnings` includes a `TEST_DRUG` `critical` entry —
    intentionally synthetic so the audit reader can tell at a glance
    that this visit is QA fixture data, not real PHI.
- `rx_warning_overrides.id = test_override_f51verify` — the row that
  satisfies the gate for the synthetic warning above.

If the `cmocm9jki…` row is ever hard-deleted, the matching override
row gets cascaded by the FK and the F5-1 retest needs a fresh
critical-warning visit. To avoid running the full Rx-drafting
pipeline (Anthropic spend), the cheapest reset is:

```sql
UPDATE transcribe_visits
   SET status = 'READY', "signedAt" = NULL, "signedSoap" = NULL
 WHERE id = 'cmocm9jki000601kwxf575d00';
DELETE FROM rx_warning_overrides WHERE id = 'test_override_f51verify';
```

…then run the F5-1 retest script and re-sign.

## Cleanup (don't, normally)

These rows are intentionally permanent. The product-separation spec
runs against prod and depends on them being present; deleting them
silently breaks 8 of the 12 cells. If a fresh QA practice is created
for a future audit cycle, point the new spec at it — don't strip the
existing rows.
