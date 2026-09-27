# Custom Word compatibility matrix — candidate 1 (deterministic, frozen 79a5b2ec)

Measured 2026-09-27 on the frozen corpus (`word-corpus-manifest.json`). The scoring was declared before any
change (`word-compatibility-target.md`). A document counts as an automatic success only if every
ground-truth area is correct, the three answer profiles fill, and every export is faithful. Tags overlap. The
LibreOffice render is evidence; native Word acceptance is a separate, owner-run check.

| family | dev success / cases | holdout success / cases | dev areas correct | holdout areas correct |
|---|---|---|---|---|
| F1 paragraph labels / blanks | 1 / 17 | 0 / 10 | 548 / 831 | 172 / 874 |
| F2 two-/multi-column | 1 / 28 | 0 / 12 | 1761 / 2259 | 287 / 987 |
| F3 merged/nested tables | 0 / 20 | 0 / 5 | 1539 / 1949 | 240 / 875 |
| F4 mixed layouts | 1 / 27 | 0 / 8 | 1654 / 2114 | 216 / 895 |
| F5 multi-page | 3 / 38 | 0 / 14 | 2012 / 2613 | 242 / 976 |
| F6 repeated labels | 1 / 28 | 0 / 8 | 1573 / 2093 | 196 / 892 |
| F7 text boxes | 0 / 9 | 0 / 6 | 152 / 265 | 29 / 73 |
| F8 content controls / dropdowns | 0 / 3 | 0 / 5 | 130 / 192 | 121 / 152 |
| F9 checkboxes | 2 / 13 | 0 / 10 | 1098 / 1289 | 262 / 942 |
| F10 header/footer fields | 3 / 29 | 0 / 11 | 1741 / 2201 | 287 / 970 |
| **all documents** | **3 / 40** | **0 / 20** | 2023 / 2651 | 386 / 1171 |

Exports clean under empty/ordinary/long answers: dev 31/40, holdout 18/20.

**Target:** ≥ 54/60 overall, ≥ 18/20 holdout, ≥ 75% within every family. **Not met.** The qualification cohort
(20 documents) is unopened and reserved for the next candidate.

Per-template evidence is retained outside scratch, in the sealed corpus directory
`rebuild/.runtime/v1-word-corpus/results/`:

- `dev-79a5b2ec6597-frozen/` and `holdout-79a5b2ec6597-first-pass/`: `results.json` (per document, the reasons
  for failure);
- `detect/`: the fields found for each template;
- `filled-{ordinary,long}/`: synthetic exports and the answers used;
- `render-{ordinary,long}/`: the LibreOffice PDFs.

Ground truth: `{dev,holdout,qual}/groundtruth/`, sealed by `GROUND-TRUTH-SEAL.txt`.

## What works today, with a clinician confirming the mapping (assisted completion — not counted above)

Every tested document inspects safely. Detection proposes fields for all ten families. With corrected mappings,
exports keep untouched parts byte-identical, and signature and initials areas are never filled. Where a page
cannot grow (headers, footers, text boxes, narrow or fixed-height cells), answer length is bounded instead of
overflowing. Known limits: bulleted lists without blanks, printed option words to circle mid-paragraph,
floating initials boxes anchored in another row, and author placeholders are misread or missed. The clinician
must correct these in review.
