# Word holdout — first pass for candidate 1 (retained; never replaced)

Evaluated once, 2026-09-27 05:47:19–05:48:13Z, after the freeze commit `cca2aa20` (pushed 05:47:11Z).
Engine `79a5b2ec` (`word_v3.py` sha256 `db227329…a93a72`), harness as committed in `word-eval/`.
Results file (sealed corpus directory): `results/holdout-79a5b2ec6597-first-pass/results.json`,
sha256 `59ee50e29a882443c9c9a34bb3f1ef9562d988a8aad7e92eae98dc505283354f`.

## Result

| measure | holdout (20) | target |
|---|---|---|
| automatic document success | **0 / 20** (tolerant 0 / 20) | ≥ 18 / 20 |
| detection strict-correct | 0 / 20 | — |
| exports clean (empty, ordinary, long) | 18 / 20 | — |
| areas correct / total | 386 / 1171 (155 missed, 630 wrong); 389 extra fields | — |
| per family | 0 successes in every family F1–F10 | ≥ 75% each |

**The deterministic candidate does not meet the V1 Word release gate.** Its development score (2023/2651 areas,
3/40 documents) did not carry over: on unseen forms most areas are found but classified or grouped wrongly
("wrong" 630), and every document has at least one error.

## Release-blocking defect found

- **Corrupted control (H08):** filling a content control that itself contains other content controls replaced
  its whole content and removed 32 nested controls (structure check: 150 → 118 content controls). The export
  check caught it before any render. It must be repaired before any Word export is enabled. The repair is
  judged on the qualification cohort, not on this holdout.

## Per document

| doc | format | declared families | areas correct | missed | wrong | extra | export clean |
|---|---|---|---|---|---|---|---|
| H01 | docx | F1 F10 F2 F4 F5 F6 F8 F9 | 7/12 | 1 | 4 | 76 | yes |
| H02 | docx | F1 F10 F2 F4 F5 | 17/30 | 2 | 11 | 10 | yes |
| H03 | doc |  | 32/58 | 0 | 26 | 30 | yes |
| H04 | docx | F1 F10 F2 F5 F6 F9 | 5/17 | 2 | 10 | 9 | yes |
| H05 | docx | F1 F10 F2 F5 F9 | 6/11 | 4 | 1 | 36 | yes |
| H06 | docx | F10 F2 F3 F8 F9 | 33/33 | 0 | 0 | 38 | yes |
| H07 | docx | F10 F2 F3 F8 F9 | 27/31 | 3 | 1 | 27 | yes |
| H08 | docx | F10 F2 F3 F4 F5 F6 F8 F9 | 54/59 | 0 | 5 | 12 | no |
| H09 | docx | F2 F4 F5 F6 F7 F8 F9 | 0/17 | 15 | 2 | 8 | yes |
| H10 | docx | F5 F7 | 8/11 | 3 | 0 | 12 | yes |
| H11 | docx | F1 F5 F7 | 5/10 | 5 | 0 | 3 | yes |
| H12 | docx | F10 F2 F4 F5 F7 | 8/13 | 4 | 1 | 1 | yes |
| H13 | docx | F1 F5 F6 | 0/23 | 22 | 1 | 14 | yes |
| H14 | docx | F10 F2 F4 F6 F7 | 4/12 | 8 | 0 | 1 | yes |
| H15 | docx | F1 F5 F7 F9 | 4/10 | 5 | 1 | 4 | no |
| H16 | docx | F1 | 2/9 | 7 | 0 | 2 | yes |
| H17 | docx | F5 | 2/11 | 9 | 0 | 2 | yes |
| H18 | docx | F1 F10 F2 F3 F4 F5 F6 F9 | 68/487 | 58 | 361 | 34 | yes |
| H19 | docx | F1 F10 F2 F3 F4 F5 F6 F9 | 58/265 | 7 | 200 | 33 | yes |
| H20 | doc |  | 46/52 | 0 | 6 | 37 | yes |

(`.doc` rows were converted to `.docx` by LibreOffice before inspection; their families were not declared
because the collectors measured OOXML only.)

## Consequence

Per the predeclared protocol this first pass stands. A repaired or extended candidate — the H08 control
repair, and above all a bounded model-assisted mapping layer — is judged on the **qualification cohort**
(20 predeclared documents, not yet opened), with every attempt reported. Until a candidate passes there,
custom Word upload can offer only **assisted completion**: the clinician reviews and corrects the proposed
mapping, which is recorded as manual and never counted as automatic success.
