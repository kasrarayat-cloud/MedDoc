# Note4 source-evidence slice — diagnostic closeout

**No clinical eligibility change and no automatic gain.** Internal semantic and
source-contract engineering remains necessary. Funding, a model-name change or
patient attribution alone does not fix this gap.

Isolated worktree `/opt/meddoc-pro/.worktrees/v1-patient-evidence`, branch
`v1/patient-evidence`, base `e37e17f041cb9e080f2a8f176b2ad8b6930aa880`.
Application source is unchanged. Generation SHA256:
`a7bbe3d9efd0db5247dccebeba0cb97137786312b03f22994c394cdfb744a81b`;
actor module SHA256:
`56f687a3f22fc4c7ce6acd494ff396f97d92cd020e0c7f3492afad079dd7119a`.

## Original result reproduced

The exact retained note4, imported field definitions and all eight original
selections were replayed with simulated unit selections and denied network
connections. The same three named values are supported: Examination, Assessment
and complete Plan. Five values remain held, including the four scoped targets:

| Target | Exact original selected source | Current result |
| --- | --- | --- |
| Chief complaint | `This is a 30-year-old female seen for headaches.` | Held; it selects one sentence from the four-unit unowned source block. |
| HPI | `The headaches started two months ago and are worse in the morning.` plus `She denies visual changes, nausea, or weakness.` | Held; incomplete source block with preceding actor and subsequent medication context. |
| Medications | `She takes ibuprofen as needed.` | Held; the actor ledger establishes patient attribution but no medication-field/context acceptance relation. |
| Smoker | `She is a nonsmoker.` | Held; no reviewed option relation exists for this pronoun statement within the full note. |

Allergies remains held under the earlier NKA containment. The original note and
all first-pass results are preserved. The wider retained result is still12/12
and26/77; this diagnostic did not rerun or alter that fifteen-input denominator.

## Why actor-based splitting is insufficient

Five predeclared controls inspected the existing source reader: the original
note and four variants changing only its Assessment to:

- `daily cigarette smoking.`
- `ibuprofen cessation.`
- `penicillin anaphylaxis.`
- `penicillin hypersensitivity.`

All five have a **complete actor ledger with identical actor-relation types,
source-block membership and eligible actor destinations**. Source text and its
actual offsets are preserved separately, not normalized away. Each of the four
target answers and Allergies is held in generation. Forced historical supported
records are also governed for every case. The latter two controls retain the
previously demonstrated NKA failure class; the first two show why a contrary
smoking or medication-status Assessment cannot be discarded as another actor's
topic merely because the selected predicate has an actor.

This is a refutation of the proposed structural shortcut, not a new defect in
the current held outputs. No unsafe candidate was applied to application code.
The exact original all-eight-pick replay is separate from these five-field
context probes; omitted offers in a probe did not change the source document.

## Exact engineering dependency

`patient_relations` establishes actor and local qualifier provenance. It does
not establish a destination or prove that another assertion cannot change a
selected answer. `v3_scope_selection` currently requires complete source blocks,
while generation also checks competing unowned destinations. Splitting that
block can identify useful source spans, but it cannot safely erase governing
context. The existing natural-Smoker relation is deliberately limited to an
otherwise empty note with an explicit Patient statement.

A follow-up design must specify **source span, actor, destination, polarity/time
and governing-context acceptance together**, with the same result used by
generation, display, save and finalization. It must explain how an Assessment
that changes a medication, smoking state or negative allergy declaration remains
governing even without repeating the printed field label. Source offsets and
actor membership alone cannot validate that semantic relationship. A clinical
synonym dictionary, a whitelist of note4's benign Assessment, or a mandatory
labelled-note workaround would not establish the contract.

The independent Word agent reviewed this bounded design claim and found no
narrower structural release justified by the evidence. The parent instructed a
diagnostic-only freeze. No permission, account, agreement or funding failure
blocked this work; the unresolved dependency is an internal acceptance design
and its clinical/source evidence. It is not a claim that ordinary-note support
is impossible, nor a decision to defer required V1 work to a later patch.

## Verification scope and handoff

Evidence files retain the original replay, five predeclared controls, exact
source quotes, answer objects, stored-governance results, structural comparison,
scripts and hashes. Runtime: `rebuild/.runtime/patient-evidence-20260927/`.
No database, live model, holdout, corpus campaign or application write was used.
DB55706 remains assigned to this stream but was not accessed. No process remains.

The existing original-note4 worker → review → five clinician decisions →
finalization → Word export proof is reused from the reviewed parent union at
the same application source, not rerun or claimed as new automatic completion.
All five clinician decisions remain assisted. No new workflow/render/native
Word qualification is asserted. Next: preserve this frozen diagnostic and define
the shared contextual acceptance contract before granting new eligibility.
