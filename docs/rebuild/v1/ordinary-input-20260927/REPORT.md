# Ordinary input continuation — 2026-09-27

## Frozen candidate

New isolated tree `/opt/meddoc-pro/.worktrees/v1-ordinary-input`, branch `v1/ordinary-input`, base **b2abff5bb7c69abdb5ef685644480a24a3c2198a**. Clinical source **fe938a2a84a8393c7fd98f614194d844a1050192**, generation SHA256 **8835d98c6943a323a07207a627151c19a34e98bcb15d2c6f373575ac586396e0**. Following commits are documentation/evidence only. The earlier independently cleared ordinary-context tree remains frozen.

**Prepared locally, with mandatory final independent refutation pending. No push, merge, installation, activation or provider call. B-G1 remains open.** App model remains Sonnet5; these mocks are not live model verification.

## Completed bounded repairs

**Inline printed options.** The option evidence locator now uses the same sentence boundaries as `source_units` when a physical line opens with ordinary prose. Previously `Patient presents... Smoker: No.` offered a correct complete source unit but the option reader refused it because the physical line did not begin with a form label. Whole values, exact offsets, unique printed options, duplicate questions and uncertainty guards remain enforced.

The first affected-suite run found a real regression: `Father: MI at 50. Smoker: yes.` became supported. The log and exact intermediate source are retained. Inline option units in a prose-opening physical line now require established preceding source context in both generation and the shared stored-answer reader. A sentence boundary alone cannot establish patient ownership. Forced-old-supported page/finalization tests refuse the father/family and unqualified consent cases. Physical-line detection matches Python's source `splitlines` behavior, including CRLF, CR and U+2028. The older separate-line contract is deliberately unchanged, and its existing proof remains explicit.

**Two narrow ancillary source relations.** A complete two-statement paragraph may keep an exact unique Smoker choice independent of `Patient [was] seen [today].` or `[The] patient drinks socially.`. Source IDs for both statements remain recorded; the tail is not erased. This relationship applies only to the actual Smoker choice. Unknown questions such as Seen recently or Alcohol use, Medications, Consent, extra clauses, qualified tails, corrections, negation, family and conditional scope are held. This is a bounded declared topic relationship, not a general patient-subject reset or a complete clinical context classifier.

**Explicit age/sex presentations.** Anchored forms such as `45-year-old man presents with...` and `This is a 30-year-old female seen for...` can establish the patient subject for the existing history/complaint destination contract. The full source sentence, age, time qualification and offsets remain intact. Local `after`, `ago` and `since` words stay with that presentation rather than governing unrelated later field subjects. They are not relaxed on a pronoun continuation or another topic. The repair does not split partial source blocks, choose between duplicate history destinations, reset relatives, or infer a new clinical answer.

Only five generation definitions changed: `LabelledLines`, `v3_preceding_reading`, `v3_scope_selection`, `v3_preceding_warnings`, `validate_tab_selections`, plus the small source grammar constants. AST comparison confirms D19-owned `v3_generation_fields` and `v3_adopted`, and root's `anthropic_request`, are unchanged. The field-capacity/row expansion stream remains separate.

## Verification and preserved failures

| Evidence | Result |
| --- | --- |
| Inline RED then repaired module | Initial six tests: two failures, exact option and full seven-answer inline workflow. Same six pass after locator repair. |
| Ancillary and age REDs | Each three-test set initially had its intended positive failure; both pass after bounded repairs. Negative controls retained. |
| First affected modules | 136 tests, two failures: real inline-father regression plus historical t-r10 hold assertion superseded by the authorized new positive. Neither failure concealed. |
| Repaired affected modules | **137 PASS**,29.678s: ordinary-input, ordinary-context and original ordinary-note tests. Includes existing consent/withdrawal, allergy corrections, wrong field/side, repeated source/dose, reference coupling and Unicode ownership guards. |
| Final source module | **17 PASS**,10.292s after the physical-line compatibility follow-up, including its CRLF/CR/U+2028 controls. Unchanged earlier module checks are reused. |
| Complete Word workflows | Seven-answer note9 as one prose paragraph; unchanged t-r10 and t-social notes on the synthetic Smoker form; retained note1 age sentence on the three-field physician/complaint/smoker form. Each exercises upload, mapping confirmation, mocked Sonnet5 worker, review, unchanged reviewed save, finalization and export of the original Word file. Exact text/hash/original bytes and applicable No/Yes check states asserted. |
| Request/accounting/legacy identity | Exact base and final source each produce **30 identical records**, digest `d3bf17e6f8361534a652b6a9822ed91b2c7ceeca055ce004f6dad535e8da6a08`. Actual mocked requests and validated outputs, no provider request. |
| Final independent refutation | Pending on source fe938a2a before integration. |

The source-preserving Word flows are engineering regressions, not native Microsoft Word acceptance or part of the60-file compatibility numerator. The age workflow uses the original source sentence in a declared context slice; it is not claimed as full r1-note1 completion. The inline note9 layout variant is reported separately from the unchanged retained-note measurement.

The identity harness initially failed preparation because the reused file imported its generation module via `harness`, not the searched direct import. No provider request or validation ran during that failed setup. The corrected helper, failed invocation logs, and successful base/candidate/final records are retained. The base-only override is explicit in the helper and never changed application source.

All inputs are retained synthetic examples. Dedicated notes PostgreSQL55706 was used; `--keepdb` preserved the synthetic test database. Missing-staticfiles warnings remain in logs. No test/process is active at handoff.

## Actual retained denominator and remaining gaps

Same15 historical synthetic inputs, exact original fields and unchanged selections; no ablations or new campaign. Original first-pass results, every previous repair stage, current exact-base results and intermediate/final outcomes remain available.

| Subset | Original first pass | This branch base | Final repaired known cases |
| --- | --- | --- | --- |
| Five retained notes |1/12|10/12|**12/12**|
| Ten retained r1 notes |5/77|18/77|**22/77**|

These are selected-answer outcomes, not document-level compatibility or a general clinical accuracy percentage. The total77 is unchanged, including invalid or ambiguous historical picks.

- **r1-note1 is now5/9**, up from1/9 on this branch's base. Explicit Allergy, inline Smoker, Examination, qualified Assessment and Plan are supported with their original wording. Chief/HPI/PMH/Medications remain held: selections split a mixed patient/pronoun block and repeat an unowned source across destinations. The age sentence has a valid independent path; that does not establish those partial or repeated selections.
- **r1-note2 stays6/9**. Chief/HPI/PMH remain a concrete source-block/role engineering gap, not a missing provider payment.
- **r1-note9 stays7/7**, the complete original note already proven through Word export. The new inline layout path also passes.
- note5 stays3/7 and note7 stays1/7. SOAP source-role mapping and caregiver/child attribution still need a defined source-evidence contract and bounded offline repair.
- notes3/4/6/8/10 retain their earlier outcomes. Clinical negation and pronoun topic decomposition remain code gaps. The54-word whole-note picks, procedure-to-Examination assignment and genuinely ambiguous father/He ownership cannot serve as reliable positive oracles without appropriate source/product evidence. Every result remains in its denominator.

The complete-source contract is still too restrictive for broad ordinary day-to-day notes. A next bounded source-span/role design must distinguish complete supported assertions from partial selections that drop negation, time, dose, relatives or correction. Do not grow a keyword list, infer consent or replace notes with mandatory labels to make the remaining rate look better. Literal coupling also remains limited: it is not a synonym-aware semantic contradiction detector. Live exact-model selection/clinical quality and unavailable independent product/Word/dictation evidence remain separate release requirements.

## Handoff

Runtime `rebuild/.runtime/ordinary-input-20260927/`; durable `evidence/` contains base and intermediate source snapshots, original and final results, tests, helper scripts and SHA256 manifest. Source frozen atfe938a2a. Next safe action is independent finished-diff refutation, reproduce any finding and repair safely, then parent integrates a reviewed union preserving D19 and model/accounting work. Parent owns release, financial authority and deployment state. No spending allowance, provider receipt, campaign reservation, account agreement, real-data operation or unexplained lock action arose in this stream.

## Later source-context repair

The prior frozen-source status above is historical. See [VALUE-CONTEXT.md](VALUE-CONTEXT.md) for the independently discovered complete-value evidence gap, preserved failures, source 5caaa50dc7c77f6d491b30a22d829ff80b4847c5 and142 passing affected tests. Final refutation remains pending; B-G1 stays open.
