# Custom Word compatibility matrix — preserved candidate 1 engine results

## Recovery correction — 2026-09-27

The table below is the **historical engine proxy** on frozen candidate `79a5b2ec`, not complete
upload → mapping → generation → correction → finalization → export acceptance. The app integration was
built later. Its original scorer did not verify checkbox correctness, and native Microsoft Word acceptance
has not run. Preserve the original results and render files unchanged; do not upgrade their meaning.

A metadata-only audit also found **44 declared independent lineages across the 60 files** (30 development,
14 holdout), despite 60 distinct file hashes and 26 source groups. At most two files per lineage were allowed
by the original selection rule. This does not establish the owner's 60 independently authored templates.
The source/lineage sets are disjoint; authorization bases are recorded. Provenance clarification or a
separately declared supplemental cohort is needed without replacing any failed original case. The frozen
manifest's `coverage` totals count lineages; the family denominators below count tagged files. Those two
units must not be interchanged. Legacy `.doc` cases without family tags stay in the document denominator.

The target remains **54/60 overall, 18/20 holdout, 75% in every declared family**, with independent examples,
all answer profiles, rendered comparisons, full app workflow and native Word checks. It is unmet. The
reserved qualification contents remain unopened; metadata inspection is not model or parser qualification.

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

## Historical assisted-path description — not a corpus-wide qualification

The engine proposes fields across all ten families. Synthetic regression checks exercise corrected mappings,
untouched-part identity and unfilled signature/initials areas. This is not proof that every corpus document
completes the app workflow. Where a page
cannot grow (headers, footers, text boxes, narrow or fixed-height cells), answer length is bounded instead of
overflowing. Known limits: bulleted lists without blanks, printed option words to circle mid-paragraph,
floating initials boxes anchored in another row, and author placeholders are misread or missed. The clinician
must correct these in review.


## Additional metadata correction — Astra continuation, 2026-09-27

The sealed qualification set also has **20 files but only 12 declared lineages** (eight pairs), across 6
source groups. Development has 40 files / 30 lineages and historical holdout 20 files / 14 lineages. This is an
audit of manifest metadata only: qualification document/ground-truth contents remain unopened.
The original manifest and every historical result remain unchanged. File hashes alone do not establish
independent authorship, so the reserved cohort is **not yet eligible evidence of 20 independent templates**.
Any supplemental selection must be predeclared by lineage/source before outputs, retain the original
manifest and attempts, and report its own denominator. Nothing here replaces a failed case or resets a result.
A metadata-only development supplement proposal exists but does not resolve qualification independence.
See `corpus-lineage-metadata-20260927.json`; no new compatibility score is claimed.


## Continued D30 long-question repair — September27

Reviewed source cf04596e retains complete bounded questions/context (1,000 Unicode code points) across detection, manual mapping and assistance. D30 changes from68 to71 detected fields; prior68 are preserved apart from document-order keys. A23/A35 long questions and A44 report-reference box now map. A21 option ownership, A26 cross-question dependency and A40 manager-only section remain visibly unresolved. Whole document: **FAIL**. A35 ordinary source remains held; correction/finalization/export succeeds only as assisted completion. Missing/ordinary/long export evidence and six changed LibreOffice renders are retained; native Word remains unperformed. See `d30-long-question-repair-20260927.md` and independent reports. No original or unseen denominator, first-pass result, or corpus qualification status changes.
