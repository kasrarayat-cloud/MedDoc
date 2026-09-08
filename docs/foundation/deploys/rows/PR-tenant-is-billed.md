# §2.5 AUTHOR ROWS — ruling #294, THE TENANT IS BILLED

**Written at PR-OPEN time, before the act**, per ruling #184 and the ADMIN-1
board filing: a passenger without author rows is a FINDING, not a pass.

**Lane:** Design/Admin. **Migrations: NONE — code-only.**
**Runtime files: 1** — `apps/transcribe-md/src/worker.ts`.

## WHAT THE CHANGE IS

`worker.ts` bound `const practiceId = visit.user.practiceId` — the AUTHOR's
practice — and fed **twenty-five sites** from that one line: admission, every AI
layer's usage metering, the audit rows, the Sentry tags, the failure notifier,
and the charge. It now derives from `visit.practiceId`, the visit's own tenant
column.

## ⚠️ THE MEASUREMENT THAT MAKES THIS SAFE, TAKEN BEFORE THE ACT

Read-only against production (`meddoc-pro-postgres-1`, `SELECT` only), 2026-09-08:

```
SELECT count(*) AS total,
       count(*) FILTER (WHERE v."practiceId" = u."practiceId")             AS agree,
       count(*) FILTER (WHERE v."practiceId" IS DISTINCT FROM u."practiceId") AS diverge
  FROM transcribe_visits v JOIN users u ON u.id = v."userId";

 total | agree | diverge
    58 |    58 |       0
```

**58 of 58 visits already have author practice == tenant, and zero diverge.** So
this change moves **NOTHING** in production today. That is the whole reason it is
safe to make now rather than after the first locum: the correction lands while
the two values still agree, so there is no back-fill and no reconciliation.

⚠️ **AND THAT AGREEMENT IS EXACTLY WHY THE DEFECT SURVIVED.** Every existing
fixture, every production row and every test had the tenant, the author and the
author's practice as the same value — ruling #260's *"a fixture that gives two
distinct things the same value cannot witness them being confused"*, holding at
the scale of the entire database.

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **294-N1** | `transcribe_visits` count | **58**, unchanged | code-only; any movement means something rode that nobody declared |
| **294-N2** | visits where `v."practiceId" <> u."practiceId"` | **0**, unchanged | if this becomes non-zero the population changed under the declaration, and every claim below about "moves nothing" is void |
| **294-N3** | clinical counts — visits, patients, signatures | unchanged | never omitted, per §2.5 |
| **294-N4** | practice balances / ledger entries | unchanged by the deploy itself | admission and charging are `BILLING_ENFORCED`-gated and the flag is OFF; a balance that moves on a code-only deploy is a finding |

## MUST CHANGE — nothing observable

There is no MUST-CHANGE row, and that is the declaration, not an omission. With
58/58 agreeing, the corrected derivation returns the **same value** for every
visit in production. The change is observable only on a locum visit, and there
are none. **A difference is THE FINDING**, whatever explanation is available
afterwards.

## HOW IT IS PROVEN INSTEAD

`tests/worker/gate-294-tenant-is-billed.test.ts` — the harness `worker.ts` has
wanted since the stuck-chart incident its own comment records (*"no unit test
runs `processVisit`"*). Three arms on a **three-identity fixture** (tenant A,
locum author, the locum's practice B):

1. admission is asked about **A**;
2. the charge lands on **A** — with a positive control, because charging is on
   the success path only and an arm that never reached it proves nothing;
3. the author's practice reaches **no seam at all**, with a non-vacuity check
   that the fixture really does carry that value.

Mutation: restoring `visit.user.practiceId` reds all three.
