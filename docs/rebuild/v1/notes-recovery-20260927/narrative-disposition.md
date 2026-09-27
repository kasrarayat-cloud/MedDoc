# WM narrative disposition for V1 — 2026-09-27

The owner requires ordinary typed and reviewed dictated notes as well as the WM development regression form. A mandatory labelled-note contract is not an acceptable substitute. The prior release documents' blanket exclusion of the WM narrative reader must therefore be revised; this is a missing engineering capability, not an owner permission question.

Read-only comparison: installed base lead `dedac162`, preserved `feat/wm-narrative` HEAD `4396c801`, `v1/ordinary-notes` recovered HEAD `d346f7c0`, `v1/review-guards` HEAD `2a67a606`, and prepared `release/v1` HEAD `30a9b177`. These are observed local refs, not proof of installation or current remote CI.

## Already ported shared repairs

`v1/review-guards` contains the narrative branch's required shared repairs, plus its subsequent refutation repairs:

- `core/views.py`: prevent regeneration over clinician decisions; explicit clear/reset path remains required.
- `core/views.py`: retain clinician-selected statement wording and sources through an employee save, invalidate review for the changed revision, and disclose a replaced wording.
- `core/views.py`: finalized records display their recorded review instead of reassessing them as the current viewer.
- `core/wm_review.py`: retain a literal ampersand rather than silently rewriting clinical text to “and”.

These are required correction/finalization/export repairs. They should be integrated based on their own current evidence, not by merging all of PR #1287 merely to acquire them.

## Required WM ordinary-note path remains missing

Generic v3 generation applies only to v3 locators. Qualified WM mappings use `sdt_id` and measurement/table locators and are explicitly routed separately. Thus improvements to v3 ordinary notes do not qualify WM narrative.

The preserved branch's necessary path comprises `core/wm_narrative.py`, its generation contract and reservation/request attribution, `jobs.py` statement proposals/adoption, source-sentence review/save/finalization in `views.py` and `wm_review.py`, and the matching `documents/sdk_word/Adapter/WmAdapter.cs` evidence and source checks. The C# adapter and Python proof digest must move together; a Python-only port is incomplete. The branch includes side, row, units, corrections, consent/assertion and conflicting-label protections with its retained offline evidence. They are interdependent clinical-path changes requiring review of the final selected diff.

The generic complete-sentence path cannot simply replace this: WM choices and measurements must remain bound to their original controls and rows, and prewritten statements require their own source or reviewed-answer evidence. Keeping the feature flag off does not prove shared changes safe, and keeping WM labelled-only does not fulfill the current promise.

## Shared performance repairs to account for

PR #1287 additionally guards expensive negative-heading searches with a colon precondition in `generation.py` and replaces quadratic colon-prefix scans in `wm_review.source_units` with the cached `_colon_labels` reader. Neither repair is present in recovered `v1/ordinary-notes` generation or `v1/review-guards` review. These should be evaluated/ported with their existing finite cost/identity probes during WM integration. No new performance campaign is needed.

## Integration requirements

1. Preserve branch and all first-pass evidence; select the necessary WM path, not the campaign tooling or an obsolete activation.
2. Adapt its Anthropic request, response blocks, limits/reservations and usage settlement to the separately prepared Sonnet 5 provider profile. Existing Sonnet 4.6 response fixtures are offline regression evidence only.
3. Keep feature-gated WM fixtures and native control/export checks meaningful on the final adapter digest, test review/finalization and statement proposals through the worker, and refute the finished combined diff.
4. Do not rerun Stage 1 or spend its consumed/model-specific authority. Necessary exact-model live verification remains subject to reconciled eligible authorization.

No WM branch edits, merge, push, activation or provider calls were performed by this recovery stream.
