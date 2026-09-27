# Clinical repair refutation — 2026-09-27

**REFUTED:** the original failures close, but adjacent record-edit language still
passes and ordinary physical-removal documentation gains false holds.

Reviewed frozen commit `5b95a725d9b7b51f24cff61cf66807753642201f`, generation
SHA-256 `7d31a1acf99e61d892911f761c16371357ab370322da8337102872ffe33500d3`.
Baseline: union `aa4e8c0d`, generation SHA-256
`923439aed9bde6eba34a26bf551b2d583a247a6bec7ba00e8679b2632d6c6f41`.

All original **30 configurations were replayed unchanged**. Their baseline
outputs reproduce the preserved results exactly. The candidate holds the
previously demonstrated retractions, anaphylaxis Plan, fullwidth corrections
and family attribution. Original positive, denial, source-span and nonsmoker
controls retain their expected outcomes. Sixteen additional configurations were
predeclared and compared: **46 configurations × two versions, zero errors**.

## F1 — P1: ordinary inflections retain the prior false green

`5b95a725:rebuild/core/generation.py:1986` omits `deletes`, `removes`, and
`omission` from the record-retraction action grammar; `:1994` depends on it.

Use unique, unscoped v3 `Allergies`, `Examination`, `Plan`, `Smoker` fields and
select only the first source unit for Allergies:

```text
No known drug allergies.
Plan: clinician deletes erroneous NKA entry.
```

Both candidate and baseline return supported `No known drug allergies.` with
its exact `[0,24)` source span. A forced existing supported answer remains
supported on the page, `governed_supported` returns `null`, and
`governed_decisions` returns `[]`. The explicitly erroneous entry should be held.

The same result is preserved for:

- `Plan: clinician removes erroneous NKA entry.`
- `Plan: omission of erroneous NKA entry.`

These are **unclosed variants of the existing failure**, not regressions newly
introduced by this repair. Evidence: B05–B07.

## F2 — P2: physical removal plus documentation is newly treated as retraction

`5b95a725:rebuild/core/generation.py:1994` tests action/reference co-occurrence
without establishing that the action acts on the record. `:1990` also treats
`documented` and the verb `record` as sufficient record references.

```text
No known drug allergies.
Plan: removal of stitches documented.
```

Selecting only NKA returned supported exact text with no stored-reader warning
on the baseline. The candidate returns conflict and empty text, and both page
and finalization governance hold Allergies. Documenting a physical removal does
not retract an allergy declaration. No provider selection of the Plan is needed.

Three further new false holds are preserved:

- `Plan: removal of the temporary device documented.`
- `Plan: record removal of stitches.`
- `Plan: remove the catheter and note response.`

The contrasting control `Plan: document removal of stitches.` remains supported,
as do the nominal naproxen, formal physiotherapy and foreign-body removal
controls. Evidence: B01–B04, B08, B12–B14.

## Scope and artifacts

Additional fullwidth retraction, fullwidth/invisible `for`, conditional and
family-scope controls hold in the candidate. No source was edited, no unfinished
patient-topics diff was inspected, and no DB, provider, Word, render, corpus or
expected-map operation was performed. Socket/process operations were disabled;
zero forbidden attempts were recorded. This is pure deterministic review, not
full application finalization or qualification.

Private runtime:
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/clinical-repair-5b95a725-20260927/`.
Every input, source snapshot, raw output and runner is retained. Delta seal:
`metadata/058-CLINICAL-REPAIR-REFUTATION-DELTA-SEAL.json` under the custody root.

| Artifact | SHA-256 |
| --- | --- |
| `adjacent-cases.json` | `7f7a5ff19883082b4f3357bcf5f8cc58791aa5ded873d37af1bf6e3151209cd5` |
| `candidate-results.json` | `9de10d87e032dfd78870a50b3f7fd69ea8b6c2aaca736b32863a131e9e440b00` |
| `baseline-results.json` | `cf310de4d4895662a70432df7e67b3719b9d543b5692d573d5e946a88f8cfc11` |
| `summary.json` | `7292a65f458b03a4e37077f15958b1156003e977b4568803c8eae9b62cc29b4d` |
