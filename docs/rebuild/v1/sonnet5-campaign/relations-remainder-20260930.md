# Field-relations remainder: the six contradiction cases (QA worker), 2026-09-29/30

Campaign `quillmd-v1-sonnet5-staged-40`, same authority and declaration (`01ff8c7d`). The field-relations contract
moved from v1 (positional, attempt 17's failure) to v2 (keyed, schema-enforced) under the committed contract-identity
amendment `docs/foundation/mutations/20260929-quillmd-v1-sonnet5-relations-contract-amendment.md` (`ee5c1182`): the
base price is unchanged and the runner recomputed both pricing versions from it. Every send went through
`scripts/run-ruled-mutation.sh`; only the recorded remainder was sent; no completed case was re-sent. QA-worker
evidence only; the installed release was not touched. Model `claude-sonnet-5`, thinking disabled, effort medium,
geography unset (metered `global`).

| attempt | case | runner | served / stop | tokens | cost | model's answer | app outcome per field | export |
|---|---|---|---|---|---|---|---|---|
| 18 | N03 | `ee5c1182` | sonnet-5 / end_turn | 1914/95 | $0.004778 | both fields selected correctly | supported_correct, over_held | completed, read back |
| 19 | N10 | `ee5c1182` | sonnet-5 / end_turn | 2220/110 | $0.005540 | both correct (Smoker "No" read from "The patient does not smoke.") | supported_correct x2 | completed, read back |
| 20 | N13 | `ee5c1182` | sonnet-5 / end_turn | 2180/127 | $0.005630 | both contradictions flagged (`conflict: true`, selected units `contrary`) | job failed: whole response refused (contract) — stage stopped | none |
| 21 | N14 | `630b6185` | sonnet-5 / end_turn | 2168/127 | $0.005606 | both contradictions flagged | held_correct x2 | completed, nothing written |
| 22 | N15 | `630b6185` | sonnet-5 / end_turn | 2189/127 | $0.005648 | both contradictions flagged | held_correct x2 | completed, nothing written |
| 23 | N16 | `630b6185` | sonnet-5 / end_turn | 2164/127 | $0.005598 | both contradictions flagged | held_correct x2 | completed, nothing written |

**Unsafe adoptions: 0 of 12 fields.** The model flagged every planned contradiction (N13–N16). The only defect was the
application's: under contract v2 as first built, a reported contradiction made `records()` refuse the whole
response. Diagnosed offline (`diagnosis-ordinary-notes-failure-2-20260930.md`), repaired as a per-field hold
(`dfde4fc8`), refuted (a HIGH: a claim by relation alone was invisible to the competitor check), repaired
(`1f1a4932`, claims compete like selections), re-refuted (LOW only), integrated and CI-cited (`630b6185`); the
retained attempt 20 now replays as held_correct x2 with the job succeeding.

**Stage state.** ordinary_notes is recorded failed-3 because attempts 17 and 20 remain earlier stops and a send is
never made twice; the remainder cannot pass the stage, which was stated before each run. It measures the veto on the
planned cases; it does not qualify the field-relations path, which stays off by default.

| stage | limit | attempts | exposure | remaining |
|---|---|---|---|---|
| model_check | $5.00 | 1 | $0.002860 | $4.997140 |
| mapping | $25.00 | 1 | $0.009840 | $24.990160 |
| ordinary_notes | $10.00 | 21 | $0.099404 | $9.900596 |
| **total** | **$40.00** | **23** | **$0.112104** | **$39.887896** |

Ledger, QA database (23 receipts, sum $0.112104, 23 distinct request ids, 0 simulated, 23 reservations settled) and
the per-attempt manifests (all 23 verify, 0 problems) agree. Calculated costs; no provider billing evidence is
available in this environment.
