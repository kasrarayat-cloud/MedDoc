# Ordinary context follow-up — 2026-09-27

## Current candidate

Worktree `/opt/meddoc-pro/.worktrees/v1-ordinary-context`, branch `v1/ordinary-context`. Source commit **1747bb2dbce6a8799af08c477164e2ac0d5a5976**, generation SHA256 **f6e8789f73cf006b05f2bd51bca78b6051610588746cef32cdf9af53f863d1c4**. Original integration base remains `ebcddc2a0fc09630ab96c62ef84028f3c567cf03`; the follow-up code diff is from first evidence head `6388a22e98fe84bfbf8e2ac0a6ce9a1fd9f24196`. Root's separate request-schema repair `d798ea7e` is not in this branch and must survive the later union; this stream made no request/profile changes.

**Prepared locally; independent finished-diff refutation of this final source is pending. No merge, push, deployment or activation occurred. B-G1 remains open for demonstrated code gaps.** All model responses were simulated. No provider request, new financial allowance, campaign, holdout, agreement, email or real-patient operation was used.

## Reconciled independent finding

The prior finished diff was independently refuted: `Plan: amoxicillin? Return if symptoms worsen.` became supported and an old supported record passed the shared finalization reader. Root separately confirmed it. Reviewer report, script, candidate and exact-base outputs are retained unchanged in `evidence/round2/independent-*`; separate generation and stored-review RED tests are in `question-red.log`.

The reader now checks the constituent sentences of a conditional Plan. A following return instruction cannot make an earlier treatment question supported. Generation holds the question; the existing-supported page becomes conflict/blank and `governed_decisions` returns `['Plan']`, even when its old reviewed flag is true. The complete affirmative `Plan: amoxicillin. Return if symptoms worsen.` remains supported unchanged. The final20-test module pins same-line and split-line negative generation, forced-old-supported review/finalization, and the positive.

The unchanged eight-case reviewer script was replayed against final source (`independent-repaired.json`). It now produces conflict for the question. That script calls `governed_decisions` on the *already conflicted generated answer*, which returns[] because that function handles implicit governance of older supported/accepted answers; this is not a finalization success claim. The explicit old-supported regression test exercises the required refusal path. Other baseline subject ambiguities found by the reviewer remain known limits, not claimed repairs.

## Exact clinical source subjects

The v3 reader keeps source-subject recognition separate from value extraction. Exact unique actual form heads `Examination`, `Assessment` and `Medications` may establish independent topics in complete source sentences. A bounded prefix and predicate grammar supports retained phrases such as `On examination there is...`, `Chest examination revealed...` and `Current medications are...`. It records the actual head's source offsets and preserves the entire new sentence, including modifiers. It does not rewrite a template or ask a clinician to relabel their note.

An exact Assessment retains `probable`; an exact Examination retains `not performed today.`. These local qualifications stay visible in their own answer. Existing family, hypothetical, correction, prior-context, question, side and destination guards still apply. Pins cover `No examination was performed` (faithful complete text or hold), mother examination, previous examination, conditional examination, duplicated form subjects, wrong field selection and a stored wrong-destination answer. Source offsets are checked against the actual original head text.

Author self-refutation then found another introduced omission: selecting only the first of two `Current medications...` sentences could drop the second and remain supported. Its script/RED output and pre-fix source are retained. The new subject route now holds repeated source subjects and shows all of their statements, including across blank paragraphs. Generation and forced-old-supported finalization are pinned. This remains a visible review requirement; repeated subjects are not counted as automatic success.

## Verification and exact limits

| Check | Result |
| --- | --- |
| Existing ordinary, Word workflow and review modules | **246 PASS**,153.700s (`affected-paths.log`), before the final conservative repeated-subject guard. Those unaffected checks are reused; the final guard and its affected paths were checked separately below. |
| Final ordinary-context module | **20 PASS**,5.608s (`context-final.log`), on source SHAf6e8789f... Includes all new positives/refusals and three complete Word workflows. |
| Whole retained ordinary note | **r1-note9, unchanged notes and original seven selections**, passes upload/mapping confirmation→queued worker with simulated Sonnet5→review→unchanged reviewed save→finalization→original Word export. All seven answers are supported; exact text, original bytes, export hash and actual No checkbox are checked. No corrective manual mapping or relabelled note. |
| Legacy/current-profile identity | **30/30 identical** current Sonnet5 tab, WM and legacy request/price/fixture/validated records; digest `d3bf17e6f8361534a652b6a9822ed91b2c7ceeca055ce004f6dad535e8da6a08`. Thirty actual mocked requests and structured validated results; original historical identity records remain unchanged. |
| Replayed independent finding | Question is held; positive retains complete Plan text; explicit stored-old-supported test refuses. |
| Mandatory final independent refutation | **Pending** for source1747bb2d. |

The Word files in these tests are synthetic regression fixtures. They do not count toward the60-file authorized compatibility corpus or native Microsoft Word acceptance. These logs do not establish live Sonnet behavior, actual served model identity, human dictation quality, or a completed V1 clinical release. The earlier207 Sonnet/profile/settlement/Word/review results remain valid evidence for their unchanged paths; the follow-up did not rerun unrelated profile campaigns.

## Known-note results: preserve each stage

Same15 retained synthetic notes; same historical source selections. No ablations, denominator replacement or broad new campaign. Per-case original notes, fields, unchanged picks, outputs/context and hashes are in `evidence/round2/known-results.json`. Pre-duplicate-repair outcomes are separately retained; the final rerun confirms all15 outcomes are identical after that conservative repair.

| Subset | Original first pass | First context repair | Current follow-up |
| --- | --- | --- | --- |
| Five retained notes |1/12 supported|10/12|**10/12**|
| Ten retained r1 notes |5/77 supported|7/77|**18/77**|

No document-level compatibility or market-wide percentage is inferred from these selected-answer counts. The first-pass description “ideal picks” was too broad: r1-note3 selects a54-word whole note into almost every field. Those picks cannot establish field-specific medication/allergy/plan answers and remain held; none is promoted to inflate success.

Current useful results and unresolved causes:

- **r1-note9:7/7**, the unchanged complete medication-review note, proven through actual Word export. Full medication sentence, negative/time-qualified examination, explicit assessment, Plan and printed No option survive.
- **r1-note2:6/9**: medication, allergy, smoker, examination, assessment and complete conditional Plan now work. Chief/HPI/PMH remain held because the selections divide an unlabelled patient/pronoun block. Those are source-context engineering gaps; unavailable provider funding is not their cause.
- **r1-note1:1/9**: the explicit allergy now works. The age/sex presentation, pronoun/combined history-medication sentence, inline option and inherited context still prevent a useful complete note. Most of these are ordinary positive content, not failures that can be discarded as invalid picks.
- **r1-note5:3/7**: SOAP subject/objective headings do not establish this form's actual question destinations; the remaining assessment also inherits an unresolved Plan boundary. No mandatory labelled-note workaround is substituted.
- **r1-note3:0/9** remains an unpunctuated mixed-topic source. The whole-note selections are not valid concise field answers. A reviewed punctuated transcript or a bounded exact-span/context contract remains necessary; the original failure stays in the denominator.
- r1-note4,6,8,10 remain held broadly; r1-note7 has only its explicit allergy supported. Relative/patient roles, ordinary negated context and implicit topic transitions need additional work. Some source statements are actually ambiguous (for example a father history followed by “He...”); an oracle's patient attribution cannot make that ambiguity disappear. Consent remains a separate deliberate clinician decision.

## Next safe action

Parent routes source1747bb2d to independent refutation, reproduces any finding and integrates only after clearance, preserving its separate Sonnet schema repair. No writer/test remains in this tree after handoff; logs and scripts are under `.runtime/ordinary-context-20260927/round2`, with durable copied evidence here.

Continue bounded source-context engineering on valid retained age/sex/pronoun, SOAP and ordinary negation cases after that gate. Distinguish ambiguous source subject attribution and invalid whole-note picks from ordinary positives that the code cannot yet use. Broad custom Word qualification and exact-model live verification remain separate release requirements. This stream closes specific defects and demonstrates a complete retained note; it does not close B-G1 or V1.
