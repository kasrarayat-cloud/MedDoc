# Gastroenterology — specialty rollout, evidence report

**Date:** 2026-08-14 · **Branch:** `feat/gi-specialty` off `833a6f2d` (contains RC-1)
**Worktree:** isolated; the shared checkout at `/opt/meddoc-pro` was never used for this work.

---

## 1 · THE MEASURED SPECIALTY SET, BEFORE THE CHANGE

Read from `packages/shared/src/specialties.ts:22` — **14 rows**. This is the
single source of truth: `SPECIALTY_IDS` (the Zod tuple), the TS union, all four
pickers and `findSpecialty()` are all DERIVED from it, so it is simultaneously
the enum and the dropdown.

| # | slug | label | templateId | in the new-visit dropdown? |
|---|---|---|---|---|
| 1 | `unspecified` | Unspecified | `generic` | no — settings only |
| 2 | `primary-care` | Primary Care | `primary-care` | yes |
| 3 | `cardiology` | Cardiology | `cardiology` | yes |
| 4 | `psychiatry` | Psychiatry | `psychiatry` | yes |
| 5 | `pediatrics` | Pediatrics | `pediatrics` | yes |
| 6 | `ob-gyn` | OB-GYN | `ob-gyn` | yes |
| 7 | `dermatology` | Dermatology | `dermatology` | yes |
| 8 | `orthopedics` | Orthopedics | `orthopedics` | yes |
| 9 | `urgent-care` | Urgent Care | `urgent-care` | yes |
| 10 | `pain-management` | Pain Management | `pain-management` | yes |
| 11 | `weight-management` | Weight Management | `weight-management` | yes |
| 12 | `bariatric-surgery` | Bariatric Surgery | `bariatric-surgery` | yes |
| 13 | `vascular-surgery` | Vascular Surgery | `vascular-surgery` | yes |
| 14 | `ultrasound` | Ultrasound | `ultrasound` | yes — **flag-gated**, and the flag is **ON in production** |

**Dropdown = 13** (`SPECIALTIES_FOR_VISIT_CREATE` drops `unspecified`;
`visibleSpecialties()` keeps `ultrasound` because
`NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`, measured from the running containers).
**After GI: 15 catalog rows / 14 in the dropdown.**

### ⚠️ The catalog is not the only specialty-shaped set, and they disagree

| set | where | members | agrees with catalog? |
|---|---|---|---|
| `SPECIALTIES` | `packages/shared/src/specialties.ts:22` | 14 | — (it is the catalog) |
| `SPECIALTY_KEYS` | `specialty-keys.ts:20` | 15, snake_case | **NO** — has `endocrinology`, `functional_medicine` (no catalog row); **lacks `ultrasound`** |
| `SPECIALTY_GUIDANCE` | `specialty-guidance.ts:13` | 9 keys | partial by design (rest fall back to generic) |
| `SpecialtyKind` | `spec-chip.tsx:7` | 6, pre-catalog slugs | **NO** — and the component has **0 JSX mounts** |

**Nothing in the repo diffed any pair of these before tonight.** The GI change
adds the first cross-catalog gate (catalog ↔ ASR). See §4.

### The production population (`transcribe_visits.specialty`)

`bariatric-surgery` 16 · `ultrasound` 17 · `primary-care` 2. `users.specialty`
holds free text in a *different* vocabulary (`cardiology`, `Vascular Surgery`,
196 NULL) — label-cased and slug-cased values in the same column family.

---

## 2 · THE ENUM QUESTION, ANSWERED BY THE DATABASE

The brief said *"pg_enum if database-backed — only the database's answer counts."*
Measured on production `meddoc`:

- **18 pg_enum types exist. None is a specialty.** (`AuditAction`, `VisitType`,
  `PracticeRole`, … — full list read.)
- All four `*specialty*` columns are plain `text`:
  `transcribe_visits.specialty` (**NOT NULL**), `users.specialty`,
  `note_templates.specialtyBaseline`, `account_deletions.specialty`.
- **Zero CHECK constraints** mention specialty.

> ### ⇒ **NO MIGRATION IS REQUIRED.** The three-layer lesson collapses to code.

The database imposes no constraint; the *catalog* is the enforcement point,
because it drives `z.enum(SPECIALTY_IDS)` at every API edge. Appending a row
extends the TS union, the Zod validator and all four pickers in one edit.
`schema.prisma` needs no change — and a §2.5 migration declaration would have
been a ceremony over an act that does not happen.

⚠️ `schema.prisma:2420-2421` documents `specialtyBaseline` as pointing at
`specialty-keys.ts`. That is stale prose and it is the origin of the brief's own
"the enum" premise. Corrected in the catalog header.

---

## 3 · WHAT GASTROENTEROLOGY GETS, AND WHY IT IS ADDITIVE

`{ id: 'gastroenterology', label: 'Gastroenterology', templateId: 'gastroenterology' }`
appended (never inserted — two call sites depend on catalog order).

### E/M and the prompt builder both fall out of ONE existing predicate

`specialties.ts:103` — `emAppliesToSpecialty(id) = !(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(id))`

`isImagingReportSpecialty('gastroenterology')` is `false`, so:

| consequence | site | result for GI |
|---|---|---|
| office-visit E/M applies | COMPUTE / STORE / EXPORT guards | **ON — no edit** ✅ *(brief item 3)* |
| report shape | `04-generate-soap.ts:94-95` `isUltrasoundReport = !emAppliesToSpecialty(...)` | **SOAP builder**, not imaging |
| specialty guidance | `04-generate-soap.ts:100` | **applied** (ultrasound deliberately gets `null`) |

**One call, three consequences.** That coupling is itself a hazard and is
written up as GI-OPEN-1 — the predicate is *named* for E/M and *used* as the
builder switch, so the obvious future one-liner ("a GI procedure note has no
office E/M level") would silently move GI to the imaging prompt builder.

### Structure still comes from the doctor's template — verified at the resolver

`resolve-active-template.ts:86-113`. The real GI templates in production carry
`encounterType = NULL`, i.e. they are the doctor's **catch-all** (step 2). A GI
visit requests `encounterType='gastroenterology'`, finds no exact match at step
1, and falls through to that same catch-all. **The template that resolves today
is the template that resolves after GI ships.** The specialty tunes the prompt;
it does not touch the layout. Exactly the fidelity contract.

### The GI guidance is deliberately CONTENT-ONLY

It branches on the two encounter shapes the pilot produces — office visit, and
procedure/operative note — following the `bariatric-surgery` "identify the phase
first" pattern. It differs from the two older entries on purpose: those
prescribe layout (*"Include a 'Body Composition' subsection"*, *"First line of
HPI MUST be…"*) and predate the fidelity contract. GI's says what to CAPTURE and
never what heading to create, because a GI operative-note template brings its
own six sections and guidance that invented headings would fight it.

Safety clause, both shapes: never state an endoscopic finding, a pathology
result, or a **surveillance interval** that was not dictated — if the clinician
said the interval is pending pathology, document that and supply no number.
A plausible fabricated interval is a cancer-screening decision, not a
formatting nicety.

---

## 4 · THE ASR LAYER — THE ONE THAT WOULD HAVE HALF-SHIPPED

`normalizeSpecialty('gastroenterology')` would have returned `'unspecified'`,
whose bundle **exists and is empty** — a real key, a real lookup, zero terms, no
error. GI dictation is exactly the vocabulary a bundle exists to protect, so the
change includes `SPECIALTY_KEYS` + 8 `SPECIALTY_VARIANTS` rows + a bundle.

### ⚠️ The 30-term ceiling is a PROXY. The budget is the constraint.

A 30-term GI draft **passed** the term ceiling and **tripped the budget
enforcer**: 143 estimated tokens against 111 for the heaviest existing bundle
(`estimateTokens = ceil(len/3.5)`, `DEFAULT_TOKEN_BUDGET = 450` shared with core
+ safety floor). GI is the first specialty whose vocabulary is mostly multi-word
anatomy — `endoscopic mucosal resection` costs 8 tokens, `omeprazole` costs 3 —
so proxy and constraint diverge here for the first time. Caught by the B1
regression guard (`confused-drug-names.test.ts`), which enumerates **every**
specialty and asserts `budgetEnforced === false`. Retuned to **24 terms / 103
tokens**, with the arithmetic and the dropped-term list written into the file.

Left unfixed, Deepgram would have silently trimmed GI terms at runtime.

### Independently re-derived, by an adversarial agent that did not trust my arithmetic

Composed through the real builder with the real safety floor, every specialty:

    CORE 57 terms / 184 tokens · SAFETY FLOOR 45 terms / 133 tokens (baseline 317)

| specialty | bundle terms | bundle tok | terms reaching payload | TOTAL | enforced |
|---|---|---|---|---|---|
| dermatology | 30 | 111 | 29 | **424** | false |
| **gastroenterology** | **24** | **103** | **24** | **420** | **false** |
| pediatrics | 26 | 95 | 26 | 412 | false |
| orthopedics | 26 | 106 | 22 | 409 | false |
| *…all 15…* | | | | | **all false** |

GI sits at **420 of 450 — 30 tokens of headroom**, second-heaviest behind
dermatology, and **all 24 of its terms reach the payload** (nothing absorbed or
trimmed). `normalizedTo gastroenterology` also confirms the `SPECIALTY_VARIANTS`
bridge resolves — without it this row would have read `normalizedTo unspecified`
with a specialty layer of 0.

⚠️ **30 tokens is not much headroom.** The next term added to GI must be
measured, not counted.

---

## 5 · THE GATES — TWO WERE FAKE, AND I VERIFIED THAT RATHER THAN ASSUMING IT

| gate | claimed | actually did |
|---|---|---|
| `deepgram-keyterm-builder.test.ts` *"every canonical specialty has a bundle"* | universal | asserted **4 literal keys** against 15 bundles, no iteration |
| `specialty-keys.test.ts` *"every variant maps to a value in SPECIALTY_KEYS"* | universal | walked a hardcoded **16-string** `examples` array |

Both now enumerate. Added: a **cross-catalog gate** (every `SPECIALTIES` id must
resolve to a NON-EMPTY bundle, or carry a named exemption) — the check neither
existing gate performed, because both watched the vocabulary module's *internal*
consistency and never compared it to the product catalog. `ultrasound` is on the
exemption list with its reason and a pointer, plus an **anti-stale arm** that
goes RED the moment a bundle lands, so the exemption cannot outlive its reason.

### Mutation proofs — red AND green, and the counter-proof

| # | mutation | new gate | old gate |
|---|---|---|---|
| M1 | GI key present, bundle removed | **RED** ✅ | — |
| M1b | *same mutation*, original gate | — | **PASSES** ⚠️ — the argument for the fix |
| M2 | variant → non-canonical key | **RED** ✅ | — |
| M3 | `ultrasound` exemption removed | **RED** ✅ | — |
| M4 | `ultrasound` gains a bundle, exemption kept | **RED** ✅ (anti-stale) | — |

Each restored from a scratch copy and re-proved green. M4 is the
mutate-toward-SUCCESS control: the gate MOVES when the guarded thing is fixed.

---

## 6 · TEST EVIDENCE, IN THE PRODUCTION FLAG UNIVERSE

Flags read from the **running containers** (`docker exec … printenv`), not
`.env`: `NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`,
`TRANSCRIBE_MD_EVIDENCE_ANCHORS=true`, `MOCK_AI_CALLS=false`.

- `tsc --noEmit` — **0 errors**
- full unit suite, anchors ON — **3808 passed, 8 failed, 296 files**
- the 8 are **inherited** (ruling #108: `l4-golden-prompt` ×1,
  `04-generate-soap` ×7). **Proved, not assumed:** all 8 changed files restored
  to pristine `HEAD` content, `git diff --name-only` confirmed **empty**, re-run
  produced the **identical 8**. GI adds zero failures.

⚠️ **My first baseline attempt was contaminated and an assertion caught it.**
The scratch backups were taken *after* the first two edits, so "restore from
backup" restored my own work. The tell was a line I had written on a hunch —
`GI present in baseline? (expect 0)` printed **1**. The
backup-before-first-mutation rule has an ordering requirement that is easy to
satisfy late and impossible to detect afterwards.

---

## 7 · WHAT IS NOT DONE, NAMED

- **The QA walk (brief item 4) has NOT run.** It requires QA images rebuilt from
  this branch: `meddoc-pro-transcribe-md:qa` is `2026-08-11 14:54Z` and the
  worker `:qa` is `2026-08-13 17:29Z`, so neither contains GI — a walk against
  them would read green and prove nothing (the B8 shape). The rebuild was
  **deliberately held** while a peer session ran an irreversible production
  deploy on the same host.
- **QA is one migration behind** — `20260813231500_rc1_reclassify_fixed_blocks`,
  which is RC-1's, not GI's. `assert-migrations-applied.sh --qa` exits 1.
  The QA rebuild will carry it.
- **CPT / ICD coding for GI** — recorded, not built, per instruction. See
  `docs/backlog/gi-open-items-20260814.md` GI-OPEN-2; the codes are measurably
  absent and 07b drops them silently.
