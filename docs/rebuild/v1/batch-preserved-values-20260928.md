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

Frozen source `952c7e2100e451882c1fd837980ab0212dc4f586`; [retained evidence and source hashes](batch-preserved-values-20260928/manifest.json). Evidence copies preserve original failures, the replay-adapter failure, and the successful finite results separately.

## Independent refutation F-B5/F-B6 and bounded follow-up

The independent33-case pass refuted the first repair. Its original `01-results.json`, script and line-cited report remain unchanged in root-owned `v1-hyperlink-content-controls/rebuild/.runtime/batch-second-review/`. Author replay07 reproduced all10 mismatches while the Word source still matched the frozen952 hash. The first repair remains reachable at952; it was not rewritten or retrospectively described as complete.

**F-B5:** native SDT scalar/dropdown controls whose `showingPlcHdr` marker explicitly says0/false/off were treated as empty placeholders. Preserved1 plus another answered1 therefore passed. The flag must be present **and true**; absence means regular contents. This is the documented [Microsoft ShowingPlaceholder/OnOffType contract](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.showingplaceholder?view=openxml-3.0.1). The constrained reader now interprets true/false encodings explicitly; invalid or duplicate flags are unknown. Missing SDT content also refuses as an unknown boundary; no wrong displayed value is claimed for that separate observation.

**F-B6:** a legacy field without a separator retained a `w:t` value in output XML but was accepted as known empty. This is a demonstrated malformed-boundary acceptance, **not a native Word rendering claim**. The constrained reader now requires exactly one result separator and rejects visible text before or inside field-marker runs. It cannot certify an ambiguous malformed field merely because an explicit write adds a separator.

Three additional marker-run cases were found while checking that same boundary: text inside the begin/separate/end run was excluded from the old result reader. First controls collided with the ordinary duplicate-priority check (log11); using distinct priority B isolated the defect and all3 were wrongly accepted (log12). The final boundary check rejects these without changing the Word writer. All original observations remain separate.

Final focused14 tests passed34.566s (log13), including all six on/off encodings, an omitted `val` attribute, malformed/duplicate markers, missing content, missing/duplicate legacy separators, marker-run text, explicit valid fixes and unchanged original F-B3/F-B4 controls. Test temporary directories now use the session-specific `/tmp/claude-1000/batch-preserved-values-20260928`; durable evidence remains under ignored runtime. No DB/provider call was used. Full repaired source requires another independent refutation; scanner pins remain untouched.

The final affected24 tests passed with the single existing opposite-side expected failure (log14); combined with focused14,37 pass and1 known expected failure. Author replay of the unchanged independent33-case probe against the final source has zero mismatches (result15). This is an author replay, not a new independent review. [Follow-up source/evidence manifest](batch-preserved-values-20260928/adjacent-manifest.json) preserves before/after records and the reviewer originals separately.
