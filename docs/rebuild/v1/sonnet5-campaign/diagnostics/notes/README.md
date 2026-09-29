# Ordinary-notes diagnostic set (frozen 2026-09-28; repaired and re-frozen 2026-09-29)

> **Re-frozen again 2026-09-29 after the recheck (`../RECHECK.md`), before any live notes result.** No case, form or
> expectation changed. `offline_replay.py --replay` now refuses (exit 2, nothing written) unless every file in
> `../mapping/EXPECTED-SHA256SUMS` matches and the cases are the frozen `cases.json`, and its output is
> `{"provenance": {...}, "responses": {...}}` (manifest, replay, cases, responses and candidate sha256; R2). The walk's
> steps that must stay identical to the campaign's live ordinary_notes stage — the path flags, the reference answer,
> the review save and the export verification — moved unchanged into `app_path_steps.py`, which `app_path_walk.py` and
> `rebuild/ops/sonnet5_stages.py` both import; `run_app_path_walk.py` gained `--runtime DIR` and compares `rebuild/`
> outside `rebuild/ops/`.

> **2026-09-29 repair** (after `../CHECK.md`; details in `../REPAIR.md`, sha256 of every file in `../FREEZE.json`).
> What changed for anyone scoring a live run:
>
> - **Real forms, app path.** Every case now references a real synthetic `.docx` (`build_note_forms.py`, runtime
>   directory `/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/notes/`, sha256 in `cases.json`)
>   and carries the fields exactly as the candidate's v3 inspect gives them. Field keys are the inspected keys
>   (`case_keys` maps them to the earlier readable names). The legacy engine refuses every one of these forms, so
>   the app path needs `QUILLMD_WORD_ENGINE=v3`. `app_path_walk.py` (run by `run_app_path_walk.py` on a
>   `quillmd_qa_diag_*` test database) walks all 21 sends through upload, mapping, confirm, generate (mocked
>   provider returning the reference selection), review, finalize and export; `app-path-walk.json` records it.
> - **Observations are separate.** `cases.json` holds expectations only and is frozen in
>   `../mapping/EXPECTED-SHA256SUMS` before anything is recorded; `offline_replay.py --record` refuses otherwise and
>   writes `offline-observations.json`. Every listed selection is recorded **replayed alone**; the one entry whose
>   outcome depends on the other fields (N02 `worse` forbidden[0] on field_relations) also carries its
>   with-reference outcome.
> - **Scoring step 3 is now "replay the whole response"**: `offline_replay.py --replay <responses.json>` replays
>   each live answer as returned and scores every field (matched entry, verdict). Do not look entries up one by one.
> - **Expectations:** N06 Plan's reference is the plan sentence alone (desired supported; the two-unit pick is
>   forbidden); a silent blank on a J field scores `usefulness_loss`; supported-control texts accept the full unit
>   or the stripped remainder (`desired_texts`); N11/N12 `cc`/`smoker` and N01 Examination/Assessment/Plan are V
>   (held today), not S; N03's label is fresh wording.
> - **Budget:** 16 cases, 21 sends, **$3.489524** worst case with the inspected fields at $2/$10 per million and the
>   8,000 / 20,000 output caps, counted ×1.1 (`cases.json` `budget`, per case `cost_bound_usd`).
>
> Sections below describe the checked 2026-09-28 set where they give sha256 values, counts or the old file layout.

A fixed set of 16 synthetic cases for the bounded Sonnet 5 campaign. It separates two
questions that earlier retained results could not separate:

1. **Did the model select the right complete source units?** (`raw_model_expectation`)
2. **Did the application adopt, hold or leave blank what it should?** (`app_adoption_expectation`)

It is **not** Sonnet 5 qualification, clinical-quality evidence, voice review, corpus or
holdout evidence, or Word compatibility. No corpus original was opened for it and no corpus
text is in it. Everything that would be sent is synthetic probe or adversarial-test
material already in the repository or the paused veto's adversarial record, plus two new
synthetic twins written for this set.

Candidate: `8e3dcfd07a5946430e7291b520faf35c8055127b` (worktree
`/opt/meddoc-pro/.worktrees/v1-sonnet5-diagnostics`).

| File | What it is |
|---|---|
| `cases.json` | The frozen set: forms, notes, per-field expectations, offline observations, cost bounds, sources with sha256. sha256 at freeze: `964e206e77a75a98ae5d71a86f4821ef1b4deafaf0f5576ec0806ee517369606`. |
| `offline_replay.py` | Replays every expectation offline against the checked-out candidate with a **simulated** provider. It records the observations once (`--record`, already done) and afterwards checks for drift. |

## The two paths, and which cases need the flag

| Path | Configuration | Who may run it |
|---|---|---|
| `default` | `QUILLMD_V3_FIELD_RELATIONS=0` (plus history context, batches and WM narrative off). Production default. Model returns `unit_ids` and `conflict` only. Options come only from a labelled line. | campaign |
| `field_relations` | `QUILLMD_V3_FIELD_RELATIONS=1`. Model also returns `option_ids` and one context relation per unit. This is the paused contradiction veto: 9, 6 and 8 HIGH findings in three rounds, and it stays off (`candidate-adversarial-pass-20260928.md`). | **isolated QA stack only**, never the installed app |

| Case | Name | Class | Sends | Needs `QUILLMD_V3_FIELD_RELATIONS=1` |
|---|---|---|---|---|
| N01 | r1-note4: patient predicates and history | V | default | no |
| N02 | Twin: repeated `Other:` write-in (D03 A28 shape) | V | default + field_relations | only for its field_relations send |
| N03 | Twin: copular `is subject to` statement (MAPPA shape) | V | default + field_relations | only for its field_relations send |
| N04 | r1-note1: one sentence carrying PMH and a medication | J | default | no |
| N05 | r1-note10: `He` after `His father...` | J | default | no |
| N06 | r1-note6: consent, procedure-as-examination, plan scope | J / I | default | no |
| N07 | r1-note3: unpunctuated run-on, one unit | I | default | no |
| N08 | `left knee pain` against a `Right knee` field | SIDE | default | no |
| N09 | `right knee pain` against `Right knee` / `Left knee` | SIDE | default | no |
| N10 | `The patient does not smoke.`: never `Yes` | DENIAL | default + field_relations | only for its field_relations send |
| N11 | `Allergies: penicillin. Sorry, I mean amoxicillin.` on one line | CORRECTION | default | no |
| N12 | The same correction on the next line | CORRECTION | default | no |
| N13 | R3-1 labelled `none` vs statement; R3-3 negated list | CONTRADICTION | field_relations + default | only for its field_relations send |
| N14 | R3-2 non-copular opposite; R3-4 double negation | CONTRADICTION | field_relations | yes |
| N15 | R3-5 negation across `but`; R3-7 `No MAPPA involvement.` | CONTRADICTION | field_relations | yes |
| N16 | R3-6 possessor (`Her mood`); R3-8 `Allergies: none.` vs `allergic` | CONTRADICTION | field_relations + default | only for its field_relations send |

The planned sends are 21: 14 on the default path and 7 on field_relations. N13 and N16 are
also sent on the default path because of the default-path observation below. The task scope
did not ask for that. Drop those two sends if the lead wants the veto-only scope.

Classes (from `REMAINING-51.md` / `remaining-51-classification.json` where a source row exists):

- **V**: explicit, relevant content that should be supported and is held today.
- **J**: meaning, wording or ownership needs adjudication, so it must stay held.
- **I**: a single-field positive would be invalid.
- **S / M / NR**: supported, missing and never-requested controls.

Each r1 field that came from the 51 carries its `source_row`: original selection, class and
engineering group.

## Budget

At the documented Sonnet 5 rates ($2 input / $10 output per million) the application's own
worst-case bound is:

- **provider cost max $3.154** for all 21 sends ($1.525 default, $1.630 field_relations);
- **customer hold max $4.731** (×1.5).

The bound per send is (serialized request bytes + 12,000) × input rate, plus the profile's
`max_output_tokens` × output rate. That cap is 8,000 on the default path and 20,000 on
field_relations. Each case's own bound is in `cost_bound_usd`. The total fits the $9.70 left
from the still-unapproved $10 ordinary-notes line after the $0.30 voice reservation
(`V1-EXTERNAL-REQUEST.md`). No retries are budgeted: a failed or unknown send stays failed.

## How to score a live run

Do these steps per case, per sent path and per field:

1. **Normalise the raw response.** Map the returned `unit_ids` to quotes with the candidate's
   `source_units()` for the same form and notes. For `units`, compare the set, not the order,
   because the application restores source order. Keep `conflict`. On field_relations, also
   keep the option texts (option id `key:i` is printed option `i`) and each unit's relation.
2. **Match it against the entries.** Try every `acceptable` entry first, then the `forbidden`
   entries. An entry with `paths` counts only on those paths. An entry with `relations` needs
   exactly those relations on the listed units. An entry without `relations` accepts any
   context. On the default path, options and relations are ignored. A response that matches
   nothing is **unlisted**. Adjudicate it by hand and replay it offline. Do not auto-score it.
3. **Compare the adoption with the prediction.** The matched entry's `observed_offline[path]`
   is what this candidate did with exactly that selection. A different live status or text
   means the served path diverged from the offline harness. That is a finding in itself.
4. **Attribute the outcome.**
   - A forbidden or wrong unlisted selection is a **model error**.
   - An acceptable selection that is held where `desired` is `supported` is an **application
     over-hold**. It is expected at this candidate when `hold_basis` names the path, so it is
     not a model failure.
   - Any `supported` answer where `desired` is not supported, or where a `never` item happens,
     is an **application leak**. Treat it as critical whatever the model did.

## Offline replay at 8e3dcfd0 (simulated provider, no network)

Reproduce:

```
cd /opt/meddoc-pro/.worktrees/v1-sonnet5-diagnostics
TMPDIR=/tmp rebuild/.venv/bin/python -B docs/rebuild/v1/sonnet5-campaign/diagnostics/notes/offline_replay.py \
  --state-dir <scratch>/state --out <scratch>/replay.json
```

What the script guarantees:

- **Sockets:** connect, connect_ex, create_connection and getaddrinfo raise before Django loads.
- **Environment file:** `dotenv.load_dotenv` is replaced by a no-op, so nothing reads it.
- **Database:** the host is a nonexistent local socket directory and every connection attempt
  raises.

It uses the application's own validate/adopt functions (the repository's `run()` /
`offered()` harness shape, keyed by field key) and the stored-answer review governance.

- **Exit codes:** exit 0 means no drift. Exit 1 means drift, either in an observation or in
  the sha256 of the four candidate modules. This check can fail: a copy of `cases.json` with
  one recorded status changed (N09 `right`, passed via `--cases`) gave exit 1 with drift 1.
  The real file gave exit 0 on two consecutive runs.
- **Scope of the replay:** it covers generation validation, adoption and review governance
  only. It does not cover the worker, HTTP, finalization, export, voice or Word.

Results for the reference selections (the first acceptable entry per field):

- **No leaks and no text mismatches.** Every J, I, M, NR, CORRECTION, CONTRADICTION and
  SIDE-hold field is as desired on every sent path.
- **Documented over-holds:**
  - 19 V fields on the default path, all REMAINING-51 groups;
  - N02 `Other:` and N03 copular on the default path;
  - N10 `does not smoke` on the default path, where the rule is that options come from a
    labelled line only.
- **Over-holds first seen while freezing this set** (`documented_before_this_set: false`;
  every one is reproduced by the case's `offline_controls`):
  - **N09, default path:** `The patient has right knee pain.` is held against `Right knee`,
    but `The patient has right-sided knee pain.` is supported. The requested "right knee pain
    supported" control therefore fails on the default path. It passes on field_relations
    (info replay).
  - **N11 and N12, default path:** the allergy correction also holds the unrelated Chief
    complaint and the labelled `Smoker: No.` (which comes after the correction), even across
    blank lines. Without the correction line, all three are supported.
  - **N02 `warning`, field_relations:** `The patient sees zigzag lines before the headache
    begins.` is held as a repeated question. With `reports` in place of `sees`, the same
    sentence is supported.
  - **N03 `attendance`:** `She attends the clinic every week.` is held on both paths.
    `The patient attends...` is supported on field_relations but still held on default after
    the first sentence. On its own it is supported.
- **Veto QA:** the paused veto still releases all eight R3-1..R3-8 shapes when every
  unselected unit is wrongly called `independent`. That is 8 of 8 `supported`, the same as the
  verifier's record at bf8f7b78. `v3_literal_facts.py`, `v3_field_relations.py` and
  `generation.py` are unchanged between bf8f7b78 and 8e3dcfd0.
- **Pairing check:** each finding's outcome with two findings bundled per case equals the
  verifier's standalone record (`supported`).

### Default-path exposure (new; please verify)

On the **default (production) path**, a model that does not set `conflict` gets a direct
opposite adopted:

- **Suicidal ideation:** `The patient is suicidal.` + `Suicidal ideation: none.` adopts
  `none.` in **either line order**, or adopts the statement, and the review governance keeps
  it supported.
- **Allergies:** `The patient is allergic to penicillin.` + `Allergies: none.` adopts `none.`
  when the statement comes first. When the label comes first it is held.
- **Other R3 shapes (N13 med, N14, N15, N16 mood):** the default path holds them.

This was reproduced with the repository's own `run()` helper. The same inputs with
`conflict=true` are held. The default path has no veto, so for these shapes production
safety rests entirely on the model's conflict flag. That is why N13 and N16 are also sent on
the default path.

## Hard-rule notes

- No model, provider or network call was made.
- No environment file was read, and no database or installed service was touched.
- Scratch was under the session scratchpad and has been reaped.
- The D03 twin uses new question wording and a new sentence. It takes only the shape from
  `word-writein-workflow-20260928.md` and `test_v3_field_relations.py`.
- The MAPPA twin uses a different arrangement name.

## Sources (sha256 at freeze)

| sha256 | bytes | path | drawn |
|---|---|---|---|
| `7ce1b703859d7f1251d6213441f8193de2d23183138b83b4123588e882219bee` | 189375 | `docs/rebuild/v1/patient-topics-20260927/evidence/refutation-1/04-retained-contained.json` | r1-note1/3/4/6/10 notes and the 11-field form, verbatim; retained picks |
| `66c9699806e75d9dec9492c89c2fa4754c60c5697cdeef27d70baa0b687680c9` | 20629 | `docs/rebuild/v1/patient-topics-20260927/evidence/remaining-51-classification.json` | V/J/I class, group and original selection per held field |
| `ea86fb5d5cea7b9f5d7e466bca56d4b36548b08331b137c401d8a497f1cc7639` | 8636 | `docs/rebuild/v1/patient-topics-20260927/REMAINING-51.md` | group meaning and required dispositions |
| `d1a822a7a1687113ab131a7599fb8420f21b9c860b6d620e539849973993708b` | 3253 | `rebuild/core/tests/test_v3_destination.py` | side controls |
| `dffafba6467ef1176084a9bb1c04c668b914057aba8ab8f31b716230c146759b` | 72433 | `rebuild/core/tests/test_v3_field_relations.py` | `Other:` and copular shapes, predicate options, `offered()` |
| `ad54cb8892cdd25a5871306e2fc7efdc5785d93738e06a67364bff6aaa6c6670` | 103839 | `rebuild/core/tests/test_v3_ordinary_notes.py` | denial and correction controls, `run()` / `field()` |
| `6ca4275784d66f4776161110a0807de9a1d5ce6203a686d78b99123de70a20eb` | 33391 | `rebuild/core/tests/test_generation_batch.py` | batch side gap, signing field never requested |
| `016263a9a2c4733fd2b9ca9e04ed13112f05d59581e81ca724546c30deb05447` | 126181 | `/opt/meddoc-pro/rebuild/.runtime/v1-full-release-20260928/adversarial-pass-bf8f7b78/result.json` | lens `copular-r3`, R3-1..R3-8 inputs, expectations and verifier reproduction |
