# Diagnosis: ordinary_notes failure 2 (2026-09-30)

reopen_stage: ordinary_notes
failed_attempts: 18,19,20
repair_commit: 1f1a49327b6ca76cbed3539c320f4aa24e903d2e

**What stopped the stage.** The first remainder run (reopening 1, runner `ee5c1182`) sent N03 (attempt 18), N10
(attempt 19) and N13 (attempt 20) on the field-relations path. Attempts 18 and 19 completed with no unsafe answer.
Attempt 20 (N13, request recorded in the ledger) returned a well-formed v2 answer in which the model reported both
contradictions: each field `conflict: true`, its selected statements marked `contrary`. `records()` refused the whole
response ("Ordinary relations disagree with their complete source selection."), the job failed as a platform
failure and the stage stopped as a contract failure before N14, N15 and N16. Nothing was adopted.

**Repair.** `dfde4fc8`: a field whose selection disagrees with its relations is held for that field; malformed output
still refuses the whole response. Its refutation confirmed a HIGH (a claim by relation alone was invisible to the
competitor check between repeated questions and numbered slots), repaired in `1f1a4932`: a field's claim is every
unit it selects plus every unit its relations mark answer or qualifier, and claims compete like selections. The
re-refutation confirmed LOW findings only. The contract identity is unchanged (v2), so the committed amendment
`20260929-quillmd-v1-sonnet5-relations-contract-amendment.md` still applies. Replayed offline, attempt 20 now holds
both N13 fields with the job succeeding.

**What the next remainder can show.** The remainder is N14, N15 and N16. Attempts 17 and 20 remain recorded stops, so
the stage cannot pass; the run measures the veto on the three remaining planned cases.
