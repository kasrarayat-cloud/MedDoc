# Literal source-subject preparation — 2026-09-27

Candidate worktree: `/opt/meddoc-pro/.worktrees/v1-literal-subjects`, branch
`v1/literal-subjects`, base `ea6cae5c754ce4e8c8e51d2992cc53c41cd294c4`.
This is a narrow dependency with completed independent finished-diff review, not a claim
that retained notes4/7/8 or V1 ordinary input now pass.

## Change and boundary

The exact, complete `No known drug allergies.` source unit can name one text or
long-text Allergies destination. Its complete negative declaration is retained;
it is never rewritten to `none`. The destination context must be empty or its
own normalized label (the actual table importer emits `context: Allergies`).
Additional context remains ineligible. The complete owned declaration alone
gets the finite-statement exemption; unrelated fragments do not.

The existing Examination subject reader additionally recognizes the retained
`Neurological examination …` and `Heart and lung examination …` heads through
the existing finite factual-predicate, qualification and scope gates. It keeps
the original full source text, including anatomical and negative wording.
The two new heads require empty or same-label Examination destination context;
another person, section, time or side context leaves the subject unresolved.

The shared source reader supplies generation, stored-answer display, save and
finalization. Existing duplicate questions/statements, foreign destinations,
family/history/correction context, unresolved neighbours and cross-topic
references continue to hold answers for review. This change establishes no
pronoun, caregiver or patient reset. `He takes no regular medications.` in
retained note7 remains held. No clinical synonym classifier was added.

## Finite verification

All inputs were synthetic or existing known development notes. No provider
call, unseen template, acquisition, deployment or production data access occurred.
The worker test used a mocked Anthropic client and explicit socket denial; it
does not establish actual Sonnet5 behaviour.

| Evidence | Result |
| --- | --- |
| `02-positive-red.log` | Baseline rejects the exact complete negative declaration. |
| `03-focused-first.log` | 8/9 pass; actual workflow fails because table mapping repeats the label as context. Retained unchanged. |
| `04-workflow-diagnostic.log` | Real imported field metadata confirms `context: Allergies`; fixed by accepting only that identical context, without rewriting the template. |
| `05-focused.log` | **23 pass in 5.246s**: 9 new controls plus 14 existing subject/coupling controls. |
| `07-workflow-capture.log` | **1 pass in 3.632s**: repeat of the same positive solely to retain synthetic original/finalized Word artifacts and their hashes. |
| `01-retained-before.json`, `06-retained-after.json` | Original fields, notes and selections for retained notes4/7/8 replayed locally; supported/held statuses unchanged. |
| `08-scoped-exam-verified-red.json`, `08-scoped-exam-verified-base.json` | Independent refutation exposed new examination heads accepting Mother/Family history destinations. Reproduced locally and by root; baseline holds those four cases. |
| `09-final-focused.log` | **24 pass in 5.215s** after the minimal context restriction: 10 new controls plus the same 14 existing checks, including actual table export. |
| `10-retained-final.json` | Final source replay confirms the unchanged three retained outcomes and identical source hash. |

The first frozen source was **not** accepted after independent review. The
demonstrated scoped-destination defect was repaired only for the two new
examination prefixes. Both heads now refuse Mother, Family history, left/right
knee, previous-visit and section context on generation and stored review.
Original failing evidence and earlier passing runs remain separate. Independent
final refutation returned **NOTHING FOUND** on the exact final hashes below;
its unchanged 21-case probe closes the four demonstrated scoped failures while
the other 17 results stay identical. Independent actual-table positive checks
for both heads retain full text and original-package export. See
`INDEPENDENT-REFUTATION.md`; its original report refers to the uncommitted source
it inspected, which is byte-identical to source commit
`1bba17d550161cd72be7b08c1c8d3aa15031d63e`. No merge/ready claim is made here.

The positive workflow exercises real upload and mapping confirmation, queued
mocked worker generation, doctor review, answer save, finalization and export
into the original Word template. Both complete source statements survive;
recorded export hash matches bytes and original bytes stay unchanged. The
constructed stale-supported family-context case refuses on page/save/finalize.
This is a stored-state negative control, not a claim of an observed ordinary
note-save mutation; normal note save clears prior answers.

Adverse controls cover incomplete or modified negative declarations, negative
examination heads, family/historical/hypothetical scope, corrections, foreign
fields, duplicate source declarations/questions, scoped/non-text destinations
and an allergy reference from another clinical topic. Assertions retain source
evidence and require no adoptable suggestion on held cases.

Tests used isolated PostgreSQL **55702**, verified before each Django command.
Test databases were destroyed normally. No broad suite was run. Core test
discovery includes the new `core/tests/test_v3_literal_subjects.py` module.
A preliminary diagnostic launch through shell stdin failed because Django's
shell `__file__` refers to its own module; it performed no candidate replay.
The corrected `runpy.run_path` diagnostic and all scored runs above are retained.

## Actual retained outcome

- Note4: all eight selected answers still held. The declaration/examination are
  recognized; unowned earlier source, the unresolved `She` continuation and the
  qualified Plan block prevent isolated adoption.
- Note7: existing labelled Allergies answer still supported; all six other
  selected answers remain held, including negative Medications.
- Note8: all eight selected answers still held. Smoker and Examination now form
  separate source blocks, but unowned early source and qualified Plan remain.

No retained score or denominator is changed by this preparation. A reviewed
union with any separately justified context relation must demonstrate its actual
retained outcomes before claiming improvement. The parent owns that integration;
this branch does not alter the other agent's topic/Unicode safety changes.

## Identity and handoff

- `rebuild/core/generation.py` SHA256:
  `03e584bed9ab5e6bb7d6e17c4b46233136aac0132f6d48772970fa739204986a`
- `rebuild/core/tests/test_v3_literal_subjects.py` SHA256:
  `4447e84df1ad94f644c02e7a654d9d866db9912d1bd9a268f2ae1983e055c6d5`
- Evidence directory: `docs/rebuild/v1/literal-subjects-20260927/evidence/`.
  `MANIFEST.json` covers every retained text artifact and names/hashes the two
  runtime-only synthetic Word files.
- Runtime: `rebuild/.runtime/literal-subjects-20260927/`, including runnable
  `inspect_retained.py`, `inspect_retained_after.py`, `capture_workflow.py`.
- Independent review of root's unrelated test-fixture correction759e0dcd is
  separately recorded in `docs/rebuild/v1/test-fixture-review-759e0dcd.md`.

Source is frozen with independent refutation complete. Next safe action: let the release owner
integrate the union and measure unchanged retained cases. Do not call this
standalone preparation a retained-case fix, compatibility qualification, native
Word acceptance or a deployed change.
