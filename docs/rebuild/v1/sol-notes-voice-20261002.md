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

The third repair is likewise **unqualified**, preserved after 19 focused tests
passed in14.261 seconds. The expanded **76 exposed diagnostic selections**
(separate from the original76 live field outcomes) measured74 correct, zero
demonstrated unsafe releases, zero unresolved dependency releases and two parser
holds; its exact21f2853f baseline measured69 correct, two unsafe, two unresolved
dependency releases and three unnecessary holds. “No longer routine” is an
ambiguous restriction requiring review, not evidence that medication stopped.
Fresh independent refutation then demonstrated three more unsafe full-governance
releases outside that set: “No longer a daily medication”, “Her father is the sole
warfarin user”, and “Her father is the only patient on warfarin”. Those original
failures remain in security/refute-notes-repaired-governance-4.* and
root-confirm-notes-refutation-5.json. Source_scope3f3d3695 is preserved exactly;
the diagnostic denominator was not expanded retrospectively to erase the failures.

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

### Fourth source snapshot — refuted, not eligible for live use

`source_scope.py` SHA256 `8b83a04c7e57778ca5896c51827fd4c2f5c304b6b60a39080a6dfc529878e3a8` passed 20 local semantic tests in 15.856s (`refutation-4-local-after-2.log`); its first harness expectation failure remains in `refutation-4-local-after.log`. Independent security refutation then demonstrated a supported current medication claim after `No longer the daily medication`, and unnecessary holds for three negative exclusive family clauses. Exact whole-validator/governance and parser evidence is retained under the sibling security scratch as `refute-notes-repaired-governance-5.json` and `refute-notes-repaired-parser-3.json`. This snapshot remains unqualified. A successful local suite does not erase these outcomes.

Hypothetical new reviewed-context replay found five completed retained voice generations across three campaigns, rather than the four reported at handoff. The two current v4 outputs still adopt zero fields with confirmation. Two older plain outputs do not admit v4 context and one old v3 wire refuses v4 parsing. No original transcript or model output was changed, and no new request, actual review or export qualification occurred. `replay-voice-context-4.log` retains the corrected replay; earlier harness failures and the erroneously confirmed baseline in replay3 remain explicitly diagnostic.

### Fifth source snapshot — unnecessary holds remain

Source scope SHA256 `169f2144383d66a1a8818c731db6b03d8ca837cbb0ac35b9c0c46ea570946f5d` corrected the definite-article release and three negative-exclusive holds; 14 focused PatientDefault tests passed in 12.267s. Independent security evidence `refute-notes-repaired-governance-7.json` then demonstrated two fresh unnecessary holds: an exclusive other person **without** warfarin and an exclusive other person's **used to take** warfarin both held the patient's supported current medication claim. The first result is retained. `No longer my daily medication` was also reported as an ambiguous speaker/dependency risk, not certified as a stopped-patient-medication failure. This snapshot remains unqualified.

### Sixth source candidate — finished diff awaiting independent refutation

The fifth source's two demonstrated unnecessary holds now distinguish the exclusive actor's negative possession and historical action from the patient's current positive claim. Nominal temporal modifiers attach to the affected clinical class without an article whitelist. The previously refuted candidates and first failed outputs above remain unqualified historical evidence.

Explicit transcript review now supplies only an actor for positively parsed subjectless clinical nominal statements, such as `No fever` and `Examination mild swelling over the left lateral ankle`. It introduces no clinical predicate, words, status, dose or source offsets. Subjectless medication nouns remain held. Unknown actors, uncertainty, time, stoppage, modal statements, bare headings and inherited other-person context retain their guards. Exact named clinical assertions can establish their own unique mapped destination, while competing field choices still hold.

Retained voice replay is **hypothetical new clinician context review**, not a changed first-pass transcription or generation score: the unchanged current-v4 SOAP first response now yields **1/9 ordinary requested answers** (Examination), or 1/11 whole-form fields including two human-owned signoff areas. Its raw transcription and all first-response hashes are preserved. Both previously correctly blocked choices remain held. The current-v4 colonoscopy response still yields zero useful answers against its SOAP mapping; two old plain responses cannot admit v4 context and one old v3 relation wire refuses current parsing. Five completed old generations were recovered, rather than the four reported in the handoff. No new provider request, actual new review or export pass is inferred from this replay.

The real blocker was traced through signed relations and final governance. The literal reader combined a parsed anatomical side with a noun as if it were a reversing prefix, treated a following spoken category or exact printed question heading as an answer to the preceding statement, and conflated explicit opposite anatomical sides. Each narrow relationship is now handled without granting a heading an actor or changing its forward source governance. Unknown or mixed side scope still holds. The first attempted shared-side proof recursively acquired a non-reentrant parser lock; its owned pure diagnostic was identity-verified and terminated with rc241. Required bounded source docs are now materialized before taking that lock, and failed reads remain cached.

A new explicit same-side denial counterexample proved a longstanding pinned-parser failure: `The patient reports pain in the left knee. The patient denies left knee pain.` supported the first sentence because deny was misattached as a verbal subject of left/leave. The repair only adds a hold on that malformed denial's positively named clinical topic. A prefixed adjective on the same named clinical noun also remains held without guessing that swollen and swelling mean the same thing. Actual prefix, denial, anatomical and family controls are retained.

An early hypothesis that a note-wide quantity correction floor caused the retained SOAP failure was false: actual correction scope was empty. The unused experimental quantity helper was removed. Its failed probe/expectation logs are retained; no absent correction floor was relaxed. The old pain-correction selection remains a positive safety regression control through the unchanged raw model output.

Measured component checks: **32/32** PatientDefault, LiteralFacts and LiteralSubjects checks passed in 22.937s (`nominal-literal-8.log`). The original **76 exposed deterministic diagnostic selections** retain their denominator: **74 correct, zero unsafe releases, zero unresolved-dependency releases, two unnecessary holds**. Twelve supplemental anatomical/prefix/denial selections measured **11 correct, zero unsafe releases, one unnecessary hold**. The latter is the existing conservative lexical-denial handling of `does not deny`; it remains explicitly unsupported, not silently scored correct. The first failed diagnostic-builder syntax output is preserved beside the corrected `qualification-finished-2.log`. These exposed author diagnostics do not replace independent REFUTE, a live campaign or a held-back acceptance set.

Current evidence is under the protected notes-voice scratch: `replay-voice-context-literal-6.log`, `raw-voice-examination-diagnosis-*.log`, `side-diagnosis-3.log`, `literal-lock-failure.json`, `nominal-patient-*.log`, `nominal-literal-7.log`, `nominal-literal-8.log`, and `qualification-finished-{1,2}.log`. Retain all failed and superseded results. The temporary Word0035 migration and isolated old-ORM fixture compatibility edit remain outside this clinical commit. The root union retains the real Word model/import guard and direct immutable import-manifest copy in its final fixture workflow.
