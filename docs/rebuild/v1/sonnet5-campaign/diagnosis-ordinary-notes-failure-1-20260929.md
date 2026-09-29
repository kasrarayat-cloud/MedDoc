# Diagnosis: ordinary_notes failure 1 (2026-09-29)

reopen_stage: ordinary_notes
failed_attempts: 3,4,5,6,7,8,9,10,11,12,13,14,15,16,17
repair_commit: 691e27d05a1fc1bff257149ab66b6ee7b0d8aa45

**What stopped the stage.** Attempt 17 (N02 on the field-relations path, request `req_011CfXCyMx9oAibfWL799x4f`)
returned `end_turn` with acceptable selections, and `v3_field_relations.records` refused it: "Ordinary relations must
cover the exact source and original options." The v1 contract asked for one positional `context` entry per source
unit; the model returned one per selected unit. The sent schema carried no length constraint on `context` (a
request-dependent length cannot be written into the static model), so structured output did not enforce coverage.
Reproduced offline from the retained request and response; the replay equals the live refusal. Attempts 3-16 (the
default path) completed; their results are recorded in `live-stages-20260929.md` and are not changed by this repair.

**Repair (`a21769e2`, refuted and repaired in `691e27d0`).** Contract v2: a per-request schema in which each field's
`context` is an object whose required members are exactly the unit IDs, closed to others, each an enum of the five
relations; a strict parser refusing duplicate members, wrong types, unknown or missing keys, then converting to the
unchanged internal form. `CONTRACT` and `SALT` move to v2 so v1 records, queued jobs and raw results refuse. The runner
gains a remainder mode (only the sends the failure recorded as not made) and a contract-identity amendment path
(`docs/foundation/mutations/20260929-quillmd-v1-sonnet5-relations-contract-amendment.md`). Two refutation rounds; the
second confirmed nine findings, all LOW (recorded in the close-out).

**What a remainder run can and cannot show.** The remainder is N03, N10, N13, N14, N15 and N16 on the
field-relations path. Attempt 17's stop stands and N02 is never re-sent, so the stage cannot pass on this remainder:
a clean run is recorded as failure 2 carrying the six outcomes. That is the intended use: it measures the paused
contradiction veto on the six planned cases; it does not qualify the path.
