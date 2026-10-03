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

### Sixth finished source — independently refuted and rejected

Exact commit `6f0f647a3d10227fc7ed9a30698c1877a7fff22f` is **not eligible for integration or live use**. Security and the lead independently reproduced five unsafe supported answers through both relation validation and current final governance: same-side swelling followed by `without swelling`, `absent swelling` or `swelling-free`; same-side pain followed by `without pain`; and exclusive other-person same-side pain. A father's complete negative swelling statement also unnecessarily held the patient's examination. All original inputs, outputs, seventeen component hashes and parser witnesses remain in the protected `security/refute-clinical-6f0f647a.json`, `security/diagnose-clinical-6f0f647a.json` and lead `root-confirm-clinical-6f0f647a.json` records.

The exact sixth affected nine-label suite finished **226/227 passing**, rc1, 287.306 seconds (`affected-final-6f0f647a.log`). Its remaining unnecessary hold was `The patient takes warfarin. Diet: none.`: an independent named label's `none` was incorrectly treated as a topicless restriction. The actual mocked audio-to-review-to-worker-to-field-review-to-finalization-to-HTTP-export workflow passed within that run. These observations do not erase the independent unsafe results.

### Seventh modifier and actor repair — awaiting independent refutation

A directly attached absence modifier or relation now holds only the named clinical claim it affects. The existing clinical vocabulary and actual parser edges bind `without swelling`, `absent swelling`, `swelling-free`, and `free of swelling`, including the pinned parser's nominal argument mis-tagged as a verb. The code does not invent a positive clinical predicate. `Without treating pain` and `no pain relief` do not directly deny pain. Cancelled or ambiguous negation remains held, and contradiction is checked whichever polarity the model selected.

Opposite sides remain independent only where each shared clinical word has its own explicit single side. For the parser's `has a right knee without pain` attachment, the sole anatomical object of that same simple relation can supply its side. Coordinates, extra clauses, unknown anatomy and unqualified sides cannot. A complete single foreign-actor clause can remain independent only when the parser proves its own actor and contains no patient, embedded speaker or unresolved pronoun. Exclusive same-topic attribution is separately enforced, including the anatomical `left` token misread as a perfect predicate.

An independent `Diet: none` no longer becomes a topicless dependency solely from a non-root word. Root-level `None`, negative temporal/nominal modifiers and all earlier stopped, wrong-subject, explicit correction, hypothetical, family, uncertainty and same-side controls retain their guards.

The first seventh local probe failed six expectations; `refutation-7-local-1.log` is retained. After diagnosis, **20/20** checks passed in 25.376 seconds. The finished focused semantic slice, with symmetric contradiction and phrase-locality controls added, passed **21/21** in 26.604 seconds (`refutation-7-local-3.log`). These are exposed author controls, not an independent safety qualification or new provider/audio result. The exact finished component commit must still pass independent REFUTE and its affected suite before integration.

### Seventh finished source — independently refuted and rejected

Exact `3b9e8bf8454f98031155f3098edcd98dce17f05a` passed **229/229** affected nine-label tests in 319.802 seconds, rc0, with its disposable test database destroyed. All nineteen clinical component hashes remained unchanged. This source is nevertheless **unqualified**: lead refutation reproduced `entirely absent swelling`; independent security refutation reproduced `completely absent swelling` and three copular absence statements. Each left the same-side positive examination supported through final governance. Selecting the negative left-ankle statement beside a positive right-ankle statement also produced an unnecessary hold. Security's eighteen controls and lead's thirty-six controls remain separately denominated, with their exact first outputs retained at `security/refute-clinical-3b9e8bf8.json` and `root-refute-clinical-3b9e8bf8.json`.

Original fourteen typed first responses replayed unchanged across **76 classifications**; the historical useful-reference denominator remains **36**, distinct from the reported handoff35. The unchanged five completed voice outputs retain the hypothetical new-review result: current-v4 SOAP **1/9 ordinary fields** useful, or1/11 including signoffs; the other four remain zero or contract-limited. Both old wrong picks remain held. These replays are neither new first-pass audio scores nor actual new review/export qualifications. Exact evidence: `existing-replay-3b9e8bf8.log`, `voice-replay-3b9e8bf8.log` and `qualification-3b9e8bf8.log`.

### Eighth direct and complement repair — finished component checks

The negative operator now binds its own clinical subject, direct argument or adjectival complement, including pinned clinical gerunds mis-tagged as verbal/clausal subjects. It uses the existing negative-operator vocabulary; modifying an operator with an adverb requires no new word exception. A bounded predicate/complement path whose interpretation is unresolved holds only its named clinical topic and dependencies. An unresolved negative relationship cannot itself supply an answer. Sibling clauses, adverbial relations and new explicit subjects or objects do not become that dependency.

A proved single foreign actor remains separate when its own clinical gerund is parsed as an open complement without another subject or person. The actor of a clinical property can also be its explicitly bound foreign possessor; unclear clinical possessive pronouns, patient references and embedded speakers retain the hold. Standard explicit copular `is not absent` does not oppose an existing affirmative claim and supplies no new value. Other malformed or nested cancellations remain unsupported. Source-side proof follows each exact clinical gerund's own phrase, preserving explicit opposite-side statements without inventing a tense, status or body location.

Finished focused checks: **43/43** passed in30.305 seconds, rc0 (`refutation-8-local-5.log`), including the full **19-test** historical owner tab contract. It verifies original SHA,24 fields/28 physical anchors,17 supported answers/seven missing, source offsets, correction, signing/consent blanks and historical mocked-adapter compatibility. The module's adapter test names Sonnet4.6; this is **not** proof of a new live Sonnet5.5 owner result. No D02 send was found among the retained standing campaigns. Lead recovered older owner support evidence explicitly labelled fixture/provider-blocked; the actual browser fixture first3/manual17 result remains separate. Restricted development originals remain excluded from provider requests.

The first eighth probe's opposite-side hold and later explicit-father gerund hold are retained in `refutation-8-local-{1,4}.log`; intermediate41/42 green checks remain supporting evidence. Read-only parser witnesses and their first harness import failure remain in `diagnose-entirely-3b9e8bf8*`, `diagnose-predicative-3b9e8bf8*`, `diagnose-negative-complement-8*` and `diagnose-direct-operators-8*`. No original failure was rewritten. Independent REFUTE and the exact affected suite remain required before integration or provider qualification.

### Eighth source independently refuted — retained, unqualified

Exact `99262258ee6e316f6949258ead43e402ad3ac2d6` passed **232/232** affected nine-label tests in293.219 seconds, rc0 (`affected-final-99262258.log`); its disposable database was destroyed. Original fourteen typed responses replayed unchanged across76 classifications; five old voice outputs retained the hypothetical new-review1/9 ordinary-v4-SOAP result and both wrong picks held. These results do not qualify the source.

Independent security's44 probes plus4 separate attribution/baseline controls demonstrated **five unsafe supported outputs**: the positive left swelling claim survived an absence noun, a direct negative complement and a reported open negative complement; the negative left swelling claim survived two exclusive other-person negative claims. It also demonstrated one unnecessary-hold mechanism, the exclusive father's negative medication possession beside the patient's positive medication use. The lead's separate48 controls demonstrated an unnecessary hold from an explicitly foreign anatomical possessor through a passive negative complement. All original raw results and nineteen exact component hashes remain protected in `security/refute-clinical-99262258{,-controls}.json` and `root-refute-clinical-99262258.json`. No malformed-double-negative hold or standalone nominal baseline hold was relabelled as a demonstrated regression.

### Ninth local negative-relation and exclusive-polarity repair — pending independent qualification

The explicit noun nominalization `absence` carries the existing `absent` operator only through its actual grammatical argument. A positively typed clinical gerund can own its bounded open negative complement even when the pinned parser attaches the gerund as an open complement or noun clause. This retains the named clinical claim for review; it supplies no new clinical assertion. Its open copula has no separate actor or object, so the same negative complement's explicit anatomy can prove a distinct side. Other embedded clauses remain excluded.

Exclusive attribution now considers the actual predicate's negative object determiner and lexical absence, rather than only its own syntactic `not`. An exclusive same-topic negative clinical property can retract a nominal negative patient claim; an exclusive father's negative possession cannot retract the patient's positive medication use. The existing time, side, actor, nonexclusive and different-topic controls remain binding. An explicitly possessed anatomical object can prove the sole foreign actor of a clinical subject through a passive open complement. Unresolved pronouns, patient references and mixed subjects remain held.

Focused checks passed **43/43** in33.577 seconds, rc0 (`refutation-9-local-1.log`), including the historical mocked owner regression. Light probes retained the first unrecorded-exit instrumentation and its exact output (`negative-scope-9-1.log`), followed by a measured rc0 probe (`negative-scope-9-2.log`), and parser witnesses (`diagnose-foreign-complement-9.log`). This is exposed diagnostic evidence, not an independent safety pass, new live audio result or native Word inspection. The finished source still requires independent REFUTE and its affected suite before clinical integration or provider use.
