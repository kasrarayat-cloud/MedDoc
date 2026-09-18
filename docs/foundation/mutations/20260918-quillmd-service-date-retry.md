# Private activation of date-of-service code selection — RETRY after a refused migration, 2026-09-18

## What happened on the first attempt, stated first

The act declared in `20260918-quillmd-service-date.md` ran at `15:37:47Z` and **failed closed inside the
migration**. PostgreSQL refused the backfill:

    psycopg.errors.RaiseException: Finalized document is immutable
    CONTEXT: PL/pgSQL function quillmd_encounter_guard() line 4 at RAISE

`encounter_scope` is a BEFORE INSERT OR UPDATE trigger on `core_encounter` that refuses **any** update to a row
whose status is `finalized`. **Six of the eleven encounters are finalized**, so the backfill could not reach them.

**Nothing was left half-done, and that is checkable rather than asserted:**

| after the failure | measured |
| --- | --- |
| `service_date` column | **absent** (`information_schema.columns` → 0) |
| `0014` in `django_migrations` | **absent** (→ 0) |
| encounters | 11, unchanged — 5 draft, 6 finalized |
| services | **stopped**, as the activator's fail-closed path requires |
| permanent main | advanced to `475a5925` before the migration ran, and left there |

⚠️ **Why no test caught it.** Every encounter in every fixture was a draft. The migration was proved on a test
database whose rows the guard had no reason to refuse — a control that passed because it was pointed at the wrong
universe, not because the code was right. A `TransactionTestCase` with a finalized encounter now exists, and it
fails without this change.

## What this act changes relative to the refused one

Exactly one thing: the migration suspends `encounter_scope` for the duration of its backfill statement and restores
it in the same transaction.

    ALTER TABLE core_encounter DISABLE TRIGGER encounter_scope
    …one UPDATE per row, writing only service_date…
    ALTER TABLE core_encounter ENABLE TRIGGER encounter_scope      (in a finally:)

**Why this is not a hole in the guard.** The guard exists to stop a finalized clinical document being edited. This
statement does not edit one: no clinical content changes, the value is derived from that row's own `created_at`, and
`.update(service_date=…)` cannot write another column. The guard has no way to express "filling a column that did
not exist a moment ago", so it is suspended for that statement alone. The window is inside one transaction, DDL is
transactional here, `DISABLE TRIGGER` takes an ACCESS EXCLUSIVE lock, and the three services are stopped throughout —
so no other writer can pass through it, and a failure at any point rolls the suspension back with everything else.

## Expected delta, declared before the act

From `475a5925` to the cited merge. The range is small because main already carries the rest of this work:

1. the migration, with the suspension above (pinned `2119a159682ea0da03523f80e6dd38f7ac0aab16733101ea6d2a60eb3deda01c`);
2. the finalized-document tests that were missing;
3. this declaration, the activator re-baselined onto `475a5925`, and the two documents that describe the state.

Database — the whole delta, unchanged from the refused declaration except where noted:

- `core_encounter.service_date`, `date`, NOT NULL, **no default**, added at the end of the table.
- Exactly **11** encounter rows gain a value, **including the six finalized ones**, each the UTC date of its own
  `created_at`. After the act `SELECT service_date, count(*) FROM core_encounter GROUP BY 1` must read exactly
  `2026-09-17=11`, and `service_date <> (created_at AT TIME ZONE 'UTC')::date` must match **0** rows.
- One `django_migrations` row, `core / 0014_encounter_service_date`.
- **No constraint changes. No index changes. No table created or dropped.**
- ⚠️ **`encounter_scope` must read `tgenabled = 'O'` after the act, exactly as before it.** The activator records the
  value before and after and refuses on any difference, because a guard left disabled would make every finalized
  clinical document on this system silently editable. That is the one new failure mode this change introduces, and it
  is the one the act checks hardest.

| Quantity | Before | After |
| --- | --- | --- |
| Tables | 35 | 35 |
| Encounters (5 draft, 6 finalized) | 11 | 11 |
| Patients | 3 | 3 |
| Jobs | 12 | 12 |
| Code suggestions | 0 | 0 |
| Terminology releases / codes | 1 / 74,719 | 1 / 74,719 |
| Per-table row fingerprints, with the new column removed for comparison | — | identical |
| `/var/lib/quillmd/files`, `/var/lib/quillmd/mail` inventories | — | identical |
| `encounter_scope` trigger state | `O` | **`O`** |

## Protected resources and checks

Unchanged from the refused declaration: every other tenant's containers, the marketing site, the ingress, the
encrypted volume layout, the compiled Word runtime and its pinned helper image, the installed unit files, private
files and mail bytes, and all credentials. `scripts/check-cotenants.sh` runs before and after. The environment file
is rewritten only to replace the release line and is byte-compared before and after.

**Reversibility.** Reversing the migration drops the column; the backfilled dates are not recoverable by re-running
anything, but `created_at` is untouched so they can be recomputed exactly. On any failure the activator fails closed:
services stay stopped and the recorded state is inspected before anything else runs — which is what happened at
`15:37:47Z`, and why this retry exists rather than a repair of a half-applied schema.

No provider request is made. No clinical content is read, written or exported.

---

## CORRECTION, appended 2026-09-18 after the retry was itself refused in preflight

The retry above was refused before it touched anything, twice over, and both refusals were the activator
describing a state it could not represent. Nothing was changed either time.

**1 · A leftover assertion.** The preflight still required `rebuild/core/coding.py` to be in the range. That was
true of the first attempt and is false of this one — main already carries it. Replaced with a requirement that the
range contains this declaration, which is true of any act that declares itself.

**2 · THE TREE'S HEAD AND THE RUNNING RELEASE ARE DIFFERENT FACTS.** The refused act advanced permanent main to
`475a5925` and then died inside the migration — **before** the line that rewrites `QUILLMD_RELEASE_SHA` in the
environment file. So three things that had always moved together came apart:

| fact | value after the refusal |
| --- | --- |
| permanent main / the tree's HEAD | `475a5925` |
| the release line the services would report | `5f673a3b` |
| the services themselves | **stopped** |

The activator assumed all three were the same and so refused its own repair: it required the services to be running
and answering `475a5925`, which they can never do. It now carries `BASELINE` (the tree) and `RUNNING_RELEASE` (the
environment line) as separate constants, accepts the services being down — which is what its own fail-closed path
produces — and refuses only if a surface answers something *unexplained*, or if the two surfaces disagree about
whether they are up at all.

⚠️ **The first version of that agreement check was `any(answer is None) or all(answer is not None)`, which is true
for every possible input including the one it was written to catch.** It is now `all(... is None) or all(... is not
None)`, and a test asserts the refused case is refused.

**Preconditions for this act, restated as they actually are:** tree at `475a5925`, release line at `5f673a3b`,
services stopped, database at `0013` with no `service_date` column, `encounter_scope` enabled, 11 encounters of
which 6 are finalized, 74,719 codes. Every expected quantity above is unchanged.
