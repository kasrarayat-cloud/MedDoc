# HANDOFF — #1018, #1022 AND #1026 BELONG TO DESIGN/ADMIN, AND THIS SESSION IS OFF THEM

**Filed 2026-09-06 by the custom-file session, on owner lane discipline.** These
three are Design/Admin's, held by the peer session working in `.wt-omit`. This
session does not touch those branches again. Everything below is evidence handed
over, with **no authorization attached** — a peer cannot carry authority, only
reasoning.

## THE THREE RULINGS THAT LANDED WITH THIS HANDOFF

Recorded in `RULINGS.md` and `docs/foundation/rulings/2026-09-06-201-203.md`.
Two of the three are implemented in the receiving lane, not this one.

| # | what it decides | whose work |
|---|---|---|
| **#201** | `compilerVersion` bumps; the active compiled versions get a ruled recompile so REVIEW-DEFAULTS can fire at all. **`isScaffolded` is outside both hashes — the recompile is armed to prove no certification hash moves.** | Design/Admin |
| **#202** | a per-field policy toggle **must not de-certify a template** — it triggers automatic re-certification; `NEEDS_CONFIRMATION` only when a new HUMAN confirmation is required. **Nulling the synthetic-test columns on a toggle is the defect.** | Design/Admin |
| **#203** | `KEY_VERSION` v6 → v7 lands in the SAME COMMIT as the #1018 fix | Design/Admin |

## WHAT #1018 ALREADY HAS, AND WHAT IT STILL NEEDS

**The fix in `.wt-omit` is right, and it was reached twice independently.** A
four-way attack on the two obvious alternatives rejected both (3 × `third_option`,
1 × `hybrid`) and converged on exactly what `60de5ff0` / `a642b88c` / `432bd450`
implement: panel keyed on `current?.reasonCode === 'omitted_unsupported_default'`,
door's omit refusal deleted, dead column dropped, `as never` casts gone.

⚠️ **THE ALTERNATIVE — "widen the select" — WOULD HAVE SHIPPED THE SAME DEFECT ONE
COLUMN OVER, INVISIBLY.** The predicate reads `mapping.status` (domain,
lowercase); the column is `mappingStatus` with UPPERCASE enum values. Applied
naively it makes `canOmit` TRUE on an unsupported field — and it passes
`tsc --noEmit` exit 0 and **855/855 tests**, including all 89 arms of the gate
written to make that mirror safe. Five hand-rolled `mappingStatus.toLowerCase()`
copies already exist in the tree; widening would have added a sixth and seventh.

**STILL OPEN, and it is ruling #203:** `KEY_VERSION` is `v6`. `insertableDefaults`
lives inside `CachedFill`, so this fix changes which fields the list CONTAINS
without changing its SHAPE, and a warm entry serves the pre-fix offer list for the
TTL. `fill-cache.ts:111` records the same trap from `v5 → v6` — *"the shape
changed and the key did not"*.

**ALSO CARRIED, from the pass:** 11 survived findings of 15 distinct (27 raw),
4 killed. The §2.5 rows corrections are already committed on the branch as
`13a94201`.

## #1022 — HELD, AND #199 DESCRIBES THE REWORK

The blast radius this session measured and then corrected: **41 of 54 open PRs
would red** (21 dependabot, 20 human), not the 29 first reported — `gh pr list
--limit 40` silently truncated a 54-PR population and exited 0. Ruling #199's
`VERIFY_REQUIRED_RE` is the answer; that ruling was received by another session
and is already in the ledger.

## #1026 — ADMIN-5, NOT TOUCHED BY THIS SESSION

Ruling #200 governs it: #195 binds the INVARIANT and its PROOF, never the
MECHANISM, and the practice-row lock is the expected shape.

## ⚠️ ONE CORRECTION THIS SESSION OWES, BEFORE ANYONE READS IT ELSEWHERE

While landing this note I read `docs/canon/INDEX.md`'s stated entry count as
**wrong by 41** — 154 stated against 115 files — and briefly filed that against
`2de0bcea`, the canon-114 commit whose own message is *"the index states its own
count, and I added a row without moving it."*

**That was my error, not theirs.** The arm at `gate-agents-md-size.test.ts:180`
counts INDEX ROWS — including `  - ↳ ` continuation rows — not files in
`docs/canon/`. Measured against the arm's own definition, **154 was correct**, and
"fixing" it to 115 would have reddened a green gate. Restored to **156** for the
two rows added here; the gate passes 9/9.

*The right question asked of the wrong universe, by the session that spent the
day reporting that class in other people's work.*
