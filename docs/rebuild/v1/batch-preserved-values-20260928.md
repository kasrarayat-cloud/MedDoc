# Preserved scalar and unknown control constraint repair — 2026-09-28

Prepared/default off on `36d23068ba38683aa3d01aa3ac4921a83711b4e7`, in isolated `fix/v1-batch-preserved-values`. No database, provider, token-count, payment, deployment, activation, push or integration. Scanner identities are deliberately unchanged and still require separate review of the final source.

## Demonstrated failures

F-B3: in an inspected103-field Word form, legacy text Priority A originally displays1 and has a blank reviewed answer; Priority B is answered1. The old validator counted only B and accepted; the actual export contained two1s despite the unique-priority rule.

F-B4: a nonplaceholder native dropdown displays4 but declares only1/2/3. Blank reviewed answers passed the allowed-priority rule because the old reader represented that unrecognized display as allFalse. The unchanged export still displayed4.

Original independent scripts/results remain in the root-owned `v1-hyperlink-content-controls/rebuild/.runtime/independent-batch/`, including the separate root replay. Two new regression methods were run against the unchanged original source and both failed because no ValidationError was raised (`06-original-red.log`,0.622s). No original failure or document was overwritten.

## Change and limits

The existing source-hash-bound sandbox now reads all constrained scalar and option values after applying the unchanged Word writer in memory. Scalars no longer fall back to stored answer text. Native legacy text and SDT text/date controls, plain cells/paragraphs and unambiguous spans are read from the resulting package. Preserved values participate in both uniqueness and maximum-active-group rules. Copies must agree; explicit writes can resolve differing copies. Missing/unknown returned values refuse.

An unrecognized displayed dropdown/option-text value is unknown, separately from a genuinely empty placeholder. Invalid legacy dropdown indices also refuse. The general option-state reader and the Word writer are unchanged; the stricter distinction is confined to constrained read-back. Existing `effective_options` callers remain compatible.

Ambiguous relationships refuse explicitly. These include a legacy nonempty default without a visible result, unsupported scalar destinations, and span boundaries whose original surrounding text changed through a neighbouring write. Simultaneously filled neighbouring spans can therefore require further qualification even when their answers would satisfy the rule; that is an identified limitation, not an automatic-success claim. No unknown is counted as empty.

No rule inference, clinical keyword exception, manifest weakening, capacity/pricing change or history rewrite is included. The earlier ordinary opposite-side expected failure remains open. Automatic global-rule qualification, actual provider qualification and broader Word compatibility remain separate dependencies.

## Finite evidence

- First9 new sandboxed no-DB cases passed11.179s (`01-focused.log`).
- First affected run exposed two old pure aggregation fixtures without the newly required exported-value reader (`02-affected-first.log`). Their expected synthetic exported values are now supplied explicitly; actual preservation/read-back is verified by the separate real-DOCX sandbox cases.
- Final focused/affected run:35 tests,34 passed and1 existing opposite-side expected failure,33.076s (`03-focused-affected.log`). Covers both original failures, valid explicit replacements, placeholder controls, invalid legacy indices, default-only refusal, preserved SDT dates, plain cells/spans, copied scalar anchors, unknown/missing values, neighbouring-span refusal, existing checkbox/multichoice constraints and existing control read-back. Django explicitly skipped database setup.
- The exact original103-field fixtures replayed with only source selection and exception capture changed; both now refuse (`05-original-repaired.json`). The first replay adapter caught validation errors but failed when separately querying the newly unknown effective value; its source and empty result04 remain retained. The complete adapter catches that read separately. No product code changed for this instrumentation correction.

All test connections were prohibited by the fixture, with managed/synthetic environment and dummy DB port1. The document-service checks exercised the actual bounded subprocess sandbox. No filled DOCX is retained or tracked; test packages stay in memory or temporary directories managed by the tests.

Private logs and replay adapters: `rebuild/.runtime/batch-preserved-values/`. Finished-diff independent refutation is required before integration. Source remains frozen during that review.
