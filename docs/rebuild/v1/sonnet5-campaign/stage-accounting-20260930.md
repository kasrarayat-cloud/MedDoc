# Sonnet 5 staged campaign — stage accounting, verdict vs admission (2026-09-30)

Authority `quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk` ("Approve the staged $40 maximum"), one campaign,
cumulative caps, declaration `01ff8c7d` (+ contract-identity amendment `ee5c1182`). Reconciled read-only before any
further work: `ops/sonnet5_qa.py status` on runner `630b6185` reports 23 attempts, `open_attempts: []`, no campaign stop;
every attempt's manifest, cost and QA-database receipt verify (23 of 23, 0 problems). Attempts 17 and 20 and the
failed verdicts are unchanged.

| stage | limit | attempts | exposure | remaining | decisions | verdict | admission today |
|---|---|---|---|---|---|---|---|
| model_check | $5.00 | 1 | $0.002860 | $4.997140 | passed | passed | not needed |
| mapping | $25.00 | 1 | $0.009840 | $24.990160 | failed-1 | **failed** (attempt 2, contract: one invalid change discarded the whole proposal) | reopen-1 permitted by the stop rules with a committed diagnosis naming attempt 2 and a repair commit the runner contains; then only the 9 declared sends not yet made (7 mapping + 2 generation, worst case ≈$2.37) |
| ordinary_notes | $10.00 | 21 | $0.099404 | $9.900596 | failed-1, reopened-1, failed-2, reopened-2, failed-3 | **failed** (attempts 17 and 20 remain stops) | a reopen-3 is procedurally possible, but **no declared send remains**: remainder mode never re-sends, so nothing is admissible |
| **total** | **$40.00** | **23** | **$0.112104** | **$39.887896** | | | |

**Which restriction affects what.**

- *Verdict:* both failed stages keep their failures. A remainder run cannot turn a failed stage into a pass
  (`can_pass: false` in both plans), because an attempt is never re-sent and the stopping attempt stays in the stage.
- *Admission — mapping:* money and stop rules both permit the 9-send remainder after diagnosis and reopen. It measures
  the repaired mapping path on the live model; it cannot pass the stage.
- *Admission — ordinary notes:* not money ($9.90 remains) but the declared plan: every declared send was made. Any
  further live measurement of the repaired notes contract (for example the 14 default cases under the field-relations
  contract) is a new send outside the declaration and therefore needs a **new allowance from the owner**. No replacement
  campaign, renamed stage, fund transfer or relaxed stop rule is used to avoid that.

Calculated costs (pinned rates × provider-reported usage). Provider billing evidence is not available here (the
campaign key is a Messages key; usage/cost reports need an Admin key or the console).

## Addendum 2026-10-01 — the mapping remainder

Mapping was reopened (reopening 1, diagnosis `diagnosis-mapping-failure-1-20261001.md`, runner `f55a1561`, CI green;
plan: 9 sends, worst case $2.3745, `can_pass: false`). The first send, attempt 24 (`mapping:f2-leave-checkboxes`,
$0.018776), returned a proposal that left 11 of 35 slots unclassified; the whole-response rule refused it and the stage
stopped again (failed-2) before the other eight. Nothing unsafe was adopted. Repair `f8adebd9` holds omitted IDs for
review (`diagnosis-mapping-failure-2-20261001.md`). The stage is NOT reopened: the runner's
repair check watches no mapping-assistance module, and passing it through an unrelated watched-file change would weaken
a stop rule (see the diagnosis). A further mapping measurement needs an owner decision.

| stage | attempts | exposure | remaining | decisions |
|---|---|---|---|---|
| model_check | 1 | $0.002860 | $4.997140 | passed |
| mapping | 2 | $0.028616 | $24.971384 | failed-1, reopened-1, failed-2 |
| ordinary_notes | 21 | $0.099404 | $9.900596 | failed-3 |
| **total** | **24** | **$0.130880** | **$39.869120** | 0 open |

