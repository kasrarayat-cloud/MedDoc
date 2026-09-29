# Sonnet 5 qualification: MAPPING-stage diagnostic set

> **Re-frozen again 2026-09-29, after the independent recheck (`../RECHECK.md`) and before any live mapping result.**
> Grader-only repairs; no map, form or expectation changed.
>
> - **R1 — a slot record over a kept wrong field is not a hold.** `grade_app_path.grade_output` grades `held_safe`
>   only when a covering field is held by a not_answer/uncertain FIELD verdict or a KEYED record, or when no field
>   covers the area and a record lies on its destination. A covered area touched only by slot-level records is graded
>   by its covering field (the kept leaked label, one-choice list or single choice is `wrong`), with `hold` recorded
>   and `hold_reaches_field: false`; the summary counts them (`areas_slot_record_over_kept_field`). The self-test adds
>   a `slot_only` response per form and four assertions (the recheck's probe, and the app's own fixture).
> - **R2 — the live graders enforce and record the freeze.** `--grade` and `--self-test` (and the notes
>   `offline_replay.py --replay`) refuse, exit 2, writing nothing, unless every file `EXPECTED-SHA256SUMS` lists
>   matches and every expected map is listed (`../freeze_check.py`, the one implementation); what they write carries
>   `provenance`: the manifest's sha256, the grader's own sha256, each input's sha256 and the candidate (commit,
>   whether `rebuild/` outside `rebuild/ops/` still equals it, the engine files' sha256).
> - **R3 — f6b's note is exercised.** Its administrative `source_note` (all five answers missing) is sent: the mapping
>   stage's plan (`rebuild/ops/sonnet5_stages.py`, `plan --stage mapping`) confirms f6b's proposed mapping and
>   generates it with exactly that note, then checks that nothing is filled; f6a is generated with `long-answer.txt`
>   and checked for the whole answer.
> - Tests: `rebuild/ops/tests/test_stage_graders.py` (subprocess; the recheck's f5.C2 positive control included).

> **Repaired and re-frozen 2026-09-29** after the independent check (`../CHECK.md`); what changed and why is in
> `../REPAIR.md`, and `../FREEZE.json` lists the sha256 of every file. In short: eight forms (the new twin `f2b`
> tests the leave list without the engine's special owner word), fresh wording where a provider-bound string shared
> a 25-character normalized window with development text (`wording_check.py`, `wording-check.json`: CLEAN, with a
> positive control on the checked sets), `must_not_name` on f1.A2, f4.A8 and f4.A15, an f6b note that answers
> nothing, a real fill and read-back of a 5,835-character answer (`long_answer_readback.py`), and a grader for the
> OUTPUT OF THE APP PATH (`grade_app_path.py`): it reads `validate_proposal`'s fields AND its review record, grades
> right / held_safe / wrong / missed / false_field, and marks what the model path cannot express at 8e3dcfd0.
> `EXPECTED-SHA256SUMS` now freezes the maps, the graders and the notes cases together. Sections below that give
> counts, sha256 values or file lists describe the checked 2026-09-28 set unless they say otherwise; the current
> numbers are in `baseline-deterministic.json` and `app-path-selftest.json`.

These are synthetic blank Word forms. Each one reproduces a mapping structure that failed, or nearly failed, on a
development original, and each comes with an independent expected map. The set is for the app-level Claude
Sonnet 5 qualification of **model-assisted mapping**: it measures how the model proposes answer areas on
structures where the deterministic v3 engine is known to be weak. The set is diagnostic information only. It is
not a gate, not the holdout, not native Word, and it changes no denominator of the Word gate (B-W1).

## Why the forms are synthetic (rights)

The rights reconciliation of the 40 development originals allows private offline replays. It does not allow
sending original content to a model provider (`original-development40-rights-reconciliation-20260927.md`;
V1-BLOCKERS B-W1: "Original development40 rights now support33 private offline replays/7held"). A diagnostic
built for a live Sonnet 5 request therefore cannot contain any original. So:

- **No development original was opened** to write this set. The structures come from the tracked findings
  documents listed below. Those documents describe structure, and none of their original form text was copied.
- **All wording is new.** The only fixed strings are the generic instruction phrases that the campaign plan
  itself names: `(please tick one)`, `(one box only)`, `Tick all that apply`, `You may tick more than one box`,
  `Select up to 3`, `Route (e.g., po)`, `Recipient(s)`, `Describe any abnormality`,
  `Normal / Abnormal / Not examined` and `Left knee / Right knee`. Where a findings document quotes an original
  owner line, such as D31's leave-list owner, the synthetic form uses different words for the same structure.
- The forms are **blank** and contain no patient data. The one note in the set, the administrative note in
  `f6b-admin-missing.expected.json`, is synthetic and was written here.
- The `.docx` files are written to the gitignored runtime directory
  `/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/mapping/` and are never tracked. They can be
  rebuilt byte for byte (see Reproduce).

## The forms and where each structure comes from

| Form | Structure reproduced | Origin finding | Where the finding is recorded |
|---|---|---|---|
| `f1-guidance-confirmation` | A yes/confirmation answer cell. **Blue** author guidance is printed in its first paragraph, and the answer goes in the empty paragraph **below** it. The guidance must be preserved. A plain date cell sits beside it. | **D31** (MAPPA confirmation row; guidance erased by `cell_replace`/all) | `patient-copular-20260928.md`, `guidance-preservation-20260928/REPORT.md`, V1-BLOCKERS (D31) |
| `f2-leave-checkboxes` | **Nine legacy `FORMCHECKBOX` fields** (`w:fldChar` begin/instr/separate/end), one per paragraph in nine consecutive paragraphs, under an owner line. No choose-one instruction applies, so this is a genuine multi-select. It follows a **separate** question printed `(please tick one)`, which is a genuine select-one, with a spacer and a heading in between. | **D31** (community-leave list mapped as one choice; the earlier tick-one table must not govern it) | `native-checkbox-history-20260928/REPORT.md`, V1-BLOCKERS (D31) |
| `f3-selection-instructions` | The selection-instruction family: `(one box only)`, `Tick all that apply`, `You may tick more than one box`, and `(select up to 3)`, which is a **documented usefulness-loss control**. Also a box column headed `Select up to 3` (D28-like), a blank medicines table with a `Route (e.g., po)` column (D35-like), and an ambiguous plural owner `Recipient(s)` with no instruction (D07-like). | **D28**, **D35**, **D07** (and the structural selection rule) | V1-DECISIONS 2026-09-28 (structural fail-closed cardinality); `word-eval/v2/candidate-live-20260928.md` (D07 A20, D28); `V1-WORKFLOW-CONTINUATION-20260928.md` (D28 max-3 diagnoses); `word-harness-v2.md` (D35 A15/A16 carry no options) |
| `f4-exam-grid` | An examination form. A **pulse grid** of Radial / Femoral / Dorsalis pedis × Left / Right, with blank value cells. **Numeric-coded legacy-checkbox columns** (`Label⇥1 ☐⇥2 ☐`) sit under a literal header line (`⇥Normal⇥Abnormal`) on centred tab stops. Two **unlabelled summary rows** (Normal / Abnormal / Not examined) are owned by their cell title. Two **comment cells** print `Describe any abnormality` **above** an underscore answer line. | **D10** (pulse values mapped as choices, checkbox codes exposed as labels, omitted summary controls, omitted or leaking comment instructions) | V1-BLOCKERS (D10), `d10-containment-witness-20260928.md`, `d10-layout-witness-20260928/REPORT.md` |
| `f5-negative-controls` | A guidance-only paragraph with no answer area; a **Left knee / Right knee** findings pair (the only genuine answers); a consent declaration with a legacy checkbox; a signature line; an initials box. | D25 (signing area), **D31** (protected guidance control, attestation roles), the F1 `c781024d` side-label class and the "left knee pain accepted into a Right knee field" class | `word-eval/v2/candidate-live-20260928.md`, V1-BLOCKERS |
| `f6a-long-answer` | A date blank and **one large free-text cell** for an answer longer than 5,000 characters. | **D30** (long activity text, 12→15 pages) and **D31** (5,556-character long comment), long-answer render class | V1-BLOCKERS (D30/D31 long mode), `d30-long-question-repair-20260927.md` |
| `f6b-admin-missing` | A clinical wound-review form (write-in, measurement, one-box-only choice, date, single legacy checkbox) paired with a purely **administrative** note. Every answer is expected to be missing. | **D30/D31** "missing" workflow mode | V1-BLOCKERS (D30 "missing" replay; D31 missing/ordinary/long) |

The MAPPA confirmation structure is recorded against **D31** in the tracked documents, not D30. D30 contributes the
long-question/long-answer and missing-mode structures (f6a, f6b).

## Files

| File | What it is |
|---|---|
| `build_forms.py` | Deterministic generator. Writes the seven `.docx` files and prints their sha256 (`--check` builds twice in memory and compares). It uses python-docx and lxml only, with no engine, no network and no model. |
| `<form>.expected.json` | The **independent expected map** for each form. It was written by hand from the generator's intent **before any engine run** on the form. |
| `check_expected.py` | An **engine-free** structural check of every expected map against the generated forms. It uses zipfile + lxml and never imports QuillMD code. It checks that each destination slot and control exists and is of the stated kind, that each label/option/preserved text is printed where the map says, and that no control is claimed twice. |
| `EXPECTED-SHA256SUMS` | The expected maps' sha256, frozen **before** the first engine measurement. |
| `measure_baseline.py` | Runs the candidate engine **only to measure** (`documents.word_v3.inspect` and `Detector(layout_proposal=True)`) and grades both paths against the frozen expected maps. It refuses to run if any expected map differs from the manifest. |
| `baseline-deterministic.json` | The pre-model baseline: what the deterministic path already gets right, gets wrong or misses, per area and per control, with extras. It also records the expected maps' sha256. |

## Expected-map schema (`quillmd-sonnet5-mapping-expected/1`)

Slot paths use the neutral grammar that the v3 contract documents for ground truth:
`b/p[n]`, `b/tbl[i]/tr[j]/tc[k]/p[n]`, `…/ff[f]` for a legacy form field, `…/sdt[s]` for an inline content
control, and `…/glyphs#g` for the g-th printed ☐ in a paragraph.

**Areas** (`areas[]`) are genuine answer areas:

- `id` and the printed `label`, verbatim. For grid cells, `printed_on_form` gives the row and column labels.
- `kind`: one of `text`, `long_text`, `choice`, `multi_choice`, `checkbox`, `date`, `measurement`.
- `options`: verbatim and in print order.
- `cardinality`.
- `destination`, with a prose `description` and then either:
  - `controls` for boxes, plus `option_slots` when the option words are printed elsewhere (a literal header, a
    row label), or
  - `region`/`answer_at` for write-ins, plus `preserve` for printed text in the same cell that must survive.
- Identity checks: `must_name` tokens must appear in the label or context. `must_not_name` tokens (the other
  side) must not appear in the label.
- Optional fields: `options_must_not_include` (response codes), `min_capacity_chars`, `if_held`, `table_group`
  and `expected_answer`.

**Controls** (`controls[]`) are places where the correct behaviour is to refrain:

- `not_an_answer`: no answerable field may be anchored there. Used for guidance, literal headers, instruction
  lines and headings.
- `must_refuse`: the place is a signing, attestation or consent act. It must be absent from the answerable fields,
  or present only as a protected/signature/initials area. With `applies_to`, the control is relational (the knee
  pair): no single field may cover both sides, and each label must name its own side and not the other.
- `must_hold`: the printed rule cannot be represented. The field contract has no selection limit, so
  `Select up to 3` cannot be expressed. The right outcome is a hold for the clinician, and
  `intent_if_representable` records what the form actually asks. These two `must_hold` controls (f3.C1, f3.C2) are
  the **documented usefulness-loss controls** of the structural cardinality rule (V1-DECISIONS 2026-09-28). A hold
  here is expected and is not a defect.

`f3.A4` (`Recipient(s)`) is multi-select by intent and ambiguous in print. A multi_choice is right. A hold is
safe and is recorded as `held_safe` (a usefulness loss). A single choice is **wrong**, because it refuses a
valid two-recipient answer (D07 A20).

`f3.A5..A16` form a `table_group`. Either twelve separate write-in cells, or **one** `table_rows` field over the
same table, rows and columns, is correct. A Route cell turned into a choice built from the `(e.g., po)` example
is always wrong.

## Grading (fixed in `measure_baseline.py` before its first run, and copied into the baseline)

An engine field **covers** an area when it shares a box with the area (a `cell` box ref covers the boxes inside
that cell), or when its anchor slot lies in the area's region. A `table_rows` field covers every cell in its
rows × columns.

- **right**: exactly one covering field, and all of the following hold:
  - its kind is accepted:

    | Expected kind | Accepted engine kinds |
    |---|---|
    | text | text, long_text |
    | long_text | long_text, text |
    | measurement | text, long_text |
    | date | date |
    | choice | choice |
    | multi_choice | multi_choice |
    | checkbox | checkbox |

  - it is answerable;
  - its boxes are exactly the expected controls, in order;
  - its options are verbatim and in order, with no response codes;
  - its identity tokens are present;
  - it preserves guidance. Accepted targets are `cell_append`, `cell_replace` with `all`, or a paragraph/span
    on the answer line. A plain `cell` target rewrites the first paragraph, so it fails where that paragraph
    holds preserved text;
  - its capacity is not below `min_capacity_chars`.
- **wrong**: covered, but some condition above fails, or the field also covers another area.
- **missed**: no covering field. When the map says `if_held: safe_usefulness_loss`, the outcome is recorded as
  **held_safe** instead. Engine notes that name the area's slots are quoted as evidence of a deliberate hold.
- **Controls** are graded `right` or `wrong` using the definitions above.
- **extra**: an answerable field that covers no expected area and no control. These are false fields such as
  spacers and headers.

Two self-checks were run before the engine measurement. `check_expected.py` catches planted slot, option, kind,
double-claim and label errors, and passes the unchanged map. The grader classified hand-made field lists exactly
as planted: right, wrong, missed, held_safe, extras, preservation, codes-as-options, pulse-as-choice, the capacity
limit and the `table_rows` equivalence.

## Pre-model deterministic baseline (recorded 2026-09-28T23:51:43Z, after the freeze at 23:51:34Z)

The run used candidate `8e3dcfd0` (`word_v3.py` sha256 `4e2ea03d…`, engine files clean), with sockets denied
in-process and verified by a positive control. It called `inspect` and `Detector(layout_proposal=True)` only.
The expected maps matched `EXPECTED-SHA256SUMS`. Full per-area and per-control results, raw fields, notes and the
grading rules are in `baseline-deterministic.json`. The file as the script wrote it had sha256 `27fadbb9…`; a
separately labelled `post_hoc_verification` section was added afterwards.

| | areas right | wrong | missed | controls right | wrong | answerable extras |
|---|---:|---:|---:|---:|---:|---:|
| `inspect` | 35 / 45 | 1 | 9 | 22 / 23 | 1 | 0 |
| `layout_proposal` | **42 / 45** | 1 | 2 | 22 / 23 | 1 | 0 |

Every area and control not listed below is right on both paths.

| Item | inspect | layout_proposal | What the engine does |
|---|---|---|---|
| f3.A2 `Tick all that apply` | missed | missed | Held. Note: "its all-that-apply instruction conflicts with a limited selection instruction printed elsewhere in the form (… select up to 3) whose reach is unresolved". This is a **form-wide scope leak**: another question's limit suppresses an explicit multi-select. It is safe, but it is a usefulness loss. |
| f3.A3 `You may tick more than one box` | missed | missed | Held, for the same reason. |
| f3.A4 `Recipient(s)` | wrong | wrong | Mapped as a single `choice`, with a note that "(s)" suggests several answers. This is the D07 A20 usefulness loss. |
| f5.C2 consent declaration | wrong | wrong | Offered as an **ordinary answerable `checkbox`**. It is not protected and not a signing kind, so a note saying the patient consented could tick a clinician attestation. By contrast, the signature line (`signature`) and the initials box (`initials`) are correctly protected. |
| f4.A7, A9–A14 (coded rows, both summaries) | missed | right | `inspect` defers all seven with "Layout verification required …" (`layout_pending` 7). The proposal path maps each row with the literal header words, never the codes. |

Correct holds, which are the expected outcome: f3.C1 `(select up to 3)` and f3.C2, the D28-like
`Select up to 3` column, are both held with a note that the count cannot be represented. These are the
documented usefulness-loss controls.

Other results that are right on both paths:

- **f1:** `cell_append` below the blue guidance.
- **f2:** the tick-one question is a `choice`. The nine-box leave list is a `multi_choice`: the earlier tick-one
  did not leak into it.
- **f3:** `(one box only)` is a `choice`. The medicines table is one `table_rows` field, and `po` is never an
  option.
- **f4:** the pulse grid is six `text` cells, with Left and Right as sides rather than options. The comments are
  spans on the answer line, below the preserved instruction.
- **f5:** the knee pair has side-specific labels. The guidance paragraph is not mapped.
- **f6a, f6b:** all correct.

**Post-hoc verification.** I re-read every raw field after the run. None of these observations changes a
declared grade:

- **f1.A2:** the date field's label and context carry the *other* question's blue guidance ("Date the lead agency
  was last informed — State yes or no. If yes, give the management level…"). The guidance cell is read as a
  column header. I rate this medium severity.
- **f6a.A2:** the >5,000-character cell is kind `text` rather than `long_text`, with no cap.
- **f2.A2:** the multi-select result depends on the owner ending in a completed-event word ("taken"), as the
  recorded D31 owner does. This set does not test a multi-select FORMCHECKBOX list outside that word class.

**What this baseline does not show.** These forms are clean reproductions of structures the engine has already
been repaired on, so the high deterministic score does **not** transfer to the originals: D10's original still
yields 126 fields against 198 independently recorded areas. For a Sonnet 5 mapping run, the discriminating items
are:

- the non-right rows above;
- the two `must_hold` controls, which a model must also hold;
- f1.A2's label;
- the knee, consent and signature controls.

## Reproduce

```bash
PY=/opt/meddoc-pro/.worktrees/v1-sonnet5-diagnostics/rebuild/.venv/bin/python
cd docs/rebuild/v1/sonnet5-campaign/diagnostics/mapping
TMPDIR=/tmp $PY -B build_forms.py --check     # determinism
TMPDIR=/tmp $PY -B build_forms.py             # writes the .docx, prints sha256
TMPDIR=/tmp $PY -B check_expected.py          # engine-free consistency of the expected maps
sha256sum -c EXPECTED-SHA256SUMS              # maps, graders and notes cases are the frozen ones
TMPDIR=/tmp $PY -B measure_baseline.py        # deterministic baseline (sockets denied in-process)
# added 2026-09-29
TMPDIR=/tmp $PY -B grade_app_path.py --self-test --state-dir <scratch> --out app-path-selftest.json
TMPDIR=/tmp $PY -B long_answer_readback.py    # fill + effective_values read-back of the 5,835-character answer
TMPDIR=/tmp $PY -B wording_check.py --out wording-check.json
# grading a LIVE mapping result (the validate_proposal output, or {"fields": version.fields, "assistance": ...}):
TMPDIR=/tmp $PY -B grade_app_path.py --grade <output.json> --form <name> \
    --deterministic <the version-1 fields the request was compiled from> --expressible <the form's expressibility>
```

A live result is graded with `grade_app_path.py`, never with `measure_baseline.py`'s field-only grade: only the
review record distinguishes a correct hold from doing nothing.
