# Allergy independence finding and containment

Current source: **35d391b31c55490e176f2cc3029bc6c31518fd52**.
Worktree and branch remain `/opt/meddoc-pro/.worktrees/v1-patient-topics`,
`v1/patient-topics`. This supersedes the accepted-result interpretation of the
earlier report, not its retained evidence. Independent re-refutation is required
before integration. The separate parent-owned nominal correction dependency
remains outstanding for the eventual union.

## Verified finding

Root changed only the Assessment in the original retained note4 to either
`Assessment is penicillin anaphylaxis.` or
`Assessment is penicillin hypersensitivity.` Selecting only the unchanged
`No known drug allergies.` source on058 returned a supported allergy answer;
a forced old supported record passed finalization governance. The exact aa4e8
base holds both cases. The author reran the unchanged eight-case probe and
reproduced the two failures before modifying code.

Patient attribution did not establish independence from a clinically related
Assessment. This was a new false green. The absence of the literal word
`allergy` in that Assessment did not make it unrelated. No drug, reaction or
synonym dictionary was introduced to hide the demonstrated case.

## Minimal change

Remove only **Allergies** from the new actor-based destination exemption.
The existing complete NKA recognizer and its previous context requirements
remain unchanged. This intentionally holds NKA in the original note4 as well
as the two adverse variants. It does not claim to classify all clinical
contradictions. The actor module, other three named values and existing scope
rules are unchanged.

The complete-note workflow now shows three automatic values (Examination,
Assessment, complete Plan), plus five held selections. Allergies is explicitly
resolved by the synthetic clinician with the other four decisions. That is
assisted completion and is excluded from the automatic count. The original
source, full wording, template bytes and export hash remain preserved.

## Evidence

All files below are in `evidence/refutation-1/`, with hashes in its manifest.

| Evidence | Result |
| --- | --- |
| `root-candidate.json`, `root-actual-parent.json` | Independent first finding and exact-base comparison. The separately retained `root-parent-literal.json` was the reviewer's initial different-parent comparison; it is not the accepted baseline. |
| `author-verified-red.json` | Author reruns the unchanged root probe on the exact refuted source and confirms both false greens. |
| `01-exact-red.log` | Two new tests fail in three assertions before the fix, including forced stored governance. |
| `02-final-focused.log` | **30 pass in 11.739s**: current patient-topic, literal-subject, cost and existing ordinary fragment contracts, including real upload/worker/review/assisted save/finalization/export. |
| `03-author-repaired.json` | Exact unchanged eight-case probe: both adverse allergy values are conflict/blank; forced supported records return `['Allergies']`. |
| `04-retained-contained.json` | Same 15 original inputs/fields/selections: **12/12 and 26/77**; exactly three supported changes from the immediate base, all note4. |
| `workflow.json` | Actual original note, automatic records, five separate clinician decisions and final records. Runtime synthetic original/export packages are hashed by the manifest. |

The actual stored-route negative first resolves every other field with explicit
clinician blank decisions, then injects only the historical allergy record.
Thus the refusal cannot be explained by unrelated missing/unreviewed fields.
The allergy is held on display, unacknowledged save does not clear its context,
and finalization refuses. Both adverse Assessments are exercised.

The female/He and male/She variants in the original probe are **not findings**:
sex does not determine pronouns. No sex-to-pronoun rule was added.

## Current limits and next safe action

Earlier 27/77 results and all first-pass failures remain intact. The same 77
denominator now contains 26 accepted and 51 held selections. Against the earlier
triage, 34 remaining relevant-value selections still identify engineering work;
seven need precise expected-field or ownership adjudication, and ten original
selections are invalid single-field oracles. Nothing was dropped or reassigned
to provider funding to improve this result. **B-G1 remains open**, including the
ordinary-note source/field and implicit-subject issues listed in the original
report. Allergy recognition alone does not close this source-context gap.

Next: independent finished-diff re-refutation of35d391b3, then the parent's
reviewed correction union and its final checks. No push/merge/deploy or live
model qualification occurred. Source is frozen; no active test process remains.
The dedicated 55706 test DB and all runtime evidence are retained.

- Generation SHA256: `dc394c394b6aad3803a06aab1a7a70f8ed132b10f4bcc815dca599bf963e6e20`.
- Actor module SHA256 remains `56f687a3f22fc4c7ce6acd494ff396f97d92cd020e0c7f3492afad079dd7119a`.
- Runtime: `rebuild/.runtime/patient-topics-20260927/refutation-1/`.
