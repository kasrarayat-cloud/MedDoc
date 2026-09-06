# BOARD FILING — OWNER IS NOT EXCLUSIVE (Design/Admin)

**Filed 2026-09-06 by the Design/Admin session, on owner ruling #195.**
Ruling body: `docs/foundation/rulings/2026-09-06-195.md`. Index row:
`RULINGS.md`. **This file is a pointer and a status, never the rule.**

## WHAT WAS DECIDED

**A practice may have more than one OWNER, and an owner may create another** —
by minting an OWNER seat or promoting a member. ADMIN-1 shipped fail-closed on
this question and flagged it as class (a) rather than guessing; the owner has
now answered it.

**Demotion and removal of an owner stay refused**, and the members page says so
in words rather than omitting the control silently.

## WHAT SHIPPED WITH IT

| | |
|---|---|
| `ASSIGNABLE_ROLES` | `['CLINICIAN','TECH']` → `['OWNER','CLINICIAN','TECH']` |
| refusal message | no longer claims the question is "not settled" — promotion IS settled |
| both role selects | now DERIVED from `ASSIGNABLE_ROLES`, previously hardcoded |
| role vocabulary | moved to `lib/practice-roles.ts` — client-safe, no runtime imports |
| gates | `gate-admin1-practice-admin` 28 arms, `gate-admin1-members-panel` 10 — 38 passing |

## ⚠️ WHAT THE NEXT SESSION WILL GET WRONG, AND THE MEASUREMENT THAT SETTLES IT

**"OWNER is not exclusive, therefore the last-owner guard is now required."**
That is the obvious reading, **this session asserted it out loud before checking
it, and an adversarial verifier refuted it against the code.**

The promotion guard (`RoleSchema` → `z.enum(ASSIGNABLE_ROLES)`) and the demotion
guard (`CANNOT_CHANGE_AN_OWNER`, `actions/practice-members.ts:180`) are separate
branches at different lines. The second refuses changing an owner *whatever role
is asked for*, so widening the first never reaches it. **"Every practice has at
least one OWNER" still holds structurally, and #195 therefore costs no
concurrency work at all.**

⚠️ **What DID change is the incidental enforcement.** Before, `RoleSchema`
rejected an OWNER→OWNER request before the guard was consulted, because no
reachable target role was OWNER. Now it is legal, and the explicit branch is the
only thing left. There is an arm for exactly that input; **do not delete it as
redundant** — it stopped being redundant the moment the list widened.

## WHAT IS FILED — `ADMIN-5`, AND IT IS NEEDED, NOT PARKED

Owner demotion and removal is now a row in `RELAY.md` immediately after ADMIN-4.
**Partners leave practices**; today the route is support running SQL.

⚠️ **ITS GUARD IS RULED IN SHAPE, SO NOBODY REBUILDS IT WRONG: a partial unique
index or a SERIALIZABLE transaction. NEVER a count read and then acted on.**

The failing interleaving, written down where the builder will meet it: two
owners demote each other at the same instant, the count returns **2** to both,
both conclude there is another owner, both write, and the practice is left with
**zero** owners and nobody able to administer it. That is not a window to
narrow — a read-then-act check cannot see it by construction.

## §2.5 ROWS — AUTHORED AT PR-OPEN, PER THE ADMIN-1 BOARD FILING

This lane's rows for this PR are at `docs/foundation/deploys/rows/PR-<n>.md`,
written before the act, as `ADMIN1-ROWS-AT-PR-OPEN.md` asks.

⚠️ **AND THAT FILING'S CENTRAL CLAIM ABOUT THIS LANE IS FALSE — CORRECTED HERE
RATHER THAN ARGUED.** It states ADMIN-1's migration rode `ff993c3a` *"with no
§2.5 rows from its author"*. The author **did** write them: 
`docs/deploy-declarations/admin1-seats-20260905.md`, commit `476cfdbc`, **in the
same commit as the migration**, carrying the same `153 → 156` enum rows the
deployer later re-derived as A1-1/A1-2/A1-3.

**The mechanism is a path, not a lapse.** §2.5 declarations live in **three**
directories — `docs/deploy-reports/`, `docs/foundation/deploys/` and
`docs/deploy-declarations/` — and `DEPLOYMENT_RUNBOOK.md` §2.5's cross-reference
step names **two**, under the emphatic heading *"AND THE DECLARATIONS LIVE IN TWO
DIRECTORIES. SEARCH BOTH, BY NAME."* The deployer searched exactly where the
runbook said to and correctly found one rows file.

**So the ask is right and the diagnosis was wrong.** Both are worth fixing, and
the second is the one that will recur: a rule that names a set which is not the
set is the WATCHED-SET failure — the right question asked of the wrong universe.
The CI gate that filing promises should count all three paths, or the third
should be retired into one of the two. **Filed to the deploy owner as a
correction, not as a counter-accusation** — nobody bypassed anything.
