# D31 structural destination ownership — 2026-09-28

Base: `7e370d5ba2e722e9fe1d55772b88211916af8992`. Isolated branch `fix/v1-d31-layout-ownership`. No installed data, DB, provider, renderer or network calls were used.

The original D31 blank template has SHA256 `f730aa53671ab367eb5e89376d653ef0d51f096962ae616480711a292eeed36d`. Its independent expected map is `docs/rebuild/v1/word-table-ownership-evidence-20260927/D31-expected.json`. Baseline inspection and original XML structure were saved before source changes.

## Demonstrated failures and scope

Five baseline destinations were false positives: title spacing `b/tbl[0]/tr[0]/tc[0]/p[3]`, the empty logo/layout cell `b/tbl[0]/tr[0]/tc[1]`, already-owned labels at `b/tbl[38]/tr[0]/tc[0]/p[0]` and `b/tbl[41]/tr[0]/tc[0]/p[0]`, and residual continuation cell `b/tbl[54]/tr[1]/tc[3]`. Baseline keys were v3_1, v3_2, v3_41, v3_47 and v3_60 respectively. Exact fresh inspection changes 66 fields to 61; every retained field is unchanged except its sequential key. Cardinality is not a whole-form semantic qualification.

The two label phantoms arose because printed guidance ending in a question mark was mistaken for another label despite its existing answer-cell mapping. The same omission affected a plain question cell above a mapped answer. The fix uses actual adjacent ownership for sole plain labels. An explicit blank/control is retained.

Two separate exclusions are intentionally narrow. A single-row unruled presentation band must contain at least two centered visible headings in one cell, no question/field markers, and only plain empty spacing elsewhere. Its borders must be explicitly invisible on a known white background. The continuation tail must be unmarked, beside only vertical-merge continuations, directly below an already-owned complete answer box, and have only a shared top edge. No row-height threshold is used. Conditional or unknown styles, theme borders, duplicate property containers, non-white shading and incomplete border information cannot establish either exclusion. The tests include boxed answers, explicit blanks, question text, shaded backgrounds, unresolved styles, theme colours, duplicate properties, marked spacing and non-merged neighboring labels.

No writer, provider, financial, admission, scanner or source-policy code changed. Parent integration owns hyperlink guidance, Annex B examples and tiny legacy controls; those remain outside this diff. The earlier no-op ZIP-identity repair is also outside this base: all-blank export here retains every part byte but repacks the ZIP, explicitly recorded as archive identity false.

## Evidence

Ignored evidence is retained at `rebuild/.runtime/d31-layout-20260928/`:

- `baseline-inspection.json`, `original-relevant-structure.json` and `baseline-controls-01.log`: original failures; four synthetic methods produced five failing subcases before the source fix.
- `focused-01.log`: 46 question-box methods pass. `focused-02.log` is an unchanged duplicate run after a shell working-directory mistake prevented an intended edit; it is not counted as new coverage.
- `affected-01.log`: 119 methods pass in 59.090 s across Word v3, guidance, document relations and hyperlinks. This ran before the final additional conservative duplicate-property/visibility guard.
- `focused-03.log`: final source 46 methods pass in 18.441 s, including extra theme, duplicate-property and marked-spacing controls.
- `original-witness.py`, `original-witness-03.log` and `original-witness-01.json`: final original replay. The prior successful JSON is preserved separately as `original-witness-02.json`. First log `original-witness-01.log` is a preserved harness import failure; adding explicit local PYTHONPATH fixed the invocation.

The original replay checks exact locator differences, all remaining mapping attributes, and exports two synthetic reviewed answers to the real Capacity Issues and index-offence guidance cells. After removing only those two appended paragraphs, whole document XML equals the original. All 32 other package parts match exactly. The original title, labels, continuation cells and valid upper submission-date cell remain unchanged. A previously saved baseline mapping exports identical answer XML. The original package is unchanged.

Independent finished-diff refutation is required before integration. These checks qualify the bounded five-destination correction, not the complete D31 clinical workflow or every visual table layout.
