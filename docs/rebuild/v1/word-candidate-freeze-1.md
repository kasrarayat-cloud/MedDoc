# Word candidate freeze 1 — recorded before the holdout is evaluated

Written 2026-09-27, before any holdout or qualification-cohort candidate output exists. The commit that
adds this file is the freeze: its timestamp precedes the holdout run.

## What is frozen

| item | identity |
|---|---|
| engine (contract v3 detector + writers) | `rebuild/documents/word_v3.py` at `79a5b2ec659751328b7ef9cf824960c926b68aff` (branch `v1/word-engine`), file sha256 `db2273293576a4991c46bba64d716070474ba8eab8a6cb897106d7bb1ca93a72` |
| evaluation harness | `docs/rebuild/v1/word-eval/` in this commit: `final_eval.py`, `score.py`, `fill_eval.py`, `render_eval.py` |
| ground truth | 80 reviewer-final files, sealed read-only; `GROUND-TRUTH-SEAL.txt` sha256 `57177ecbd114d752963ae59b14cb4e905c4694275162d3161089afcf81104791` (per-file hashes inside, in the sealed corpus directory) |
| corpus | `word-corpus-manifest.json` (sealed full manifest sha256 `450c0a6a…4f`) |

The candidate is **deterministic only**: no model is used for detection or mapping.

## Scoring as run

`final_eval.py` implements the predeclared scoring in `word-compatibility-target.md`. A document is an
automatic success only if detection is strict-correct (every ground-truth area at the right destination with
the right kind class and option count, duplicates disambiguated, no unmatched detected field), AND the fill
succeeds for empty, ordinary and long answer profiles, AND each export passes the checks. The export checks are:

- package entries unchanged except touched parts, and structure counts equal;
- untouched text identical, printed text kept in order;
- every text answer visible in a LibreOffice render;
- no new overprinting.

A tolerant variant allows at most max(2, 10%) extra detected fields. It is reported separately and never
substituted.

Harness corrections made during development, all before this freeze:

- one field written to every copy of a repeated header satisfies each copy's area;
- captions in all capitals and rows that break across pages do not count as invisible answers (the
  visibility probe ignores case and whitespace);
- guidance paragraphs the form says to overwrite are expected to go.

## Development result for this candidate (40 documents; the development set is not a holdout)

| measure | result |
|---|---|
| automatic success | **3 / 40** (tolerant 4 / 40) |
| detection strict | 3 / 40 |
| exports clean under all three profiles | 31 / 40 |
| areas correct / total | 2023 / 2651 (421 missed, 207 wrong); 1411 extra detected fields |
| per family (success / cases) | F1 1/17 · F2 1/28 · F3 0/20 · F4 1/27 · F5 3/38 · F6 1/28 · F7 0/9 · F8 0/3 · F9 2/13 · F10 3/29 |

This is far below the ≥90% target. The holdout is still evaluated once now. Its purpose is an unbiased
measurement of the shippable deterministic candidate, not a claim that it passes.

## What happens after

- The holdout result is retained as first-pass evidence and never replaced.
- Any later candidate — including a model-assisted mapping layer, which needs separate spending authority
  before it can be measured — is judged on the **predeclared qualification cohort** (20 documents). Every
  attempt and failure is reported.
- Manual mapping corrections in review are **assisted completions**: useful recovery, never counted as
  automatic success.
