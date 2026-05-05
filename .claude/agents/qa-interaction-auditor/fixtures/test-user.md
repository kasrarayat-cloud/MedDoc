# Test user — `qa-auditor@quillmd.test`

The QA Interaction Auditor agent walks the doctor workflow as a real
authenticated user. To stay non-PHI, the agent uses a dedicated test
account that lives only in the `clinic_main` practice.

## Why a dedicated account

- A real doctor's account contains PHI (real patient names, real audio,
  real notes). The agent must never read or write that.
- Sharing the e2e admin account (`admin@test.dev`) is wrong — that user
  is `SUPER_ADMIN`, lands on `/system-admin`, and bypasses tenant
  scoping. The QA agent needs to walk the *doctor* workflow.
- A purpose-named account makes it obvious in `audit_logs` who did
  what. Filtering for `userId = qa-auditor@quillmd.test`'s id strips
  out test traffic from compliance reports.

## Account spec

| Field | Value |
|---|---|
| email | `qa-auditor@quillmd.test` |
| password | (set via env `QA_AUDITOR_PASSWORD`; not committed) |
| name | `QA Interaction Auditor` |
| role | `DOCTOR` |
| practiceId | `clinic_main` |
| isActive | `true` |
| specialty | `family-medicine` |
| timeZone | `America/Los_Angeles` |

The `.test` TLD is reserved (RFC 2606) so the email never resolves to
a real mailbox — agents that try to "verify" the address by sending
mail will bounce harmlessly.

## Seeding

Run once on a fresh environment. Idempotent — safe to re-run; resets
the password + active state to known-good.

```bash
cd /opt/meddoc-pro

# Set the password in your shell (do NOT commit). The agent reads this
# from env at run time. Use a strong value — this account has DOCTOR
# permissions on a real practice in dev.
export QA_AUDITOR_PASSWORD='<paste a strong password here>'

# Seed.
docker compose -f docker-compose.yml --profile db-seed run --rm \
  -e QA_AUDITOR_PASSWORD \
  transcribe-md npx tsx scripts/seed-qa-auditor.ts
```

If the `seed-qa-auditor.ts` script doesn't exist yet, hand-seed via
`psql` (template below). Then add the script to
`apps/transcribe-md/scripts/` matching the shape of
`apps/meddoc-pro/scripts/seed-e2e-admin.ts`.

### Hand-seed template

```bash
HASH=$(node -e "const b=require('bcryptjs');b.hash(process.env.QA_AUDITOR_PASSWORD,12).then(h=>console.log(h))")
docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc <<SQL
INSERT INTO "User" (id, email, name, "passwordHash", role, "isActive", "practiceId", specialty, "timeZone")
VALUES (
  'qa_auditor_user',
  'qa-auditor@quillmd.test',
  'QA Interaction Auditor',
  '$HASH',
  'DOCTOR',
  true,
  'clinic_main',
  'family-medicine',
  'America/Los_Angeles'
)
ON CONFLICT (email) DO UPDATE SET
  "passwordHash" = EXCLUDED."passwordHash",
  "isActive" = true,
  "lockedUntil" = NULL,
  "failedLoginCount" = 0,
  role = 'DOCTOR',
  "practiceId" = 'clinic_main';
SQL
```

## Verifying the account is healthy

The agent runs this before every walk and aborts if the user isn't in
the expected state:

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA <<SQL
SELECT row_to_json(t) FROM (
  SELECT
    email, role, "isActive", "practiceId", "lockedUntil",
    "failedLoginCount"
  FROM "User"
  WHERE email = 'qa-auditor@quillmd.test'
) t;
SQL
```

Expected: `{"email":"qa-auditor@quillmd.test","role":"DOCTOR","isActive":true,"practiceId":"clinic_main","lockedUntil":null,"failedLoginCount":0}`.

If `lockedUntil` is set, the agent re-seeds (idempotent) before
proceeding. If `isActive` is false, abort + surface to Kasra.

## Per-run cleanup

After every walk, the agent drops every visit it created:

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA <<SQL
DELETE FROM transcribe_visits WHERE "userId" IN (
  SELECT id FROM "User" WHERE email = 'qa-auditor@quillmd.test'
);
SQL
```

This keeps the dev DB lean and prevents cross-run contamination
(yesterday's signed visit from a previous walk shouldn't influence
today's "filter: signed" assertion).

The agent does NOT delete `audit_logs` rows — those are append-only by
HIPAA design (Phase 17). The audit trail of QA-account activity is
useful for self-validation: if last week's run wrote five
`VISIT_SIGNED` rows and this week's run writes zero, that's a
regression signal.

## Boundary rules

The agent treats this account as **the only writable user**. Any
mutation observed against a different `userId` is an automatic abort +
P0 finding ("agent walked into the wrong account"). Defense in depth
against scope-leakage bugs.

## Credential rotation

If `QA_AUDITOR_PASSWORD` leaks (committed by accident, posted in chat,
etc.):

1. Rotate immediately: re-seed with a new value.
2. The seed script's `ON CONFLICT` clause overwrites the hash, so the
   old credentials stop working as soon as the seed runs.
3. Audit `audit_logs` for unexpected activity:

   ```sql
   SELECT "createdAt", action, ip, "userAgent", metadata
   FROM audit_logs
   WHERE "userId" = (SELECT id FROM "User" WHERE email = 'qa-auditor@quillmd.test')
     AND "createdAt" > '<rotation-timestamp>'
   ORDER BY "createdAt" DESC LIMIT 100;
   ```

4. If anything looks off, surface to Kasra. The agent does not triage
   suspected breaches alone.
