# Elicited qualification process pricing repair — 2026-10-04

The normal canonical-5 E01 invocation refused before opening a run or attempting a provider request. Its all-off process correctly computed the declared generic price `configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2`, but `check_configuration` compared it with the qualified per-send price. The retained status shows only the successful C1 model-check attempt, no open or unknown attempt, and zero elicited attempts or failures.

The runtime change adds `ordinary_notes` first in `STAGE_PRICING['elicited_qualification']`, matching the existing notes stage. The process still requires every contract flag off. `standing_qa_elicited.price_sends` and `ElicitedRun.notes_send` retain their existing per-send override, closed ordinary-v4 contract, exact qualified price and 20,000-token profile. A caller environment flag cannot replace the normal scrubbed process configuration.

Four focused offline methods passed, with zero DB/network attempts and unchanged source (10.034 seconds including imports; 8.051 seconds in unittest). They exercise the actual generic 8k configuration, actual deterministic forms and qualified price/compiler at 20k, then reject the wrong process price, a global relations flag, the wrong qualified price, an 8k qualified profile and an arbitrary default send. Restoring the original tuple in memory makes the positive control fail with the same pricing refusal; that expected failure is retained separately.

Base C1 is `2240a49ed4f843cf2248550a46bd35fdf3bbb8f9`. Its normal model-check run 0001 remains C1 evidence: request `req_011Cfhs31xT7u3b79tX5VAwr`, Sonnet 5.5, 8,000 tokens, between-tools thinking, medium effort, no inference geography, calculated provider cost `$0.002862`. Its original manifest, request, response, outcome, export and run records remain unchanged. This generic prerequisite can apply to the repaired runner because the model-check pricing entry, process flags, compiler, worker and fixtures are unchanged; it is not a qualified 20k result on the repaired source.

Normal canonical-5 resumption is applicable: `require_preflight` checks the campaign/model; `stage_open` checks pinned terms and the passed prerequisite; `begin_run` records each new actual runner commit. The refusal created no failed stage or reopening. The declaration, original gold, fixture manifest and 24-send plan stay unchanged. New runs must record their actual C2 commit; no C1 artifact is relabeled. Six intended sends remain (five elicited and first N01), after which 13 other notes and four voice sends remain unattempted. Provider testing resumes only after the integration owner freezes and grants C2.

Protected evidence, all retained under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/hpi-release-20261004/qualification-preparation/`:

- `canonical5-send2-E01.log`, `canonical5-refusal-status.json`, `canonical5-before-attempt-refusal.json`: actual refusal and accounting.
- `ops-price-repair-controls-r1.log` and `ops-price-repair-controls-r1-result.json`: four successful controls.
- `ops-price-baseline-r1.log` and `ops-price-baseline-r1-result.json`: expected baseline rejection.
- `ops-process-repair-proof-r1.json`: sole runtime AST delta, unchanged clinical/source bytes and C1 record seals.

No qualified provider result on this repair is claimed. The 16-case cached application transfer is prepared separately and will bind the final integrated source before execution.
