# THE ELEVEN-ROW ACCEPTANCE — the owner's definition of done for the custom-file batch

**RECOVERED FROM THE SESSION TRANSCRIPT, 2026-09-05, and recorded here because
it existed nowhere else.** Ruling #191 calls it *"the acceptance test for the
regenerated form"* and does not carry it; the batch's final step is a diff
against it. A definition of done that lives only in a transcript is the exact
failure the record-a-ruling-first rule exists to prevent — and it very nearly
cost the batch its acceptance criteria.

⚠️ **PROVENANCE, STATED SO IT IS NOT READ AS MORE THAN IT IS.** The rows are the
owner's own words, quoted from a session message. **THE NUMBERING IS DERIVED,
NOT QUOTED** — the source lists them as prose separated by semicolons.

## THE NUMBERING RECONCILES AGAINST THE OWNER'S OWN CITATION

The prose reads as ten items if *"ROS and exam as per-clause scaffolded fields"*
is one row, and eleven if it is two. It is two, and the check is independent of
this document: the owner wrote separately that **"checklist row 6 could never
flip"** about the telehealth consent line. Telehealth lands on row 6 **only**
under the eleven-row split. An enumeration that did not reconcile with an
outside citation would be a finding, not a checklist.

| # | row |
|---|---|
| 1 | distribution **one per bullet** |
| 2 | `past_surgical_history` as its **own concept**, surgeries and conditions separated **both ways** |
| 3 | HPI on the **four intro lines**, with `{patient}` / `{age}` from the record |
| 4 | **ROS** as per-clause scaffolded fields — contradicted clauses from evidence, uncontradicted defaults kept |
| 5 | **exam** likewise |
| 6 | **telehealth omitted when unsupported** |
| 7 | Referring MD / Patient / Age filled via dictated-fact and `visit_metadata` |
| 8 | **Total minutes 45** |
| 9 | marital status via a `social_history` **sub-concept** |
| 10 | family history **honestly blank** and filed |
| 11 | recreational drugs blank, pending the owner's ruling on declared-denial text |

**Plus two nits:** the trailing space in `"Tobacco: Former…"`, and the
Marital/Occupation **single-line** render.

## HOW IT IS FLIPPED

**By re-running the SAME dictation** — not by a new one. The comparison is a
paragraph diff plus a fill map against this table, on a fresh export of the
Alvarez dictation.

## ⚠️ WHAT ROWS 4 AND 5 NOW DEPEND ON

Rows 4 and 5 say *uncontradicted defaults kept*. Under ruling **#192** that is
no longer inferred from content: the transfer must **declare
`unmentionedPolicy: 'keep'`** on the six ROS and ten exam controls, and
**`'omit'`** on the telehealth control (row 6). An undeclared control takes the
bounded clear, so rows 4, 5 and 6 cannot flip without those explicit
declarations.

## ⚠️ AMENDMENT, 2026-09-07 — THE SECTION ABOVE IS SUPERSEDED BY #194, AND ITS INSTRUCTION IS NOW UNBUILDABLE

**The superseded wording is kept above rather than overwritten**, per the
standing practice that corrections are appended and dated.

The section *"WHAT ROWS 4 AND 5 NOW DEPEND ON"* instructs the transfer to
declare `unmentionedPolicy: 'keep'` on the six ROS and ten exam controls. It was
correct under #192. **Ruling #194 then abolished the `keep` half entirely** —
*"the machine never prints an undictated default"* — collapsing the policy to
`NULL | 'omit'`, with **no `'keep'` value anywhere** and `default_kept` retired
with its arms.

> **So a session following that tail today would build against a value the
> schema no longer has.** It reads as a live instruction and is not one, which
> is the same stale-authority hazard `AGENTS.md` opens with: a rule you cannot
> execute is worse than an absent one, because it does not look absent.

**THE CORRECTED FORM:**

| row | how it flips now |
|---|---|
| **4** (ROS) and **5** (exam) | **NOT** by a declared `keep`. #194 moved the doctor's defaults to a HUMAN act at review — **REVIEW-DEFAULTS**, audited `DEFAULT_INSERTED_BY_DOCTOR` — with `scaffoldText` carried in the IR for it. An undeclared control takes the bounded clear and is COUNTED as blank, which is now the correct and honest outcome. |
| **6** (telehealth) | unchanged — **`omit`**, the one policy that survived. It clears through the proven bounded clear, carries `omitted_unsupported_default`, earns a byte-verified `emptied` proof, and is counted in its own bucket. |

**The transfer therefore declares `omit` on the telehealth control and nothing
else.** ⚠️ **AND #194's REASONING IS WHY, NOT MERELY THAT IT SAID SO:** `keep`
fired when `conceptCandidates.length === 0`, and concept equality is the only
test this pipeline performs — so *"nothing dictated contradicted this default"*
was always a claim about the EMPTY SET. Measured there: a scaffold reading *"no
varicosities, no oedema and no ulceration"* was KEPT on a visit dictated as a
*"large weeping ulcer … with gross bilateral oedema"*, because the fact carried
`chief_complaint` and not `exam.vascular`.

⚠️ **AND ROWS 4 AND 5 CANNOT FLIP AT ALL UNTIL REVIEW-DEFAULTS CAN FIRE**, which
is a separate, measured blocker filed as **ruling #201**: production reads
`total_fields=185 scaffolded_true=0`, because all four compiled versions predate
the compiler that sets `isScaffolded` and `compilerVersion` never moved. **That
is Design/Admin's lane, not this one** — recorded here only so the next reader of
this checklist knows why the rows will not flip on a fresh export alone.
