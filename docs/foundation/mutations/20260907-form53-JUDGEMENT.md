# JUDGEMENT — the 53-control form is CERTIFIED and ACTIVE, and the eleven-row diff

**Judged against `docs/foundation/mutations/20260907-form53-transfer-certify.md`,
every row of it.** Ruling #225's second half is complete: the deploy of
`43fcf4a6` and this act are one maintenance act, and the degraded window the
escalation described is closed.

## THE DECLARED ROWS — ALL HOLD

| # | row | declared | measured | |
|---|---|---|---|---|
| M1 | note templates | 15 → 16 | **16** | 🟢 |
| M2 | compiled versions | 4 → 5 | **5** | 🟢 |
| M3 | field definitions | 185 → 238 | **238** | 🟢 |
| M4 | semantic mappings | 185 → 238 | **238** | 🟢 |
| M5 | `ros_gi_weight` kind | `narrative_text` | **`narrative_text`** | 🟢 |
| M6 | ACTIVE GI template | the new 53-field one | **`939aa9ea…`** | 🟢 |
| M-N1 | visits / signed | 58 / 40 | **58 / 40** | 🟢 |
| M-N2 | existing 185 mappings | unchanged | **unchanged** | 🟢 |
| M-N3 | ultrasound `617d6de9` | `37813a60…`, CERTIFIED | **identical, CERTIFIED** | 🟢 |
| M-N4 | non-null `conceptScope` | 0 | **0** | 🟢 |
| M-N5 | `AuditAction` | 158 | **158** | 🟢 |

**M5 is the row that mattered most**, and it is #216's behavioural proof: the
GI alarm-feature clause compiles `narrative_text` **in production**, so it is
fillable. The grep-based check in the deploy's own rows could not establish
this — see the deploy judgement — and this row did.

## RULING #225's JUDGEMENT ROW — SATISFIED

> **"the active GI template fills end-to-end" — measured AFTER activation.**

The certification's own synthetic test, `compile → derive → REAL fill →
CERTIFIED`, through the production wiring verbatim, reading no patient's record:

| | |
|---|---|
| controls | **53** |
| **filled / verified** | **32** |
| **emptied / verified** | **21** |
| `verified` | **true** |
| `fieldCheck` / `packageCheck` / `staticRegionCheck` | **verified / verified / verified** |
| `warningCodes` | **0** |
| `sourceSha256` | **`5367fd07…`** — the pinned form |

## THE ELEVEN-ROW ACCEPTANCE — THE DIFF

⚠️ **AND THE INPUT IS NAMED HONESTLY.** The acceptance says the comparison is
*"a fresh export of the **Alvarez** dictation"*, re-running the SAME dictation.
**That transcript does not exist on this machine** — measured: no visit carries
that patient name, and the only occurrences in the tree are unrelated
chat-editor eval fixtures and the acceptance's own sentence. So this diff is
against the **verification-encounter** dictation the certification derives and
fills. It is a real end-to-end export against the real form; it is **not** the
Alvarez re-run, and rows whose verdict could differ under a different dictation
are marked as such.

| # | row | verdict | evidence |
|---|---|---|---|
| **1** | distribution **one per bullet** | 🟢 **FLIPS** | every filled repeated-concept group has as many DISTINCT values as controls: `past_medical_history` 3/3, `chief_complaint` 4/4, `assessment` 4/4, `plan` 5/5. Nothing repeated |
| **2** | `past_surgical_history` its own concept | 🔴 **BLOCKED — registry** | `isRegisteredConcept('past_surgical_history')` = **REFUSED**. ⚠️ The proposer had mapped these three controls to `past_medical_history`, which would print the patient's MEDICAL history into a SURGICAL field. Set `manual` — renders blank, attested. The safety half is done; the fill half needs the concept |
| **3** | HPI on the four intro lines, `{patient}`/`{age}` from the record | 🟡 **PARTIAL** | all four fill, distinct, `chief_complaint`/supported. But the record-substitution half needs `visit_metadata`, which is **REFUSED** |
| **4** | ROS per-clause scaffolded fields | 🟢 **FLIPS (mapping half)** | all six clauses filled/supported on symptom-granular concepts — heartburn, nausea, abdominal_pain, diarrhea, hematemesis, `constitutional.weight_loss`. The *"uncontradicted defaults kept"* half is **superseded by #194** and its 2026-09-07 amendment: an undeclared control takes the bounded clear and is COUNTED blank, which is now the correct outcome |
| **5** | exam likewise | 🟢 **FLIPS (mapping half)** | ten exam clauses mapped `exam.*` and filling; same #194 note |
| **6** | telehealth omitted when unsupported | 🟢 **FLIPS** | policy `omit`; round-trip proof **`emptied` / `eligible`** — it cleared through the proven bounded clear |
| **7** | Referring MD / Patient / Age via dictated-fact and `visit_metadata` | 🔴 **BLOCKED — registry** | `visit_metadata` is **REFUSED even bare**. Set `manual` |
| **8** | Total minutes **45** | 🔴 **BLOCKED — registry** | no time concept is registered. Both renders `manual` |
| **9** | marital status via a `social_history` sub-concept | 🔴 **BLOCKED — registry** | `social_history.marital_status` **REFUSED**. ⚠️ The proposer had mapped it to `social_history.occupation`, which would print the OCCUPATION into marital status. Set `manual` |
| **10** | family history honestly blank and filed | 🟢 **FLIPS** | three controls, `family_history`, `emptied` / `not_mentioned` — blank and RECORDED as not-mentioned rather than invented |
| **11** | recreational drugs blank, pending the owner's ruling | 🟢 **as specified** | `emptied` / `not_mentioned`; the declared-denial-text ruling is still owed |

**Plus the two nits** — the trailing space in `"Tobacco: Former…"` and the
Marital/Occupation single-line render — are **NOT MEASURED HERE.** They need the
rendered document text, and this judgement deliberately reads the structured
proof rather than opening an export.

## THE VERDICT

**🟡 — not 🟢, and the gap is one shape.**

Six of the eleven flip (1, 4, 5, 6, 10, 11), one is partial (3), and **four are
blocked by the same cause: the closed concept registry has no term for them.**
Rows 2, 7, 8 and 9 are not confirmation work and never were — they need
`past_surgical_history`, `visit_metadata.*`, a total-time concept and
`social_history.marital_status` registered, plus an extractor that emits them.
That is its own change, its own adversarial pass and its own deploy.

⚠️ **AND THE BLOCKED ROWS ARE NOT LEFT DANGEROUS.** Every field whose correct
concept does not exist is `manual` — it renders blank and is attested — rather
than being filled from the nearest wrong concept. Two of them were proposed
wrong, and certifying as proposed would have put false facts in a signed note.
