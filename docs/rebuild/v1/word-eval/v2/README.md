# Word harness v2.1: the `ticked` check

This implements the `ticked` check of `docs/rebuild/v1/word-harness-v2.md`, including the section "v2.1 — seven
readings" (committed as `3fc6520d`). It was self-tested on the development set only. Everything was written in
scratch. Nothing under `/opt/meddoc-pro`, no worktree and no corpus file was changed, and no filled document was
written anywhere: the information pass keeps its exports in memory.

v2.0 (`38f9283f…`, README of `64b1491d`) is the baseline. Every v2.0 fail-closed reading is kept unless a v2.1
reading replaces it, and each such place is named below.

| file | what |
|---|---|
| `ticked.py` | the independent reader: `zipfile` + `lxml` + the standard library; never imports `word_v3` or `core` |
| `answering.py` | v2.1 reading 1: the ground-truth-derived answers, filled through the candidate's public `fill` API as `final_eval.py` does. It is the only file that touches the engine, which is passed in and never imported by name |
| `test_ticked.py` | unittest self-tests: the v2.0 set plus the v2.1 readings (35 tests, 69 planted mutants) |
| `info_v21.py` | the development information pass with the v2.1 answering, for a given engine file |
| `codemut_sensitivity.py` | plants 36 code mutations in copies of `ticked.py` and checks the fast suite catches each one |
| `symcheck/` | the LibreOffice renders behind the glyph table: v2.0's `w:sym` render and v2.1's five-form render (see reading 3) |

```
sha256  e45a7fc00fd2a2d97173c9093cd1caebe1c7cdd7fe23ffeea6c12fdcdab37b79  ticked.py
sha256  75d61b7c29bc129fb03a8a1fcc17fac9cafb2423af28eaca0951e87c7912f6c4  answering.py
sha256  221597e6fed15128b6d25d97a4355b7fb6f056bb09a332190205acddf5866104  test_ticked.py
sha256  0946d5a77f6de2f0accd62c0eef225e14f507001c93acdb8235c05445a7d5033  info_v21.py
sha256  2fedae90a91bbd38a0700b50eb789b22f98d4c3f571ff36dfc6d258d6013edba  codemut_sensitivity.py
```

The self-tests, the information pass and the sensitivity run below were all run on exactly these bytes.

## Run

All commands run with `/opt/meddoc-pro/rebuild/.venv/bin/python`. None of them needs network access, a provider or a
`.env` file.

- `-m unittest -v test_ticked`: 35 tests, about 80 s, all pass.
- `info_v21.py`: about 6 minutes, one process.
- `codemut_sensitivity.py`: about 50 minutes, one mutant at a time.

Results go to the output directory named by the environment variable `TICKED_OUT`. The default is the session
scratch directory `…/scratchpad/v1/harness-v21/out`. It is never next to the files: each script refuses an output
directory inside a git work tree or inside the corpus. `info_v21.py` takes the engine file from `TICKED_ENGINE`. The
default is the frozen candidate's `word_v3.py`, extracted with
`git -C /opt/meddoc-pro/.worktrees/v1-word show 79a5b2ec6597:rebuild/documents/word_v3.py`
(sha256 `db227329…a93a72`). The live `v1-word` worktree is at a later commit, and its engine was not used.

Every corpus path goes through a guard. The guard refuses anything outside `dev/` and
`results/dev-79a5b2ec6597-frozen/`, and it refuses the `.annotator.json` files as ground truth. `holdout/` and
`qual/` are never opened.

## API

- `check_document(original_bytes, export_bytes, groundtruth, chosen) -> {"passed", "questions", "counts", "version"}`.
  `chosen[area_id]` is one of:
  - `None` or absent: unanswered;
  - a list of ground-truth option indices;
  - `{"unknown": why}`: the question is unverifiable;
  - `{"mapping": why}` (v2.1): the question **fails** with a reason starting `mapping:`.
  Every choice, multi_choice, checkbox and checkbox_group area gets a verdict (pass / fail / unverifiable), a reason,
  the box kinds it read, and the tie mode (`slot-per-option`, `printed-text`, `dropdown`, `cell-text`).
- `answering.answer_document(engine, original_bytes, groundtruth, detection, profile, score_doc, answers_for) ->
  {"export", "chosen", "answers", "refused", "notes"}`.
- `answering.load_answers_for(final_eval.py)` takes v1's `answers_for` from `final_eval.py`'s own source, via `ast`.
  It is not retyped, and it is not imported, because importing it would load an engine from a fixed path.

## The seven v2.1 readings, as implemented

1. **The chosen answer in ground-truth terms** (`answering.py`).
   - Choice: option `min(1, n−1)`. Multiple choice: the first two. Checkbox: ticked.
   - The option's ground-truth label is given, as text, to the field the v1 scorer's row matches to the question.
   - If no field matches, the question fails as `mapping: no detected field matches`.
   - If the engine refuses the fill, the question fails as `mapping: the matched field … did not accept the label …`.
   - The whole fill is tried first. If the engine refuses it, each answer is tried alone on top of v1's unchanged
     text answers, and the refused ones are dropped. An answer accepted alone but refused together with the others
     would be dropped as "refused in combination"; that did not happen on dev.
   - Text answers are `answers_for` of `final_eval.py`, unchanged.
   - Before any v2.1 answer was given, the engine file was proven to be the frozen candidate on all 40 dev documents
     (details under "Development results").
2. **Printed options with no box, one slot per option.** A slot holding no box reads its option by the inserted mark
   before the option's printed text, found in *its own slot* (word-bounded, first occurrence).
   - FAIL-CLOSED: the option is not printed in its slot, or is printed there only inside a longer option's text →
     unverifiable.
   - Slots are read one at a time, so one slot may hold a box while another is read by a mark.
   - The shared-slot (second bullet) mode already read boxless lines by the mark.
   - This replaces v2.0's fail-closed choice 5.
3. **Wingdings / Wingdings 2 characters stored as text** are read through the same table as `w:sym`, keyed by the
   run's font and the character code (`U+F0xx` or the plain byte). FAIL-CLOSED choices:
   - "The run's font" is the set of slots that can draw the character: ascii **and** hAnsi, plus eastAsia under an
     eastAsia hint or for an East Asian character, plus cs in a complex-script run. All of them must name one font.
   - The package's `fontTable.xml` must declare that font with `w:charset 02`. Without that declaration,
     LibreOffice draws a fallback glyph for the text forms (first render), so the entries were verified only in that
     configuration.
   - Every table entry, old and new, was rendered in five storage forms (see "The glyph table").
   - This replaces v2.0's choice 2 for table entries only; every other symbol-font text character stays unreadable.
4. **Radio circles.**
   - Unicode `○` reads unticked; `◉` and `●` read ticked.
   - Symbol-font circles whose render is `○` / `●` are added to the table (see below).
   - A `☒` inserted beside a circle that stays `○` reads as the circle unticked, and the question fails. The `☒` is
     also no option's mark. This is D28 A155 on dev.
   - FAIL-CLOSED: only these shapes. `◯ ⚪ ⚫ ◎`, the combining enclosing circle U+20DD `⃝`, the heavy rings
     (Wingdings A2, Wingdings 2 9B), the ring with a dot (Wingdings 2 9C) and Wingdings A4 (`◉`, which renders as
     a fallback glyph) stay recognised but unreadable.
5. **Two questions in one paragraph.** A box tied to another question's option, and an inserted mark read for another
   question's option, are judged by that question only. Rule 3's "every other box" means this question's non-chosen
   options' boxes plus boxes tied to no question.
   - This applies to rule 3 (the judgement), not to rule 2 (the ties).
   - The v2.0 conflict guard stays: one box tied to two questions ties neither, and a conflicted question ties
     nothing. Its boxes remain "tied to no question" for any third question (`ConflictedTiesAreNoOnes`).
   - This replaces v2.0's choice 11.
6. **Cell text.** This applies to a question with ONE slot that is a cell (`…/tc[k]`) empty in the original, and with
   at least two options. Its exported text must equal an option's label exactly: paragraphs are joined by a line
   break and only the outer whitespace is stripped; case, punctuation and inner spacing count.
   - Equal to the chosen label → pass.
   - Equal to another option's label → that option is shown → fail.
   - Empty → fail.
   - Any other text, a box, control or picture in the cell, text that does not print, or two options sharing the
     label → unreadable.
   - Several options chosen for one cell → unverifiable.
   - A question with one slot per option keeps the cell-mark reading of rule 1.
7. **Legacy dropdowns** are read as v2.0 declared. **No development document has one: the `FORMDROPDOWN` reader is
   proven on synthetic packages only (`LegacyDropdown`), and a qualification report must say so.**

## The glyph table (fixed in `ticked.py`)

| Unicode | state |
|---|---|
| `☐` `○` | unticked |
| `☒` `☑` `✓` `✔` `◉` `●` | ticked |

| font | unticked | ticked |
|---|---|---|
| Wingdings | `6F` `71` `72` `A8` `A1`(○) | `FC` `FD` `FE` `6C`(●) |
| Wingdings 2 | `A3` `81`(○) `99`(○) `9A`(○) | `50` `51` `52` `53` `54` `97`(●) `98`(●) |

Every entry was rendered through networkless LibreOffice (gotenberg:8, `docker run --network none`, as the v1
`render_eval.py` renders) in five forms:

- `w:sym`;
- `w:t U+F0xx` with rFonts on all four slots;
- `w:t U+F0xx` with rFonts on ascii/hAnsi only;
- `w:t` plain byte with rFonts on all four slots;
- `w:t` plain byte with rFonts on ascii/hAnsi only.

The package's font table declares both fonts with charset 02. Each entry drew the same glyph in all five forms:

- The page is `symcheck/wingdings-wt-render-1.png`; the circle rows are enlarged in `symcheck/zoom-*.png`.
- In the PDF text layer (`symcheck/text-layer.json`), every form is drawn in OpenSymbol, the font LibreOffice
  substitutes for Wingdings.
- The first render had no font table. There, every text form was drawn in NotoSerif as a fallback glyph, which is
  why the charset condition exists.
- Left out, because they render as fallback glyphs in every form: Wingdings `78` and Wingdings 2 `2A`. D05's footer
  box is Wingdings 2 `2A` stored as text, so it stays unreadable.

Anything else recognised as a box is **unreadable**.

## Fail-closed choices where the declaration is silent

v2.0's 20 choices (README of `64b1491d`) stand, except these:

- **5** is replaced by reading 2.
- **11** is replaced by reading 5.
- **2** is narrowed by reading 3.
- **1**: radio circles are now read by reading 4.
- **20** (the text join): the information pass uses reading 1 instead. `join_chosen` is kept only to rebuild the
  chosen sets of the frozen v1-profile exports the self-tests use as bases.

v2.1 adds these fail-closed readings, each pinned by a test and a code mutation:

21. **The inserted-mark reading, tightened** (`MarkReadingFailClosed`; mutations C33–C35). Three rules:
    - The option's printed text must survive as one unbroken run of the original's characters.
    - When nothing is inserted before the option, the visible token now before it must be the original's.
    - Text (not whitespace, not `☒`) inserted right before the option makes it **unreadable**. v2.0 read it as
      unticked.

    Found on dev: the candidate typed a label over bracketed alternatives, as in `[he/she]` → `she`. The letters of
    `she` lined up with the printed option, so v2.0's rule would have called the question a definite fail. The
    reader cannot tell a kept option from a retyped one, or a typed `X` mark from other text. v2.0's rule was also
    fail-open: a typed `X` before a non-chosen option read as unticked, so the question could pass.
22. **Typed bracket boxes** are boxes of unreadable state (`TypedBoxes`, C36): `[ ]`, `[  ]`, `[]` and `( )` (at least
    one space inside parentheses). They are the same idea as a bordered blank run. They occur only in D29 on dev,
    and its ground truth says "mark inside the brackets". Read as text, they would let reading 2 read a correctly
    marked `[X] no` as "no unticked", a false fail.
23. Reading 3's font-slot agreement and font-table charset condition (above; C20, C21).
24. Reading 6's exactness, and "another option's label = that option shown" (C29, C31).
25. Reading 1's answering choices (listed under "Ambiguities").

A limit that stays: glyph tokens align by kind, not by shape. When a glyph is inserted right after a glyph box, the
alignment can pair the new glyph with the original box. The displaced box then reads as an inserted box of no
option, so this can only produce a fail, never a pass (`TypedBoxes` covers the shape).

## Verdicts the v2.1 readings changed in the existing self-tests

Every v2.0 test still passes. Only these expectations changed, each deliberately:

| test | v2.0 expectation | v2.1 | why |
|---|---|---|---|
| `FailClosedReadings` D28 A155 | unverifiable, "list bullet" | **pass** (identity) | readings 3+4: its Wingdings 2 radio-circle numbering bullets read `○` |
| `FailClosedReadings` D04 A2 | unverifiable, "holds 0 boxes" | **pass** (identity) | reading 2: a lettered option with no box is read by the inserted mark |
| `FailClosedReadings` D06 A58 | unverifiable, "not printed" | **pass** (identity) | reading 6: one empty answer cell is the "cell text" kind |
| `FailClosedReadings` D05 A6 | unverifiable, "w:t, not w:sym" | unverifiable, "(w:t) outside the glyph table" | reason text only: Wingdings 2 text is read through the table, and `2A` is not in it |
| `SymTable` Wingdings 2 `F099` | unverifiable | **pass** | reading 4 put `99` (○) in the table; `F09C`, `F09B`, Wingdings `F0A4`, `F0A2` took its place and stay unreadable |

The three pins that now pass are kept as positive pins (`V21IdentityReadings`, together with D28 A7). New unverifiable
pins were added: D27 A33 (□), D29 A103 (reading 2's no-box branch), D03 A20 (three boxes in one slot), D38 A32
(mixture), D29 A117 (a label cell that is not empty) and D29 A46 (typed bracket box).

All 35 v2.0 mutants keep their verdicts. The positive controls are unchanged.

On the frozen v1-profile exports with v2.0's join (`DevInformation`, information only), the v2.1 reader changes 189
of 1,132 question verdicts:

- 187 go from unverifiable to pass:
  - D06: 105 cell text;
  - D04 23, D29 30, D03 2, D30 1: slot marks;
  - D28 19 and D38 6: circles read.
- 2 go from unverifiable to fail: D28 A158 and A198. Each is unanswered, but a circle was ticked by a v1 extra field.

## Development results: v2.1 answering, frozen candidate `79a5b2ec6597` (information only)

**The engine is the frozen candidate's.** On all 40 dev documents:

- `inspect()` equals the frozen detection;
- v1's `answers_for` equals the frozen `answers.json`;
- filling those answers gives exports byte-identical to all 80 frozen v1 exports.

The ordinary and long profiles give identical counts.

**Documents (40 per profile)**

| verdict | count | which |
|---|---|---|
| pass | 11 | D01 D05 D06 D08 D09 D11 D13 D25 D33 D34 D37 |
| fail | 20 | D03 D04 D07 D10 D12 D14 D15 D17 D18 D20 D24 D27 D28 D29 D30 D31 D35 D36 D38 D39 |
| unverifiable | 0 | |
| no ticked questions (vacuous pass) | 9 | D02 D16 D19 D21 D22 D23 D26 D32 D40 |

**Questions (1,132 per profile)**

| | pass | fail | unverifiable |
|---|---|---|---|
| all | 774 | 306 | 52 |
| mapping failures (reading 1) | – | 297 | – |
| read | 774 | 9 | 50 |
| chosen set unknown (the ground truth lists no options: D35 A15, A16) | – | – | 2 |

The 297 mapping failures are made up of:

- 217 labels refused (`invalid_answer`);
- 1 refused (`answer_too_long`);
- 79 questions with no matched field.

Most refusals come from candidate option wordings that differ from the printed options. D10's options are `2` and
`(option 2)` (118). Other wordings: `] kg [`, `Acid ……`, `Yes → if yes, describe…`. Other refusals come from a
multiple choice mapped to a single-choice field (D03, D07, D14…).

Documents that passed under v2.0 and fail now (D07, D12, D14, D15, D31, D39) fail on mapping only. D06 moved from
unverifiable to pass (cell text).

The nine read failures:

- D17 A16, D18 A16 and D24 A9: the label list was written into another placeholder, and the options are unmarked.
- D28 A152 and A184: mapped to text fields; no box ticked.
- D28 A155: a `☒` was inserted beside a numbering circle that stays `○`.
- D28 A182 and A183: a 4-option question was mapped to a single checkbox field. The engine takes the label "No" as
  *unchecked*.
- D36 A1: "No" was typed after "Circle Yes or No:"; the options are unmarked.

**Per box kind (ordinary; mapping failures keep the box kinds of their informative read)**

| box kind | pass | fail | unverifiable |
|---|---|---|---|
| legacy checkbox | 368 | 144 | 0 |
| glyph (incl. list bullets, circles, text Wingdings) | 188 | 90 | 24 |
| cell text (reading 6) | 105 | 0 | 0 |
| inserted mark | 55 | 32 | 13 |
| cell mark | 30 | 3 | 9 |
| content-control dropdown | 28 | 0 | 0 |
| content-control checkbox | 0 | 11 | 0 |
| picture | 0 | 16 | 0 |
| glyph + picture | 0 | 0 | 1 |
| untied | 0 | 10 | 5 |

**Every remaining unverifiable question (52 per profile), per box kind**

- **glyph (24)**
  - 11: U+20DD `⃝` circles, not a declared radio circle. D03 A33 A76 A79 A80; D38 A5 A31 A39 A41 A47 A52 A56.
  - 11: a typed bracket box is gone from the export, because the candidate wrote its text answers over `[  ]`.
    D29 A46 A49 A51 A53 A55 A57 A59 A62 A65 A66 A69.
  - 2: `□` U+25A1, outside the table. D27 A33 A35.
- **inserted mark (13)**
  - 6: the printed options were rewritten: the label was typed over bracketed alternatives. D17 A6 A12, D18 A6 A12,
    D24 A33 A37.
  - 5: text inserted right before the options: the label list was written over the placeholder. D17 A11, D18 A11,
    D24 A16 A27 A34.
  - 2: the same printed options are tied to two questions. D24 A29 / A32.
- **cell mark (9)**: the candidate wrote labels or text answers into per-option cells, e.g. "Twice daily" in the
  "Once daily" cell. D27 A19 A22 A25 A27 A28; D29 A25 A44 A45 A105.
- **untied (5)**
  - D35 A15 and A16: the ground truth lists no options.
  - D03 A34: boxes before some options only (a mixture).
  - D29 A32: a checkbox slot with no box.
  - D38 A57: one option slot holds three boxes.
- **glyph + picture (1)**: D28 A11, picture boxes.

Full per-question records are in `out/dev-results-v21.json`.

## Planted mutants (69, all detected)

Each mutant is applied to an in-memory copy. It must first prove it applied: the bytes differ, the targeted XML
differs, and a kind-specific post-condition holds.

- The 35 v2.0 mutants are unchanged: every one gives the same verdict as in v2.0.
- The v2.1 bases are **synthesized from dev originals**. The export starts as the original and only the question
  under test is answered.

| reading | base | mutant | verdict |
|---|---|---|---|
| 2 mark in own slot | D04 A3 (☒ before "Female") | mark removed / moved to "Male" / two marks / ☑ instead / mark after the option / pre-ticked "☒ Male" printed and left / the ☒ hidden | fail ×7 |
| 3 Wingdings text | D28 A7 (w:t Wingdings 2 `F081` ○; "No" → `F098` ●) | chosen left ○ / tick moved / two ticks / pre-ticked default left / ☒ inserted beside a circle that stays ○ | fail ×5 |
| | | font table no longer charset 02 / the ticked run's hAnsi another font / `F09C` as the tick | unverifiable ×3 |
| 4 radio circles | D15 A16 redrawn with ○ ("No" → ●) | ☒ beside a circle that stays ○ (the declared case) / ● back to ○ / ● moved / ◉ on both / pre-ticked default left | fail ×5 |
| | | `◯` as the tick | unverifiable |
| 5 two questions | D17 A11+A12 (marks), D03 A60+A61 (⃝ redrawn ☐) | this question's non-chosen option marked (A11; A12) / a mark beside a word of no question / this question's non-chosen box ticked (A61) / a box tied to no question ticked (A61's "After" removed from a GT copy) | fail ×5 |
| 6 cell text | D06 A58 ("No" written) | cell left empty / another option's label | fail ×2 |
| | | "no" / "No." / "X" / "No/NA" / hidden label / pre-filled original | unverifiable ×6 |

`TwoQuestionsInOneParagraph` also proves two things:

- Both bases pass under v2.1 and one question of each fails under v2.0's reading.
- When one question of a pair fails, the other still passes.

## Positive controls

- The v2.0 controls all still pass: unmutated D01, D07, D09, D15 and D33 exports; mutant bases, also after a null
  rewrite; pre-ticked defaults correctly unticked; and every dev original against itself never fails.
- Each v2.1 base passes, also after a null rewrite: mark-slot, wt-circle, radio, celltext, two-q-marks, two-q-boxes.
- Readings 2, 3 and 4 have pre-ticked positives (a printed default correctly unticked beside marks).
- Identity pins pass by the new modes: D04 A2 (inserted mark), D28 A155 (numbering-bullet circle), D28 A7 (w:t
  circle), D06 A58 (cell text).
- Synthetic tests pass:
  - every table entry in text form (PUA and byte; four slots and two);
  - the `w:sym` radio codes;
  - the Unicode circles;
  - cell text;
  - slot marks read in their own slot;
  - `answering.py` with a stand-in engine;
  - `answers_for` equal to v1's.
- On the real candidate (information pass), every new kind has passing questions:
  - cell text: D06, 105;
  - Wingdings 2 text and numbering-bullet circles: D28, 150;
  - `⃝` boxes the engine redrew as `●`: D38, 6;
  - slot marks: D04 15, D29 18.

## Code-mutation sensitivity

`codemut_sensitivity.py` first runs the baseline, which passes. It then plants 36 mutations in copies of `ticked.py`,
each asserted to apply exactly once, and runs the fast suite (every class except `DevInformation` and `Resolver`)
against each copy. **All 36 are detected** (`out/codemut.log`).

| # | mutation | caught by (first failing test) |
|---|---|---|
| C1–C16 | v2.0's 16: orphan rule, content-control display check, ☒-only mark, the inserted-mark scan (re-anchored), conflict guard, unreadable glyph read unticked, cell-mark strictness, list entries, word bounds, odd legacy values, `w:sym` font (re-anchored), symbol-font text, hidden runs, bordered blanks, list bullets, legacy dropdown cached result | as in v2.0 |
| C17 | reading 2: a slot with no box never read by the mark | `V21IdentityReadings`, mark-slot mutants |
| C18 | reading 2: the option searched in every slot, not its own | `SlotMarks` |
| C19 | reading 2: the "inside a longer option" check in a slot removed | `SlotMarks` |
| C20 | reading 3: the font-table charset condition removed | `WtTable`, the wt-circle font-table mutant |
| C21 | reading 3: only the ascii slot read | `WtTable`, the wt-circle hAnsi mutant |
| C22 | reading 3: text forms never read | `V21IdentityReadings`, wt-circle base |
| C23 | reading 4: `○` read ticked | `RadioCircles`, radio mutants |
| C24 | reading 4: `●` read unticked | `RadioCircles`, radio base |
| C25 | reading 5: boxes tied to another question not excluded | `TwoQuestionsInOneParagraph` |
| C26 | reading 5: marks read for another question not excluded | `TwoQuestionsInOneParagraph` |
| C27 | reading 5: boxes tied to no question treated as foreign | the orphan mutants |
| C28 | reading 5: conflicted questions own their boxes | `ConflictedTiesAreNoOnes` |
| C29 | reading 6: cell text compared case-insensitively | `CellText`, "the label in another case" |
| C30 | reading 6: cell text removed | `V21IdentityReadings`, celltext base |
| C31 | reading 6: another option's label read unverifiable | `CellText`, "another option's label written" |
| C32 | reading 1: a mapping failure read unverifiable | `Mapping` |
| C33 | inserted text before an option read unticked (v2.0's rule) | `MarkReadingFailClosed` |
| C34 | the rewritten-neighbour check removed | `MarkReadingFailClosed` |
| C35 | the unbroken-option-text check removed | `MarkReadingFailClosed` |
| C36 | typed bracket boxes not recognised | `TypedBoxes`, `FailClosedReadings` D29 A46 |

## Ambiguities for the declaration's owner

1. **Reading 1 does not name `checkbox_group`.** It is answered like a choice, with one option `min(1, n−1)`. One
   ticked option is a valid answer under either reading of a group.
2. **Ground-truth checkboxes carry no label.** All 123 dev checkboxes have `options: []`, so there is no "label as
   text" to give. The value given is `True`; a text field writes it as "True" (D27 A25).
3. **A multiple choice's two labels** are given as a list, which is the engine's shape. A text field matched to a
   multiple choice then writes the list's repr, `['injuries', 'condition']`.
4. **Detected choice fields that no ground-truth choice question matches are left unanswered.** There are 198 per
   profile; v1 answered them. The choice answers are fixed in ground-truth terms, and these fields have none.
5. **"Does not accept" is observable only as the engine refusing the fill.** A label the engine *accepts with another
   meaning* is not a refusal: "No" given to a checkbox field is taken as unchecked (D28 A182, A183). The reader then
   fails the question, so the document outcome is the same, but the class is "read", not "mapping". A text field
   accepts any label, so questions mapped to text fields are judged by the reader. They are mostly unverifiable when
   the label is typed over the options.
6. **Reading 3's "run's font"**: a run has four font slots. Here they must all agree (see above), and the font table
   must say charset 02. That is the only configuration in which LibreOffice draws the text forms correctly.
7. **Reading 4 lists three characters.** U+20DD `⃝`, the radio circle of D03 and D38, is not one of them, which leaves
   11 dev questions unverifiable. `◉` has no Wingdings code that renders, and the Wingdings 2 heavy pair `9B`/`9C` is
   out.
8. **Reading 6 speaks of "the chosen option's label" in a cell.** It is read for a question's single answer cell.
   Per-option empty cells keep the cell-mark reading, so a label written into an option's own cell is unreadable
   (9 dev questions, all a label written into the wrong option's cell).
9. **Typed bracket boxes** (`[ ]`) and the tightened mark reading (choices 21, 22) are new fail-closed readings. They
   hold 22 dev questions at unverifiable where a literal v2.1 reading would say "fail". Every one of them is a
   candidate that typed text over the options or boxes. Declaring a "typed box" kind (for example `[X]` ticked) would
   let a correct candidate pass there.
10. **Legacy dropdowns are proven on synthetic packages only** (reading 7).
