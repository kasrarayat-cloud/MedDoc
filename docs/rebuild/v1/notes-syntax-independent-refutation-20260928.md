# Independent ordinary-sentence syntax refutation — 2026-09-28

Candidate `978d6ab004ce78a2ada0ecb34a635f18e0ca1e8e` in the separate
`v1-notes-workflows` worktree, compared with base `4caa34431a60e6ce3409ecadbbb6989b50659d7b`.
Generation SHA256 `bdb7304bbb2a51b4c2e80d18613c02c560a09c8a517a4a0855f6efe8419dcee9`;
syntax helper SHA256 `44bb30eda9405fb38fcbea2eefc3450505443f71d71aed9ed522f1642c30e2b8`.
No source edits, provider requests, database connections or corpus reads.
The harness disables sockets and uses a dummy database port.

## Demonstrated introduced finding: foreign subject accepted as patient activity

At `rebuild/core/generation.py:2633`, the new completeness allowance treats the
lexical prefix `The patient ` as established patient ownership. At
`rebuild/core/v3_syntax.py:58`, the syntax check requires one subject but never
checks that this subject is the patient.

Concrete notes: **“The patient advocate attends an art class every Monday.”**
Question: **“What activities does the patient attend?”**
Provider selection: the entire exact source unit, with its original offsets.

- Exact base: `conflict`, empty answer.
- Candidate: `supported`, the full advocate sentence as the patient's answer.
- Candidate `governed_decisions` with the generated answer and review tick: `[]`.
- The parser correctly labels `advocate` as `nsubj` and `patient` as `compound`.
  This is not a parser misclassification; the application discards that distinction.

The same introduced outcome is reproduced for **“The patient care coordinator
attends an art class every Monday.”** and **“The patient caregiver attends an art
class every Monday.”** The full text survives, but its foreign subject is not held
for destination review as promised. This pure probe proves generation and the
shared finalization governance reader; it does not claim a separate HTTP exercise.

A related diagnostic, **“The patient attends an art class and her father swims
every Monday.”**, also moves from conflict to supported. It has two differently
owned finite clauses, so the stated single-clause claim is wider than the code's
check: only a conjunction attached to the first subject is rejected. The stronger
foreign-subject cases above establish the blocker without depending on this mixed
sentence's clinical applicability.

## Bounded other lenses and controls

Sixteen exact synthetic inputs are retained in `result.json`, with parser token
relationships, base/current answers and governance results. Explicit patient
activity, complete negative activity and patient-only coordinated activity retain
full wording and offsets. Possessive father, conjoined patient/father subject,
conditional, incomplete fragment, embedded hopes-to clause and question remain
held. The modal `should attend` is supported on both versions and is explicitly
not presented as an introduced finding. `Patient education improves sleep` is an
additional noun-compound diagnostic, not a distinct blocker claim.

The compound-question display's partitioner and template diff were read. Printed
text is concatenation-preserved and escaped by the existing template renderer;
existing clinician review remains required. No additional concrete offset/data
loss or compound-review bypass was demonstrated in this bounded pass. This is not
broad semantic qualification.

## Evidence and disposition

Private runtime: `/opt/meddoc-pro/.worktrees/v1-word-workflows/rebuild/.runtime/notes-syntax-refutation-20260928/`.
The exact probe and result are copied beside this report. All first results remain.
Root was notified for independent verification. Do not merge this candidate until
the demonstrated subject-ownership defect is repaired and the finished repair is
independently replayed. The Word engine source remains separately frozen.
