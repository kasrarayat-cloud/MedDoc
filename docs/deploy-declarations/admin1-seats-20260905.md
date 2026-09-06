# §2.5 PASSENGER DECLARATION — ADMIN-1, seat-minting and the members page

**Written BEFORE the act**, at PR-open time on `2026-09-05`, while
`feat/admin1-seats` was still an open PR and **before the merge commit
existed**. Nothing below could be tuned to an outcome, because no outcome
exists yet.

Branch `feat/admin1-seats` · RELAY **ADMIN-1** · rulings **2026-08-06 (signing is
the sole role-gated action)**, re-ratified 2026-09-05.

> ⚠️ **PASSENGER DECLARATION — this session does not deploy.** The change rides
> the next declared deploy as a **named passenger**, and the deploying
> session's own §2.5 governs the comparison. On that deploy this file goes
> verbatim to `docs/foundation/deploys/<YYYYMMDD>-<short-sha>.md` with only a
> header line naming the SHA the original could not know.
>
> ⚠️ **THIS ONE CARRIES A MIGRATION, so it is NOT a "nothing but the image ids"
> deploy.** A deploy that ships it without naming it has shipped an unjudged
> irreversible act.

---

## WHAT SHIPS

The two gaps the ADMIN-1 row names, and **nothing else**.

1. **Seat-minting.** A practice OWNER creates an invite carrying **both**
   `practiceId` and `practiceRole`. Today the only `inviteCode.create` in the
   tree sets neither, so a multi-seat invite is raw SQL.
2. **The members page** — `/settings/members`, and a `Members` section in both
   settings branches. `practiceRole` currently appears in **0** `.tsx` files.

**Deliberately NOT shipped, because it is RULED AGAINST:** role enforcement
across the other 48 mutating surfaces. *Signing is the sole role-gated action*;
techs prepare, including deleting unsigned drafts, and deliver.

---

## ⚠️ THE IRREVERSIBLE PART — THREE ENUM LABELS

`20260905000000_admin1_practice_seat_audit_actions`:

    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_SEAT_INVITED';
    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ROLE_CHANGED';
    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ADMIN_REFUSED';

**Postgres has no `ALTER TYPE … DROP VALUE`. All three are permanent.**
`IF NOT EXISTS` makes the migration idempotent so a partial application cannot
wedge a deploy half-way through a three-statement change.

### MUST CHANGE

| | before | after |
|---|---|---|
| `AuditAction` label count | **153** | **156** |
| applied migrations | *(baseline)* | **baseline + 1** |
| image ids (`transcribe-md`, `-worker`) | *(baseline)* | **changed** |

### MUST **NOT** CHANGE

| | |
|---|---|
| `transcribe_visits` total | **identical** |
| visits with `signedAt IS NOT NULL` | **identical** |
| patients | **identical** |
| `users` total | **identical** |
| **`users` grouped by `practiceRole`** | **identical** |
| `invite_codes` total | **identical** |
| `ledger_entries` | **identical** |
| any other table's row count | **identical** |

⚠️ **THE `practiceRole` DISTRIBUTION IS THE ROW THAT MATTERS, and it is stated
as MUST-NOT-CHANGE deliberately.** This deploy ships the machinery to change
roles; it must not itself change one. A movement there means the migration or
the deploy wrote a role, which nothing in this change does — **a difference
that is not in this declaration is THE FINDING**, whatever explanation is
available afterwards.

⚠️ **THE `ledger_entries` ROW CARRIES NO NUMBER ON PURPOSE.** The RELAY row
records 177 rows summing $1,770 across 177 practices, but **that is another
session's measurement and this one cannot confirm it** — no production access.
Restating it here as a baseline would dress a citation up as a reading. The
invariant is what this change is entitled to assert: *this deploy writes no
ledger row*, and the deploying session's own baseline supplies the number.

⚠️ **AND `invite_codes` MUST NOT MOVE EITHER.** The new writer is reachable only
from a signed-in OWNER pressing a button. A row appearing during the deploy
would mean something minted a seat with no human, which is the one outcome
this surface must never have.

---

## WHAT ELSE THE DEPLOY TOUCHES

- **`AuditAction` TS mirror** widened by the same three labels, pinned by the
  existing `gate-audit-enum-mirror` in both directions.
- **The settings page's user read** widens by `practiceId` + `practiceRole`.
  ⚠️ **READ FROM THE DATABASE, NEVER FROM THE SESSION** — a JWT is minted at
  sign-in, so a member demoted five minutes ago still carries the old role in
  their token, and this surface hands out SEATS.
- **The legacy settings eyebrows renumber `02…07` → `03…08`.** Cosmetic, and
  the numbering reconciles 01–08 with no gap or duplicate. Nothing pins them.
- **`RELAY.md`'s ADMIN-1 Done-when** loses a clause that contradicted its own
  row's body. The superseded wording is **quoted verbatim in its replacement**,
  so the ledger loses nothing — `--numstat` is 1 added / 1 removed on one line.

---

## ⚠️ WHAT IS FAIL-CLOSED, AND WHY IT IS NOT A GAP

**Whether one OWNER may create another — whether OWNER is exclusive — is
UNRULED.** The ADMIN-1 row flags it, and this build refuses rather than guesses:
`ASSIGNABLE_ROLES` is `['CLINICIAN','TECH']`, an OWNER's role cannot be changed
from this page, and the surface says so in words rather than hiding the control.

That refusal is also what makes **"every practice has at least one OWNER" hold
structurally** — a solo signup mints OWNER, invites can mint only the other two
— rather than by a last-owner count that would have to be correct under
concurrency.

**A refusal is recoverable by a ruling. An accidental second owner is somebody
else's clinic.**

---

## ⚠️ NO PRODUCTION BASELINE NUMBERS, AND WHY

This session has no production database access — the read was attempted and
**denied**, which is the correct posture for a session that never deploys. Every
row above is therefore stated as an **invariant to compare against**, not as a
measured value. The deploying session captures the baseline.

**An unmeasured row named honestly is worth more than a number I could not
read.**

---

## VERIFICATION AVAILABLE WITHOUT TOUCHING A RECORD

Structural only — no real doctor's visit is a smoke target:

- `SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
   WHERE t.typname='AuditAction';` → **156**
- the three labels present:
  `SELECT enumlabel FROM pg_enum … WHERE enumlabel LIKE 'PRACTICE\_%';` → 3 rows
- `_prisma_migrations` carries `20260905000000_admin1_practice_seat_audit_actions`
- the new surface is in the shipped bundle: `grep -c 'members-panel' <chunk>` ≥ 1
- `GET /settings/members` returns 200 for a signed-in account (DOM presence
  only, mutating nothing)
- **the full walk — mint, redeem, change a role — belongs on QA**, on the
  synthetic stack, against a byte-identical build.
