# Notes and reviewed voice repair, Sol continuation 20261002

**REFUTED CANDIDATES — DO NOT INTEGRATE AS QUALIFIED.** Independent security refutation
after the small-batch measurements found two unsafe reviewed-context releases:
“Takes warfarin 5 mg daily. Only her father does.” and “Takes warfarin 5 mg daily.
Not today.” for today's medication question. First failures are retained; repair and
a fresh independent finished-diff refutation are required. The 45-case numbers below
remain their original measured result and do not claim these two extra cases passed.

The first hold-only dependency repair is also **unqualified**. Its affected 181 tests
passed in 218.776 seconds and the exposed 60 diagnostic vectors measured 58 correct,
zero unsafe releases and two unnecessary parser holds, versus 49 correct, nine unsafe
and two holds under the original172 behavior. Fresh independent finished-source
refutation then found two additional unsafe releases through final governance:
“Takes warfarin 5 mg daily. Not since Monday.” for current medications, and
“Takes warfarin 5 mg daily. Only her father takes warfarin.” for medications.
These original failures remain retained in security/refute-notes-repaired-governance-1.*.
The 60-vector result does not include these extra failures or qualify the feature.
`repair-affected-01.log`, `qualification-repair.py/.log`, `refutation-local-before.log`
and `repeated-ellipsis-before.log` retain the first repair's exact measurements.

The second repair is also retained as **unqualified**. Its 18 focused controls
passed in 13.871 seconds; 68 exposed diagnostic vectors measured 66 correct,
zero unsafe releases and two unnecessary parser holds, versus 61 correct,
five unsafe and two holds under1144. This incorporates all **three** supported
outputs in the first repair's raw refutation JSON (“Not on Fridays” was omitted
from the initial two-finding message), plus cross-predicate cough and known
nonexclusive activity controls. Fresh finished-source refutation then demonstrated
“Takes warfarin 5 mg daily. Her father is the sole person taking warfarin.”
still incorrectly supported the medication. This separate failure is retained in
`root-confirm-notes-refutation-3.json/.py`; the 68 vectors did not include it.
The source hashes at that measurement were source_scope23a285fa and
generation77e123ba. Its exact source and first failures remain preserved; no
live campaign or application activation was authorized by these partial results.

Private, synthetic-only component work on `fix/v1-sol-notes-voice-20261002`, based on
`d49ece788c058c9e733e895910a81c8aad94c6a3`. Sonnet 5.5 stays the application model;
ordinary field relations stay contract v4. No provider requests were made by this worker.
This report does not qualify the broad Word corpus or a human microphone.

## Existing live evidence recovered, without a retry

Original campaign 5 evidence remains at
`/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261002-3/evidence/`.
The actual requests used `claude-sonnet-5-5`, `thinking: between_tools`: plain
requests capped at 8,000 output tokens; v4 relations at 20,000. All 28 note responses
returned that model with `end_turn`. Fourteen cases per route supplied 76 field outcomes.

| Original route | Correct supported | Unnecessarily held | Correctly held/missing | Unadjudicated | Unsafe observed |
|---|---:|---:|---:|---:|---:|
| Plain | 6 | 29 | 40 | 1 | 0 |
| Relations v4 | 27 | 9 | 40 | 0 | 0 |

**Denominator correction, not a new baseline:** the earlier report and handoff say
27/35 reference answers. Those original claims remain retained. The frozen
`sonnet5-campaign/diagnostics/notes/cases.json` contains **36** supported expectations;
the original 14-case live classifications also declare 36 supported, 29 missing and
11 held outcomes per route. Thus 27 correct plus 9 over-held equals 36. The plain
unadjudicated outcome is N08/v3_2. Do not present 76 as a reference-answer denominator,
or silently replace the historical 35 claim. Exact file hashes and profiles are recorded
in `notes-voice/original-counts.json` and `original-profiles.json` below.

A replay of all 14 preserved relations responses on this semantic repair changed
**0/76** outputs. It sent no requests and is supplemental reuse of exposed evidence.
The doctor's Sonnet 5.5 configuration with the relations switch unset already selects
v4 by default; the new reviewed-context route is exercised through that actual admission.

## Delivered behavior

A structurally complete transition to a named body position no longer ends unrelated
medication claims. A positively typed medication transition with an elided source still
holds medication and actual treatment dependencies, while an independently supported
patient symptom can remain useful. Unknown transitions, conjunctions and elided stops
keep their prior protection. No medication or release keyword list was expanded.

Named source/target interpretation remains the existing `_superseded` contract:
“switched from warfarin to apixaban” ends the source; a separately explicit, current
patient claim for apixaban can remain supported. Historical, hypothetical, family,
withheld, held and contradictory target claims stay held. The previously unsafe
“Haematology reviewed and stopped” and “INR was checked and stopped” controls stay held.

Transcript review now offers a separate, unchecked clinician confirmation of the default
patient subject. It supplies the subject only for qualified subjectless statements;
explicit other people, personal pronouns, modal/imperative claims, medication cessation,
timing, sides and correction/contradiction guards retain their meaning. Every supported
answer retains the original source text and offsets.

`TranscriptReview` (0036, after Word's 0035) retains original-result/raw-text hashes,
the clinician's exact edited transcript, actor, source revision and bounded span separately.
It is append-only in Python and PostgreSQL. The SQL guard locks encounter then preservation,
requires the exact succeeded same-encounter transcription and authorized actor, and checks
the current source revision and exact source span before retaining a review.

Admission uses the server's current signed review, rather than a supplied quote token.
Single requests and immutable whole-form plans carry the context and account for its
request bytes. Any changed source edit invalidates it, including edit-and-revert;
unchanged saves and field review do not. A clinician can re-review the retained paid
transcript after an edit with explicit confirmation and replacement, without a new
transcription or a new transcription charge. Existing audio/provider output stay untouched.

Optional role suggestions now have a conservative complete-response byte bound plus
thinking headroom. Rows that would exceed the cap remain unasked, preserving the ordinary
request byte-for-byte. Incomplete structured output still refuses adoption and remains
subject to the existing platform-failure cost/customer-settlement distinction.
**Role suggestions remain off; signing and attestations remain human-owned.**

## Verification and remaining limits

| Evidence | Result | Scope |
|---|---|---|
| Original supersession regression portion of focused-01 | Passed | 66 prior tests; unrelated new tests in that run failed and are retained |
| Focused-03 | 19 tests passed, 17.168 seconds | Exact original voice controls, review lifecycle, narrow transition scope, output cap, actual mocked-provider HTTP-to-Word export |
| Affected-01 | 210 tests passed, 380.489 seconds | Input, relations/contract/workflow, whole-form batches, role invariants and new semantic/lifecycle cases |
| Final source-span guard | 14 tests passed, 17.247 seconds | Final0036 plus SQL counterexamples, lifecycle and voice export |
| Preserved campaign replay | 14 cases / 76 fields, 0 changes | Original first responses only, no new calls |
| Deterministic interpretation vectors | 43/45 correct, 0 unsafe releases, 2 unnecessary holds | Simulated model picks; 16 useful expectations, 29 required holds |

The interpretation vectors previously measured 37/45 correct, zero unsafe releases and
eight unnecessary holds. Six useful releases are three positional changes, one unrelated
symptom beside a typed medication transition, and two explicitly reviewed subjectless
current statements. Remaining parser holds are “Reports left ankle pain” and “Mild swelling
over the left ankle”; they were retained rather than semantically guessed around.

The full HTTP test sends synthetic audio through a mocked Deepgram result, clinician review,
default Sonnet 5.5 admission and worker, field review, finalization and genuine Word export:
**2/2** subjectless statements (“Takes warfarin 5 mg daily” and “Reports cough”) are supported
and exported. Transcription and generation each have one usage row. This is offline workflow
evidence, not a new live transcription-accuracy or microphone result.

The exact original campaign5/031 raw transcript, 11-field mapping and first model response
are copied with provenance hashes into `core/tests/voice_first_pass_controls.json`.
Both original wrong selections remain held with and without patient confirmation: current
medications from the plan's “No medication is prescribed”, and HPI containing the superseded
pain score beside its correction without a contrary relation. Original transcription mistakes
remain in that fixture. New clinician edits must never be scored as original audio accuracy.

Focused-01 and focused-02 failed outputs remain retained: SQL variable ambiguity was fixed;
test contract/profile and compiled-wire assumptions were corrected; unresolved nominal/left
parser holds remain failures; the initial simplified medication control was replaced by the
actual full original first response after showing that the standalone phrase differed.

## UI reference lock

Applied `.agents/skills/refero-design/SKILL.md` using the existing QuillMD transcript-review
surface and source-edit warnings in `templates/encounter_input.html`, field-review checkboxes
in `encounter_detail.html`, and bundled `references/craft-details.md` accessibility/copy rules.
The existing sober clinical form is the dominant reference. The new subject confirmation is
separate from transcript review and every field decision, has explanatory `aria-describedby`,
is never prechecked, and exposes retained original text during re-review. No new visual system
or implication that confirming a subject accepts all answers was introduced.

## Integration and continuation

The measured component tree contains base d49ece78, this owned repair and the temporary
byte-identical migration0035 from qualified Word commit
`6e1653d0b6291fd884179f9df7be7048db27b0e2`, SHA256
`627bb0430cfa942a92e38f97609b3dd2d80212683f1e0a6ff48428f97cb697bf`.
That temporary dependency is excluded from this worker's commit. Word's import-manifest
model/views implementation is not part of this measured component tree. The coordinated
union needs its own exact-commit gates. Finished clinical semantics require independent REFUTE.

The security worker owns TranscriptReview disposition/catalog/retention/restore integrity and
fail-closed immutable-review redaction refusal in0037; no destructive redaction workaround
was added here. Lead owns union, CI, fresh distinct live identities under the existing standing
authority, private demonstration activation and retained evidence. Human microphone acceptance
and native Word inspection remain distinct external results.

Protected evidence root:
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/notes-voice/`.
Retain `focused-01.log`, `focused-02.log`, `focused-03.log`, `affected-01.log`,
`guard-final.log`, `qualification.log`, `qualification.py`, `existing-replay.log`,
`replay-existing.py`, `original-counts.json`, `original-profiles.json` and probes.
The scratch/linked environment contains no provider credentials. Disposable caches require
lead's verified cleanup manifest; no shared environment or retained evidence was removed.
