# Round nine on #1018, round six on #1036 — step 6 under #254/#286

**Run 2026-09-08. 12 lenses in write-sealed sandboxes at the exact heads
(#1018 `53d5a939`, #1036 `260d5653`), every finding put to 3 independent
adversarial verifiers. 108 agents, 106 completed, 2 verifier calls errored —
both on findings that still carried two voters.**

**32 raw findings → 3 refuted → 29 survivors.**

| PR | survivors | CODE | INSTRUMENT | #254 verdict |
|---|---|---|---|---|
| **#1018** | 8 | **2** | 6 | ⛔ **DRAFT HELD** |
| **#1036** | 21 | **6** | 15 | ⛔ **DRAFT HELD** |

⚠️ **NEITHER DRAFT RELEASES, AND TWO OF THE CODE DEFECTS ARE MINE — INTRODUCED
BY THE VERY RULINGS THIS ROUND WAS ORDERED TO CHECK.** That is the round working.

---

## THE TWO I INTRODUCED

### `DL-2` — my #267 change closed the document for a locum

`readAndPrepareTemplateTwinFill`'s single `practiceId` parameter does **two
jobs**, and I moved it to the right value for one of them:

| line | what it scopes | wants |
|---|---|---|
| `fill-engine.ts:502` | `compiled.sourceArtifact.practiceId !== input.practiceId` | the **TEMPLATE OWNER'S** practice |
| `fill-engine.ts:587`, `:867` | `transcribe_visits` lookup / `visitByIdScope` | the **VISIT TENANT** |
| `fill-engine.ts:591` | the override-row read | whatever the WRITE stamps |

⚠️ **NEITHER VALUE IS CORRECT, AND `main` WAS BROKEN IN THE OTHER DIRECTION.**
`main` passed `visit.user.practiceId` (the author's), so on a locum visit the
visit lookups at 587/867 found nothing. #267 made those right and broke
provenance at 502: `TEMPLATE_PROVENANCE_MISMATCH`, caught at
`preview-visit-document.ts:437`, returns `miss('fill_failed')` — **no document at
all**, and the insert-default door refuses forever.

**This is not fixable by choosing a better value.** The parameter must be split:
a template-provenance practice and a visit tenant. Which one owns a locum's
TEMPLATE is a product decision with no ruled precedent — **class (a), the
owner's**.

### `F1` / `F7` — my #278 atomicity did not cover the case it was written for

⚠️ **`rotate-ledger.sh --apply` STILL wipes `RELAY.md`'s archive index — 25 rows
to "0 archives · 0 chars" — and STILL prints `✔` and "rotation applied".**

The reason is precise and it is my miss: **#278 says *"write a temp copy, run the
LEDGER GATES on it, swap"*, and I ran the script's own post-conditions instead.**
Those three (bytes changed, head shrank, no duplication) all pass on a wiped
index. `gate-ledger-reachability` is what catches it, and it never ran on the
staged copy. The staging works; **the wrong checks were run inside it.**

`F7` adds that `RULINGS.md` cannot rotate at all — no dated level-1/2 headings for
the cutoff scan — so every `--apply` exits 2, *after* the RELAY leg has already
swapped its damaged head in.

---

## #1036's OTHER CODE DEFECTS — FOUR UNGUARDED ADMIN DOORS

`R6-RACE-1`, `V1`, `D1` and `FG-1` are four lenses on one finding, and the census
is worse than any of them said. **Measured across every admin route:**

| route | writes a user row | `withPracticeLock` | `wouldStrandPractice` |
|---|---|---|---|
| `suspend` | ✅ | ✅ | ✅ |
| `soft-delete` | ✅ | ✅ | ✅ |
| **`unsuspend`** | ✅ | ❌ | ❌ |
| **`grant-admin`** | ✅ | ❌ | ❌ |
| **`revoke-admin`** | ✅ | ❌ | ❌ |
| **`force-logout`** | ✅ | ❌ | ❌ |

⚠️ **#268's door list was HAND-ENUMERATED AT FOUR, and the tree has seven routes.**
`unsuspend` reaches the orphan guard's advisory lock while holding its own row
lock — #268's deadlock, reachable, at a door nobody counted. `D3`/`V1` name the
generalisation: **nothing derives the doors from the tree**, so the fifth is
invisible at 46/46.

**`D2`** — the INSERT/orphan arm creates a class of refusing doors with **no
friendly refusal**: an invited doctor gets *"Please try again"* forever.
**`R6-2`** — `READ UNCOMMITTED` is refused although the guard is provably correct
there; the check tests a **string**, not the property it cares about.

---

## THE INSTRUMENT SURVIVORS WORTH NAMING

**`NM-1` is filed CODE and is the sharpest finding of the round** — a NINTH
unmirrored site. `validation/index.ts:632` carries a **partial second copy** of
`requiresClinicianInput`: three of its five clauses, applied to a `not_mentioned`
the ladder produced for the opposite reason. On a MANUAL or
`verified_note_selection` field with `required: true` it emits
`REQUIRED_FIELD_NOT_MENTIONED` at **blocking**, so the doctor's own form is
withheld on every visit — verbatim the harm the `manual_source_not_filled` row
exists to prevent. Demonstrated with a negative control, and
`grep -rn REQUIRED_FIELD_NOT_MENTIONED src` returns exactly **one** line: the
emission. **No test in the repository names it.**

Also: `L1`/`M1`/`FG-4` — #280 traded the regex's byte-range boundary for a
FUNCTION boundary and **inherited the blind spot**; the tracer sees 7 of the
resolver's 17 reads, and `missingResolution`'s omit branch is now in *no* read
set. `FG-2` — the ladder's ORDER is pinned only at index 0. `FG-3` — the
biconditional's encounter can never reach `omitDeferralGuard`, so the deferral
half is unmeasured. `R6-RACE-2` — **`mk_moved` plants the relocated lock behind
an early return**, so on the `owners_left > 0` path the "moved" mutant *is* the
delete mutant; #279's 10/12 needs re-deriving. `F4` — the generated census says
"130 rulings" over a block of 235 rows.

---

## REFUTED BY VERIFIER MAJORITY (3)

- the worker fill reading the author's practice (2/3 — superseded by `DL-2`'s fuller account)
- a `search_path` shadow of `current_setting` defeating #269 (2/3)
- three "SUPERSEDED by…" rows carrying `OWNER-RULING` in the status column (2/3)

---

## WHAT THIS ROUND ESTABLISHES

⚠️ **Two rulings I implemented and reported as done were incomplete, and the
round found both.** #267 over-applied a correct rule to a parameter doing two
jobs; #278 built the right mechanism and ran the wrong checks inside it. Neither
was visible to any gate on either branch — including the gates I added in the
same commits.

**Nothing here is fixed yet.** The unguarded-door census and the #278 gate gap
are unambiguous and small. `DL-2`'s parameter split is a product decision.
