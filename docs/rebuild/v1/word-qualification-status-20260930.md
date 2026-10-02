# Word qualification — status, development-set census and the precision attempt (2026-09-30)

**The Word gate is not met and no unseen set was opened.** Criteria (unchanged, `word-compatibility-target.md`):
60 forms from ≥10 sources, 40 development / 20 unseen, ≥54/60 overall and ≥18/20 unseen, ≥75% per family, the
actual app workflow, native Word acceptance by the owner. Holdout, reserved Q20 and the fresh N20 cohort were not
opened by any candidate or harness; nothing was relabelled.

## Why unseen qualification was not started

- The development set predicts failure: on the 33 rights-supported development forms the candidate's engine reaches
  strict detection on **3 of 33** (D02, D09, D13; 1,730 of 2,253 answer areas; 808 extra fields). Opening N20 now
  would spend the only unseen cohort on a known failure.
- N20 contains three OLE2 `.doc` originals and the candidate refuses `.doc` (conversion by FOSS tools was rejected
  earlier for demonstrated content/control loss), capping N20 at 17 of 18 required.
- Seven N20 files are byte-identical to reserved Q20 files and ten lineages overlap, so only one of the two can serve.
- The development set itself has at most 26 of 40 independent lineages; the corpus independence requirement and
  native Word acceptance are external (independently authored corpus; owner's Word session).
- Rights: all 40 development originals are "no provider upload"; seven are held from filled replay and were not
  processed in this work.

## Census of development-set misses (candidate 43fcf214, 33 forms, offline)

Every miss, extra field and export failure has one engine-level cause (tables in
`rebuild/.runtime/v1-product-20260930/c/word-census/`):

| class | areas / extras | forms blocked |
|---|---|---|
| K1 claim order swallows blanks | 87 / 2 | 9 |
| K2 box-option grouping | 76 / 5 | 9 |
| K3 cardinality | 20 / 0 | 6 |
| K4 option marks not seen | 69 / 20 | 10 |
| K5 empty-cell roles | 26 / 150 | 13 |
| K6 layout witness (D10) | 119 / 0 | 1 |
| K7 signing-block structures | 10 / 3 | 5 |
| K8 no answer space after a label | 50 / 1 | 13 |
| K9 unrecognised placeholders | 33 / 0 | 7 |
| K10 bracket/angle placeholders in prose | 0 / 94 | 8 |
| K11 non-answer text read as answers | 5 / 204 | 20 |
| K12 one area as several fields | 13 / 319 | 7 |
| K13 several areas as one field | 15 / 0 | 5 |
| K14 protected areas surfaced as fields | 0 / 10 | 2 |
| K15 cell_append adds a paragraph (export check) | — | 4 |

**Safety exposure on real development forms** (release-blocking "wrong destination" class): five signature/initials
areas are mapped to fillable fields (D15, D17, D18, D36 ×2) and 63 extra fillable fields sit inside signature blocks
or consent text. The integrated destination roles do not close these, because they are the engine's own mislabels;
every generated answer is still clinician-reviewed before finalization, and model-assisted mapping stays off.

## The precision attempt (not integrated)

`fix/v1-word-precision` (pushed, `3b508a21`) implemented K7, K10, K11, K14, K15 and a K5 subset as structural and
wording rules: strict detection 3 → 6 of 33, areas OK 1,730 → 1,752 with none lost, extras 808 → 613, signing
exposure 5 → 0, consent-text extras 63 → 4, v2.1 passes 8 → 9. Refutation confirmed 22 regressions against 43fcf214
in round 1 and about 18 more after the repair (for example a date written on the line of 'Patient signature [or
guardian]: ___ Date: ___'; 'Countersigned by (name)' and 'Reviewed by' becoming unwritable signatures; 'Other [If
other, please specify]' fields dropped). Every wording class regressed, so it was not integrated. The next attempt
should flag such places for clinician review without changing their kind (hold-only), and needs its own refutation.

## Per-document evidence

`rebuild/.runtime/v1-product-20260930/a1/word-qual/word-qual-matrix.json` (all 40 development forms by evidence class:
frozen harness, v2.1 ticked, v1 legs, app replays; holdout/Q20/N20 listed with no candidate evidence) and the census
per-form blocking classes. D30/D31 app replays on the integrated candidate are reported in the qualification report.
