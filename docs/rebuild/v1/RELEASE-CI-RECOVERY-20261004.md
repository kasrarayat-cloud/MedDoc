# Release-completion CI recovery — 2026-10-04

The latest pushed project candidate remains `6346019377ed1a2e65763da7040c6f85da13f72c`, draft PR [1294](https://github.com/kasrarayat-cloud/MedDoc/pull/1294). Its [CI run 37215844080](https://github.com/kasrarayat-cloud/MedDoc/actions/runs/37215844080) failed; its secrets run passed. No subsequent local repair is assigned that remote citation.

The actual completed job logs were read before any repair. Core jobs `111476058888` and `111476058852` contain 46 failure/error blocks covering **44 unique methods**. Support job `111476058951` contains two unique failed methods, one with two caption subcases. Browser job `111476058856` contains 13 passes and a failure asserting the served administrator's inactive Sonnet 5.5 ordinary-v4 profile. Marketing passed. These original logs and failures remain unchanged.

An initial `gh run view --log` returned exit 0 with zero bytes for four jobs. That instrument output is not evidence of empty logs. The genuine retained completed core logs and the separately retrieved REST support/browser logs are used instead. Their paths and hashes are in `/opt/meddoc-pro/rebuild/.runtime/v1-release-completion-20261004T200104Z/CI-original-failure-inventory.json` and the retained-C source inventory beside it.

The subsequent candidate repairs were inspected against those actual errors. The 44 original core selectors were then executed selectively on the clean, exact local candidate **`fcd68c9b43b0d65b0411d031b16ea66e2b2b104d`**, using the existing protected isolated QA wrapper. All **44/44 passed**, actual child exit **0**, no timeout, 135.223 seconds reported by Django and 148.876 seconds outer. Tracked source bytes remain unchanged; the owned normal and test databases are independently absent afterwards, and the child is reaped. No provider or renderer call occurred.

The first selective support rerun preserves an actual exit **1**: the old scalar-alternatives method had been renamed, so that obsolete selector is missing; the original authorship/clinical-recording destination method passes. The changed scalar contract was inspected rather than treating a missing selector as a success. Its two current positive/negative methods verify complete original controls and date destinations, retain unproved source coverage and conflicts, and refuse competing/malformed answers. Both pass, actual exit **0**, 3.361 seconds. The old failure, obsolete-selector error and current controls remain separate.

The browser cause is the expected literal `ordinary-fields-v4` differing from the actual configured `ordinary-field-relations-v4`. Existing commit `8f13ddf` repairs that assertion and its focused served-profile control passes. An actual final served browser run is still required; component proof does not establish dashboard completion.

The already prepared 119-selector financial packet was executed on the same clean `fcd68c9b` through its normal guarded source/wrapper checks. All **119/119 pass**: 24 pure/prepared-witness controls, 67 historical-profile/wire/metering controls and 28 persisted quote/hold/settlement/payer controls. All three actual exits are **0**, without timeout, with unchanged source, reaped children and independent normal/test database absence. Provider and renderer calls are **0**. This result qualifies that source; a later change to guarded clinical dependencies requires its own financial adjudication and affected execution.

Raw release-completion receipts remain under:

`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/release-completion-20261004T200104Z/`

| Evidence | Identity |
| --- | --- |
| `original-C-44-selectors.json` | All 44 original unique selectors; unchanged full-suite coverage is not inferred |
| `original-C-44-fcd68c9b/result.json` | Actual execution, source preservation and catalogue cleanup |
| Core selective log | SHA256 `e49e9ab7204c54bede1386ea7e299ccde33b898f40e9fc17b7163065de038501` |
| `original-C-support-2.log` | Original method pass plus obsolete-selector failure |
| `original-C-support-replacement-2.log` | SHA256 `6b002de3c58b4ec344b9bba3af0222f47605fc3aeec7d41b3dd5fd92c9357914` |
| `financial119-fcd/result.json` | All three real passing packet executions, exact source and zero provider/renderer usage |

This is selective recovery evidence, not final release acceptance. The finished integrated source must receive every required exact-commit CI workflow and its own affected application/export qualification. A merge, if performed, needs the merge commit's citation. The PR remains draft while those and the fixed original Word gates are unmet.
