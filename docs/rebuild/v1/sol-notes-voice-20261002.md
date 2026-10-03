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

### Ninth finished source — three definite failures, one withdrawn finding

Exact `8a030d4c8f0027dc962554b8d8df0d4a5207d21d` passed **246/246** explicitly enumerated affected tests in205.143 seconds, rc0 (`affected-final-8a030d4c.log`), with database destruction. Original14 typed outputs remained unchanged across76 classifications. Exposed diagnostics retained74/76 correct, zero unsafe releases and two unnecessary holds; the separate12 supplemental controls retained11 correct, zero unsafe releases and one unnecessary hold. Five original voice outputs remained unchanged, with hypothetical new review1/9 ordinary-v4-SOAP useful and both old wrong picks held. None of these denominators substitutes for independent qualification.

Independent security's60 frozen whole-governance probes demonstrated **three definite unsafe releases**: positive swelling survived `no evidence of swelling` and a father's denial of the **explicit patient's** swelling; nominal negative swelling survived exclusive foreign possession of an absence of that same swelling. The initial raw instrument flagged four. After the lead challenged the medication interpretation, security **withdrew** `The patient takes no warfarin` versus `Only her father lacks warfarin` as an accuracy failure: possession and taking are distinct claims, and the patient can possess medication without taking it. Raw four flags remain immutable alongside the dated correction; no medication guard was widened for that withdrawn assertion. Security retained `refute-clinical-8a030d4c.json` and its exact19-source manifest. This source remains unqualified despite green affected tests and the lead's separate48+16 controls.

### Tenth negative argument and property polarity repair — pending independent qualification

A negated unknown nominal container's grammatical OF argument retains only its named clinical topic for review (`no evidence of swelling`). It establishes no absence or diagnosis. A negative predicate's patient content clause likewise remains relevant even when the outer speaker is another person. A positively foreign content-clause subject is distinct; an unresolved subject supplies no independent-claim proof. Matching arguments can use their own nearest, sole explicit patient subject for anatomical side proof, without letting a subject elsewhere qualify them.

Exclusive attribution's polarity now follows the affected clinical property rather than an enclosing affirmative light verb. `Has an absence of swelling` has an affirmative `has` but a negative swelling relation. An unresolved negative relation cannot supply polarity or prove an exclusive same-topic assertion independent. This does not equate medication possession with taking, broaden signing eligibility or infer a positive clinical value.

Focused PatientDefault and historical mocked owner checks passed **44/44** in33.673 seconds, rc0 (`refutation-10-local-2.log`). The first30.769-second run's opposite-side nested patient hold is retained in `refutation-10-local-1.log`; parser witnesses remain in `diagnose-refutation-8a030d4c.log`. This finished source still requires fresh independent REFUTE and the affected note-floor/workflow checks before clinical integration or live calls.

### Tenth source — nested dependency omission and positional false hold retained

Frozen `fff30c50f04c8f440895f3910e7931f1f8977913` passed the directly affected **28/28** note-floor/HTTP-worker workflow supplement in98.635 seconds, rc0 (`notes-workflow-fff30c50.log`), with database destruction. The lead's48+16 separate whole-governance controls passed with nineteen unchanged component hashes. Security's pinned-parser84 probes plus8 separate controls nevertheless found a same-topic dependency omission through `absence → of evidence → of swelling` and a definite unnecessary medication hold from `switched from prone to supine positioning`. Exact first outputs, hashes and parser witnesses remain protected in `security/refute-clinical-fff30c50-sharedvenv.json` and its controls record. The initial wrong-venv instrumentation failure remains separate from those measured results. This source was rejected; no provider calls or clinical activation followed.

### Eleventh bound nominal relation and positional event repair — pending independent qualification

The negative argument reader walks the entire same grammatical OF chain, bounded by the source document's nodes. An unknown intermediate nominal relation does not establish independence from its explicit negative container. A known separate clinical/treatment topic, another person or a non-OF relation stops that path. The result remains an unresolved review dependency, not an invented absence or diagnosis.

A complete positional transition can bind its source and target when the target is the explicit position noun or its noun nominalization `positioning`, and the source is a grammatical adjective or a complete position noun. No orientation names are added to a release list. Named medication sources, uncertain source adjectives, arbitrary noun/proper-name sources, extra actions and unrelated clauses cannot establish this positional interpretation. Named medication replacements keep their existing separate source, target, time and explicit-current-claim requirements. The new scope does not supply an answer or positive medication status.

Focused checks passed **53/53** in39.414 seconds, rc0 (`refutation-11-local-2.log`), covering PatientDefault, medication transition/source/target/time/stop controls and the historical mocked owner contract. The first40.235-second probe is retained: two injected-mutation assertions incorrectly assumed already-independent positional forms entered a bare-event floor; the third tested an unspecified adjective as though it were a named medication. Only the independently demonstrated shape now receives that mutation assertion. An explicitly unknown medication remains a held negative control. Parser evidence is retained in `diagnose-positional-fff30c50.log`. This finished source still requires independent REFUTE and the exact final integration checks before live use.

### Eleventh source — unresolved medication contract and foreign-position hold retained

Frozen `9dc386183a0c17b76c90c180ffb0de325936b1b2` remains unqualified. Independent lead and security controls proved that a lowercase generic unknown medication source bypassed the bare-event floor and released a medication claim without resolving that source dependency. This is an **unresolved dependency contract failure**, not proof that the explicitly named warfarin was the unknown discontinued drug. Security's original automatic unsafe flag remains retained with the lead's classification correction. A father's complete positional transition also unnecessarily held the patient's medication, with both subjectless-confirmed and explicit-patient standalone baselines supported. Exact retained evidence is `security/refute-clinical-9dc38618-root-controls.json` and `root-refute-clinical-9dc38618-fresh.json`.

The eleventh component manifest inherited stale `focused_result` metadata (43 tests/30.305s) from the eighth manifest. Its exact source hashes were correct; the actual eleventh log is53 tests/39.414s, rc0. This correction does not change the original manifest or the independent failures. The next manifest records its own actual result.

### Twelfth source argument and question-reference repair — pending independent refutation

A positively parsed old medication argument without a bound medication identity retains the affected medication claim and its actual dependencies for review. A positional target supplies no proof that this old source was a position. Known source names retain their original cessation keys; a separate complete current claim of the exactly named replacement remains distinct from the unidentified old medication. Extra target qualifiers cannot provide that narrow independence proof. Explicit foreign, negated and modal future events add no completed patient-change dependency here; existing named-source, stopped, historical, actor and uncertainty guards remain binding.

A positional event's grammatical argument remains a position when its actor is an explicit family member. That event does not modify the patient's medication. No orientation words or medication classes were added to a release list, and no foreign medication value gains a patient actor.

The first56-check probe passed50 tests and failed six Medications controls, rc1/47.001s (`refutation-12-local-1.log`). Parser and signed-record witnesses proved a separate literal-reference guard was coupling every sentence merely because a generic medication noun appeared as an old treatment argument. A supplemental Current medications probe passed56/56 in41.547s; this label substitution did **not** qualify the actual Medications workflow. The original failures and event-only source snapshot remain preserved in `twelfth-event-only-source/manifest.json` and `diagnose-transition-12{-2}.log`.

The actual Medications guard now distinguishes that exact generic source token's grammatical argument from a printed-question reference. Headings, section names, targets, mixed references, invisible alternate readings and unparsed tokens retain structural coupling. Actor, polarity, time, source identity and clinical dependencies are still checked separately. Both Medications and Current medications now exercise the original controls, named old/replacement values, current versus historical/hypothetical/foreign replacement claims, unrelated cough versus cough-with-medication dependencies, and question-reference counterexamples.

Measured affected checks: **88/88** passed in70.128s, rc0 (`refutation-12-local-5.log`). This includes PatientDefault, transition controls, the19-test historical mocked owner contract, and ordinary-context regressions with actual fixture HTTP workflows. The disposable test database was destroyed. Earlier56/56 (50.022s) and58/58 (51.217s) probes are retained separately. No provider requests or new audio accuracy result occurred. This finished diff must still pass independent REFUTE and the coordinated integration gates before live use.

### Twelfth finished source — mixed-actor cessation failures retained

Frozen `acdd1f2f06e9776f7993098d7473189f5a1bc53c` is unqualified. Security's133 whole-governance probes and21 separate narrow/lead controls demonstrated that a father's positional clause could conceal the explicit patient's stopped, withheld or replaced warfarin in the same source unit, including semicolon separation. The unchanged warfarin answer remained supported through validation, current governance and finalization decisions for both Medications and Current medications. The opposite case, the patient's ended **apixaban**, unnecessarily held the independent warfarin claim. Exact20 component hashes, first outputs and per-predicate parser witnesses remain protected in `security/refute-clinical-acdd1f2f-root-controls.json` and the primary evidence. The88 green author checks did not qualify this source.

The unchanged five original voice outputs replayed under explicitly hypothetical new patient-context review yielded0/0/0/1/0 adopted fields (`replay-voice-context-acdd1f2f.log`, rc0). Current-v4 SOAP retains1/9 ordinary fields, or1/11 whole-form fields including signoffs, and both old incorrect picks remain held. This is unchanged raw-response diagnostic replay, not a new transcription, provider request or actual reviewed voice-to-export qualification.

### Thirteenth per-clause actor and ended-argument repair — pending independent refutation

Each finite source predicate now retains its own explicit actor and ended argument. A foreign main clause cannot discard a contained explicit patient cessation. Coordinated verbs have separate ownership; coordinated medication objects remain together. A patient's explicitly foreign-owned medication does not become the patient's own ended medication. Unknown or elided actors cannot establish independence. The original named-medication, uncertainty, chronology, wrong-subject and medication-source/replacement protections remain binding.

A mixed positional unit can narrow its formerly global bare-event floor only when every grammatical clause proves a position, a separately supported clinical topic, or a bounded actor-owned ending. A positively typed medication in the pinned parser's object-predicate slot stays a named ended argument, so ended apixaban does not also end warfarin. Unidentified medication sources retain their actual medication dependencies; source and target metadata belong to the exact predicate, including multiple foreign and patient events in one unit. No new positive clinical assertion, generic medication status or actor is invented.

The first59-check run failed232 repeated harness errors from passing a token list to a helper requiring a source span (`refutation-13-local-1.log`,28.777s). The original failure remains retained; source spans now require contiguous clause ownership. A narrow mixed-actor probe then demonstrated four unnecessary holds from apixaban's object-predicate parse (`refutation-13-narrow-1.log`,8.971s), followed by the same controls passing9.984s after the bounded argument repair. A59-check run retained one replacement-target false hold (`refutation-13-local-2.log`,61.048s), corrected by per-predicate source/target binding; its two affected controls passed11.734s.

The subsequent60-check probe passed59 and failed one author's overstrict policy expectation (`refutation-13-local-3.log`,57.511s): `stopped an unidentified substance` did not prove a medication claim or an explicit warfarin contradiction. The lead agreed that an unidentified substance could be non-medication. That first policy diagnostic and exact preceding source are preserved in `thirteenth-policy-diagnostic-source/manifest.json`; withdrawing that unsupported expectation does not reclassify any earlier demonstrated medication failure. Actual known-medication, mixed-actor cessation and generic medication-source controls remain in the final slice.

Finished focused checks passed **60/60** in63.158s, rc0 (`refutation-13-local-4.log`), covering PatientDefault, transition controls and the19-test historical mocked owner contract. These are exposed author controls with no provider or database requests. The prior actual fixture HTTP workflow evidence remains separately scoped. The exact finished20-component manifest and commit still require independent REFUTE and coordinated integration checks before live use.

### Thirteenth source — nested patient cessation and carrier false holds retained

Frozen `fa3de6f365840fbf7ed8a6df0ed4acbc83f3db5d` remains unqualified. Lead80 controls found two unnecessary holds from a patient's report of a father's positional change. Security30 controls then demonstrated that a father switching position and reporting that **the patient stopped warfarin** could conceal the patient's cessation. The lead independently reproduced stopped and withheld warfarin, and unnecessary holds for another ended medication, a confirmed foreign positional change and a reported historical foreign positional change. Both Medications labels were exercised. These first results and exact20 component hashes are retained in `root-refute-clinical-fa3de6f3-fresh.json`, `root-refute-clinical-fa3de6f3-embedded.json`, and `security/refute-clinical-fa3de6f3.json` with the security parser witness. The original60-check author scope did not cover that nested parser shape. Security withdrew a resumed-today raw flag as a newly demonstrated false hold after its standalone baseline also held; the original outputs and correction remain separate.

The pinned parser reads the embedded report as a noun conjoined to positioning, and the patient's stopped/withheld predicate as an ACL under that noun. The previous predicate filter excluded that real separately owned assertion. Read-only first witnesses remain in `diagnose-carrier-fa3de6f3.log` and `diagnose-nested-fa3de6f3.log`. Original voice raw responses retained the same hypothetical new-context1/9 ordinary-v4 result and both wrong picks held; no provider request was made.

### Fourteenth complete clause ownership and bounded attribution — pending independent qualification

Every verbal ACL or relative branch removed from an outer clause is now inspected separately, including a passive or unresolved actor. An explicitly patient-owned ending remains relevant through its own named argument. An unresolved actor cannot establish independence from that same ended medication: the affected claim is held without assigning the actor to the patient. A positively bounded different named medication does not end the selected medication. Generic positively medication arguments retain medication dependencies; an unidentified substance does not itself prove that class.

A finite content clause retains its own subject and argument rather than adopting its outer speaker. A bounded attribution carrier owns no clinical argument or independent modifier and cannot use negation, intention or an ending operator to prove independence. The pinned parser's nominal reporting carrier is accepted only through its existing light-word classification and explicit finite content-clause structure. No reporting-verb or orientation-name release list was added. A grammatical adjectival FROM source can own its TO position target even when that preposition is nested under FROM. A proved foreign clause can remain independent only while every contained clause is accounted for. Unknown actors and unknown arguments supply no positive value.

The first two-method probe retained eight failed subcases in10.327s (`refutation-14-narrow-1.log`): four unresolved same-drug actors and four different-drug false holds. The same two methods passed11.141s after the bounded ownership repair. Adding the unresolved-actor/different-named-drug positive retained four additional false holds in10.971s (`refutation-14-narrow-3.log`); exact parser witnesses remain in `diagnose-unknown-child-14.log`. The final expanded two methods passed11.893s. All original results remain unchanged.

Finished exposed controls passed **62/62** in69.817s, rc0 (`refutation-14-local-1.log`): PatientDefault, transition controls and the19-test historical mocked owner contract. They include both source baselines and both medication labels, nested stopped/withheld/replaced values, unresolved same versus different drugs, cancellation/future, explicit foreign ownership, passive endings, and complete/historical foreign positional complements. These are offline checks with no database or provider requests. Independent finished-diff REFUTE and coordinated integration gates remain required before clinical use.

During the clinical review wait, independent Word refutation used a protected exact `ec23c3b1` documents-only archive:29 pure cases/5.315s/rc0 and four source-role controls. Four complete first-person attestations mapped as ordinary unprotected checkbox/text destinations and exported successfully; the role reader returned no roles or violations. This is source/writer evidence, not a demonstrated live HTTP generation result. The exact inputs, source hashes, direct exports and limits are preserved in `notes-voice/refute-word-ec23/report.md`, `result.json` and `roles.json`. The first mutable-tree HEAD refusal was retained. The lead must independently reproduce these Word findings before repair; no Word source was changed by this agent.

### Fourteenth source — nested negative use and unrelated clause holds retained

Frozen `5748175ad2b0dccfa364eb0257cc25e0540d8764` is unqualified. Security57 controls found two concrete unsafe nested patient-use denials: a father denies that the patient takes warfarin, and a foreign position change contains an explicit patient does-not-take-warfarin clause. The lead independently reproduced both for Medications and Current medications; direct patient denial, foreign or different-drug denial, negated STOP and the two original wrong voice picks remained held/released appropriately. Exact first outputs and twenty component hashes remain in `security/refute-clinical-5748175a{,-witness}.json` and `root-verified-clinical-5748175a-denials.json`. Security also retained five unrelated-context holds. The lead104 controls confirmed six unnecessary holds (two labels each) for explicit foreign positional action with an inherited family STOP/REPLACE predicate or an outer patient report. The old62 green author checks did not qualify this source.

### Fifteenth intermediate — bounded denial and grammatical family ownership

The new hold-only opposition reader compares each actual patient predicate with its own head, named argument, polarity and tense, including an explicit patient assertion beneath a canonical denial by a foreign speaker. Taking and possession remain different predicates. This adds a source review dependency without assigning a patient actor or supplying an answer.

An explicitly named family member's complete positional predicate can own its direct subjectless coordinated action when there is no separate patient or unresolved subject. It cannot infer a clinician/service's role, adopt an unknown actor, erase an embedded patient assertion, or apply family ownership beyond that exact grammatical parent.

Two narrow methods passed in6.742s, then **64/64** semantic/transition/historical mocked owner controls passed in73.722s, actual exit0 (`refutation-15-local-1.log`). These are exposed intermediate offline checks, not qualification. Exact intermediate source copies are retained in `fifteenth-intermediate-source/manifest.json`.

Read-only diagnosis of four additional holds is retained in `diagnose-additional-15.log`: the pinned parser attaches the passive medication to positioning while leaving withheld without a theme; a separate knee-pain denial prevents the mixed-clause proof; and an actual modal patient STOP has no relation cessation cause but retains the old note-wide lexical might scope. The latter remains an explicit unsupported scope interpretation until a coherent shared proof can be demonstrated. No tomorrow exception or scope evidence deletion is authorized by these results. Product edits and full/DB suites paused at the lead's20261003T053034Z preflight BLOCK; last own suite exited0 and no process remained.

### Fifteenth finished bounded argument repair — pending independent REFUTE

After the lead's20261003T064243Z FIX-AND-GO cleared the unchanged gate, passive source custody was repaired through exact adjacent coordination: a positively typed named medication immediately precedes its passive auxiliary, although the pinned parser places it under the preceding nominal. The same token is now accounted for in its child clause and removed from the parent's clause. Unknown objects, alternatives, nonadjacent tokens and subordinating marks do not establish that proof. A passive action cannot inherit the preceding active family's subject. Withholding's actual FROM recipient supplies only its own patient or foreign ownership; a missing recipient supplies no person. An unresolved same medication remains held; a positively named different medication narrows only that ended argument's dependencies.

A direct patient's known negative clinical argument can bound the mixed positional bare event without claiming that the clinical denial itself is independent of its own topic. The existing same-knee denial, patient medication denial, medication-bearing dependency, unknown-topic, side and ownership guards remain binding. No clinical class, orientation, medication name or future-time exception was added to a release list.

The first two-method passive probe retained two different-drug subcase failures in6.574s, rc1 (`refutation-15-narrow-2.log`). The pinned parser marked the unqualified passive as an ADVCL despite its explicit immediate AND/nominal/passive-auxiliary structure. Exact failed source remains in `fifteenth-passive-first-source/manifest.json`; parser witness is `diagnose-passive-15.log`. The same two methods then passed in5.883s, rc0. Finished exposed controls passed **66/66** in76.397s, actual exit0 (`refutation-15-local-2.log`): PatientDefault, transition controls and the19-test historical mocked owner contract. No database or provider request occurred.

The separate36-case exposed whole-validation/current-governance/finalization diagnostic matched36 expected guard outcomes in8.761s, rc0 (`exposed-fifteenth-controls.json`): **16 supported**, **20 held**, **zero observed unsafe release among the demonstrated negative controls**, and **two known unnecessary holds** from the explicitly unsupported base-modal scope, one per medication label. The two uncertain-perfect scope holds and two retained medication-bearing dependency holds are conservative guard evidence, not independently certified clinical accuracy. These36 cases are not the historical typed76 classifications or36 reference fields, and their outcomes do not change those denominators.

Unchanged original voice transcripts, mappings and raw first responses replayed with an explicitly hypothetical new clinician context retained0/0/0/1/0 supported fields, rc0 (`replay-voice-context-fifteenth.json`). Current-v4 SOAP remains1/9 ordinary fields, or1/11 whole form including signoffs; both old incorrect v3_2/v3_4 picks remain held. This is diagnostic reuse of raw provider evidence, not new audio accuracy, a fresh generation or actual voice-to-export qualification. No source/response was edited to score it differently.

The finished diff must still pass fresh independent REFUTE and the coordinated affected v4/review/voice HTTP workflow checks before clinical integration or provider use. The retained might-stop scope boundary is not reported fixed. All earlier refuted source/results remain unqualified and retained.

### Fifteenth source independently rejected — coordinated medication omission

Frozen `562dc645b13ed2e17ebed0ef9bc904c2c120366b` is unqualified. The author, security and lead independently reproduced four unsafe whole-governance outputs: a selected current warfarin claim survived `warfarin and apixaban were/was withheld from the patient`, for both medication headings, after a foreign positional clause. The pinned parser attached the first drug to the preceding nominal; passive-theme recovery captured only the last drug. Reversing the two drug names held the claim. Validation, current governance and finalization all released the original first claim in the failing cases. Exact first outputs remain in `probe-coordinated-passive-562dc645.json`, `security/refute-clinical-562dc645-r2.json` and `root-verified-clinical-562dc645-coordination.json`; security132 probes and lead8 probes exited0 as instruments, not qualification.

Security retained16 unnecessary-hold flags: two old base-modal inputs and14 new flags from eight distinct inputs. Six explicit actor/argument/polarity inputs account for12 new flags across both medication headings. Two anatomical HIS possessives remain held: no actor identity was inferred from gender or a nearby family noun. Their original flags and the lead's conservative ownership boundary are both retained; these outcomes were not rewritten as automatic successes. The standalone negated-withholding hold is distinct from the already-supported version with a foreign positional prefix. `security/refute-clinical-562dc645-scope-witness.json` preserves each exact source and owned clause.

The lead's later91% disk BLOCK paused product work with bytes unchanged. `sixteenth-blocked-checkpoint.json` records source, actual exits, no owned processes or pending requests and the next repair. Work resumed only after20261003T073135Z FIX-AND-GO at89%; no agent cleanup or provider request occurred in this slice.

### Sixteenth bounded passive and claim-scope repair — independent REFUTE pending

Detached passive recovery now requires the existing explicit positional nominal anchor. A different medication or unknown nominal head cannot prove that only the last drug was ended; incomplete groups fall back to a review hold. A sole explicitly foreign clause can bound its own bare event without inheriting a patient. Complete named endings covering every matching source key retain their actual recipient and cancellation; unknown, unparsed and modal endings retain the original floor. A foreign FROM recipient is distinct from a patient's request, while patient-owned medication and unresolved recipients remain held.

A canonical denial may carry its explicitly owned finite child, so its outer speaker cannot erase an inner patient's denial or turn another person's denial into the patient's. A complete named medication denial bounds only its own positional dependency. The existing malformed explicit patient denial preserves its exact named clinical topic, including beneath a foreign main clause, while a proved separate topic no longer holds unrelated medication. No orientation list, medication-name release list, assumed current status or future-time exception was added.

Three new methods passed in9.226s, rc0. The first69 affected checks retained one failure: the new argument reader discharged the old standalone explicit-patient MAY-stop floor. Exact source and output remain in `sixteenth-first-source/manifest.json` and `refutation-16-local-1.log` (68pass/1fail,79.792s, rc1). The modal fallback was restored without changing the test expectation. The same **69/69** semantic/transition/historical mocked owner checks then passed in80.808s, rc0 (`refutation-16-local-2.log`), without a database or provider request. Historical owner checks remain mocked adapter/workflow evidence, not live Sonnet5.5 owner qualification.

The finished72 exposed whole-validation/current-governance/finalization diagnostics matched72 expected guard outcomes in12.970s, rc0 (`exposed-sixteenth-controls-2.json`): **28supported**, **44held**, **zero demonstrated unsafe releases in that exposed control set**, **two known base-MIGHT unnecessary holds**, and two separately retained unresolved anatomical-pronoun outcomes. These are guard diagnostics, not72 independently scored clinical answers, held-back Word acceptance or the historical typed76/36 reference denominator. The first72-result diagnostic on the failed intermediate remains separate and unchanged.

Unchanged raw transcripts/mappings/first responses replayed under hypothetical NEW clinician context again retained0/0/0/1/0 supported fields, rc0 (`replay-voice-context-sixteenth.json`). Current-v4 SOAP remains1/9 ordinary or1/11 whole-form fields; the original wrong v3_2/v3_4 selections remain held. This supplies no new first-pass audio, actual review, generation, provider billing or export result. Fresh independent finished-diff REFUTE and the coordinated actual v4/review/voice HTTP workflows remain required before integration or live admission.

### Sixteenth finished source — bounded independent refutation result

Frozen clinical commit `98d0ce3957ec9a4bf46a0f412f29aa25923ba8ba` completed security's independent **184 whole-validation/current-governance/finalization controls** in54.633s, actual exit0: **zero unsafe releases**, **zero unsafe forced-stored-supported releases**, and no instrument errors. Its exact20 clinical component hashes and482 protected Git-source imports were unchanged before and after the run. The former coordinated patient-medication omission and nested patient-denial controls now hold. Raw results, parser witnesses and unchanged first failures remain in `security/refute-clinical-98d0ce39.json`, its log, and `security/refute-clinical-98d0ce39-scope-witness.json`; `notes-voice/clinical-frozen-98d0ce39.json` binds the source. This is a bounded source qualification result, not universal natural-language accuracy or actual workflow acceptance.

The independent instrument retained **16 unnecessary-hold flags across nine distinct inputs**. These include the existing base-MIGHT scope, anatomical or medication HIS possessives without proven ownership, a foreign recipient in a coordinated medication group, cancelled coordinated withholding, denial of having stopped a medication, and a FOR-family recipient whose role is not proved. The52 fresh inputs account for10 flags across five distinct inputs. These conservative cancellation/recipient/parser limitations remain visible; no actor identity, current medication state or successful result was invented to discharge them. The original raw voice replay still supplies one useful current-v4 SOAP answer and holds both former wrong picks, with all other first results unchanged.

An offline replay of the14 preserved typed relations-v4 first responses at this exact clinical source retained all **76 field statuses and texts unchanged**, actual exit0 (`notes-voice/existing-replay-98d0ce39.log`). It made no new provider requests and does not change the historical36 reference-field denominator, first-pass grading, paid campaign identity or original response evidence.

The next required gate is the coordinated real integration tree with Word's actual import-manifest ORM and SQL guards: `test_transcript_context.ReviewVersion`, `test_transcript_context.VoiceToWord`, `test_v3_field_relations_workflow` and `test_v3_notes_floors`. The voice workflow uses mocked transcription/provider responses; fresh actual synthetic Sonnet5.5/transcription work remains the lead's separately declared standing-authority campaign. No database suite, provider request, demo activation or installed release change was performed in this closeout slice. The lead session reported an execution error; its activation and shared-resource ownership were not assumed by a specialist.

### Separate Word action/status refutation — four exact source/writer failures

A distinct 72-case pure refutation of Word commit `17b4d04ade891e45e54a22f464a38d6fbc90df48` completed in 13.598s, actual exit 0, with all 495 source bytes and HEAD unchanged. Four comma/parenthetical first-person witness, manager, undersigned and patient-permission captions had zero coverage issues but exposed unprotected text/checkbox destinations and allowed machine-written human acts. Exact originals, mappings, writer values and exports are retained in `notes-voice/refute-word-17b/report.md`, `result.json`, `source-manifest.json` and hashed artifact directories. The Word specialist received the four inputs for independent reproduction before repair. The 42 raw flags include duplicate forged variants and table inputs already carrying unsupported write-in coverage; they are not claimed as 42 served-workflow failures. No database, provider, browser or native Microsoft Word result is claimed by this probe.

After that source was released, a separate immutable Git snapshot of the same failed Word commit completed 44 additional pure actor/witness controls in 10.044s, actual exit 0. Its 71 source files were unchanged before and after. Eight distinct witness, interpolated/fronted actor and checkbox-condition captions exported unprotected human acts without coverage issues in all three paragraph/checkbox/table structures, giving 24 exposed source/writer variants. The specialist's mutable repair was not measured. Exact originals and exports, positive ordinary-field controls, source hashes and limitations are retained in `notes-voice/refute-word-17b-extra/report.md` and its raw results. These variants are not a broad-form acceptance denominator or actual served generation result. The redundant 1.8MB Git snapshot has a precise cleanup proposal; no cleanup was executed by this specialist.

### Fresh Word source — actor destination and receipt-history failures retained

The distinct action/status lens of Word commit `3b0fed600a76f82c98199ba73c975b2b2377eaf5` completed **45 original structural inputs / 75 one-target writer attempts** in 11.018s, actual exit 0. The live tree had first passed its declared 495-file manifest check; it was then explicitly released so the Word specialist could repair independently found failures. This instrument scored an immutable 71-file Git document-package snapshot, with all 49 Python files matching the declared manifest and all 71 snapshot hashes unchanged before and after. The first missing-README manifest refusal and separate syntax-only instrument failure scored zero cases and remain retained. No mutable replacement source or actual served workflow was measured.

The corrected instrument retained **18 zero-coverage-issue human-frame writes across 14 input strings**. Actor/capacity blanks before an approval, permission or witnessing predicate lost the role already proved by their full original source; quoted approval/consent and conditional authorisation checkboxes also accepted machine ticks without roles. **Eight ordinary hold targets across three receipt-history inputs** remain separately recorded: active receipt history mapped to signature fields, and an explicitly recorded receipt date for signed consent mapped to a date but was protected as a consent act. Two genuinely separate initial-value destinations remained useful; a third mixed checkbox/initial input was unsupported with a merged label and is not counted as successful or a demonstrated role-propagation failure. Exact source/writer witnesses, originals, mappings, exports, raw refusals and file/line causes are in `notes-voice/refute-word-3b0/report.md`, `result.json`, `witness.json` and hashed artifacts. These are exposed pure safety/usefulness probes, not a broad Word acceptance denominator, provider generation or clinical-signing workflow result.

The Word specialist received the concrete findings for independent reproduction before repair. Own clinical source remains exactly the independently measured `98d0ce39`; no integration, activation, provider request or database test occurred. Root's observed `c9491651` still differs from that clinical source in generation and source scope; `notes-voice/root-semantic-source-c949-readonly.json` preserves the exact read-only comparison. No qualification was transferred to the shared candidate.
