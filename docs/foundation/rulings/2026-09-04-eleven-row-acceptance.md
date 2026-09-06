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
