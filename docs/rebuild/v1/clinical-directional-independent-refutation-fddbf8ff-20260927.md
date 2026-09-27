# Directional record guard: independent refutation — 2026-09-27

**REFUTED by adjacent inputs. All 46 previously established configurations now
meet their expected outcomes.** These findings remain within the existing
record-action vocabulary and the physical-removal/documentation distinction.

Frozen candidate: `fddbf8fff3255cdef8e1b04b2a9fc7463913b39d`, generation SHA-256
`b5db05756ee413bcccee6686b1dd7e8e2bbf10d422b245f1b4f986d314a118ea`.
The previous repair `5b95a725` and original union `aa4e8c0d` are retained bases.
No source edits were made.

## Established cases

The previous 46 input configurations and runner were reused unchanged against
candidate and previous repair. The previous repair reproduces its preserved
outputs exactly. This closes every previously demonstrated input, including
the original Unicode, record-retraction, for-complement and physical-removal
cases, without changing their expected outcomes.

Twelve additional configurations were declared before execution and compared
with all three versions. Total this round: **128 version runs, zero errors**.

## F1 — P1: remaining forms of existing actions escape note-wide review

Source: `fddbf8ff:rebuild/core/generation.py:1986` and `v3_note_correction`.
With unique unscoped v3 fields, select only the exact NKA source unit:

```text
No known drug allergies.
Plan: clinician strikes erroneous NKA entry.
```

Candidate, previous repair and original union all return supported
`No known drug allergies.` with exact `[0,24)` evidence. A forced existing
supported answer remains supported in page governance; `governed_supported`
returns `null`, and `governed_decisions` returns `[]`.

The same false green is preserved for these Plan tails:

- `clinician invalidates erroneous NKA entry.`
- `amendments of erroneous NKA entry.`
- `clinician struck erroneous NKA entry.`
- `corrections of erroneous NKA entry.`
- `invalidations of erroneous NKA entry.`

These are ordinary forms of the already declared strike/invalidate/amend/correct
actions. They are unclosed variants, not newly introduced by `fddbf8ff`.

An additional scope probe is:

```text
No known drug allergies.

Plan: clinician withdrew erroneous NKA entry.
```

It also passes all three versions and both stored readers. Removing the blank
line holds on all three through the existing unsettled-context rule. Thus that
control is not evidence that `withdrew` entered the new note-wide correction
reader. Evidence: C03–C10, with C08 as the same-paragraph control.

## F2 — P2: a later chart reference is still mistaken for the removed object

Source: `v3_record_retraction`, particularly the first subsequent reference
return in `fddbf8ff:rebuild/core/generation.py:2012`.

```text
No known drug allergies.
Plan: removal of stitches documented in chart.
```

Only NKA is selected. The original union supports it and returns no stored-reader
warning. Both repairs instead return conflict, empty text, and an Allergies
governance hold. `chart` names where the physical removal was documented; it is
not the removed object. The second preserved counterexample is:

```text
No known drug allergies.
Plan: record removal of stitches in the chart.
```

The same false hold remains. The action/reference ordering is insufficient to
establish their grammatical relationship. These false rejections began in
`5b95a725` and remain in `fddbf8ff`; neither is a new regression unique to the
second repair. Evidence: C01/C02. C11 retains a real record-removal hold; C12
retains the physical-documentation positive without the later chart reference.

## Evidence and limits

Private runtime:
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/clinical-directional-fddbf8ff-20260927/`.
All 46 replay inputs, 12 new inputs, exact source snapshots, raw generation and
stored-reader outputs are preserved. The custody delta seal is
`metadata/060-CLINICAL-DIRECTIONAL-REFUTATION-DELTA-SEAL.json`.

Socket/process operations were disabled; no forbidden attempt occurred. No DB,
provider, Word, render, corpus original, expected map, or unfinished patient-topics
source was accessed. These are pure deterministic probes, not full application
finalization or a qualification campaign.
