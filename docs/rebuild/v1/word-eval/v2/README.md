# Word harness v2: the `ticked` check

Implements the `ticked` check of `docs/rebuild/v1/word-harness-v2.md` (committed as `64b1491d`), self-tested on the
development set only. Written in scratch; nothing under `/opt/meddoc-pro`, no worktree and no corpus file was changed.

| file | what |
|---|---|
| `ticked.py` | the independent reader: `zipfile` + `lxml` + the standard library; never imports `word_v3` or `core` |
| `test_ticked.py` | unittest self-tests on dev: information run, resolver cross-check, planted mutants, positive controls |
| `dev-results.json` | written by the tests: per document and question verdicts, the summary tables, the mutant table |
| `codemut_sensitivity.py` | supplementary: plants 16 code mutations in copies of `ticked.py` and checks the fast tests catch each |
| `symcheck/wingdings-sym-render.png` | the LibreOffice render used to check the `w:sym` table entries |

```
sha256  38f9283f3c5db02efee0695873d234a7af1c9af163758886a3653b8190f9dcbc  ticked.py
sha256  ec6b24531c4f2935e18af9fcbaa125a11672527e201f2e9dbb0d4edbbfe734b2  test_ticked.py
```

Run: `/opt/meddoc-pro/rebuild/.venv/bin/python -m unittest -v test_ticked` (14 tests, about 1 minute, all pass). The
tests read the dev corpus, the frozen results `results/dev-79a5b2ec6597-frozen/` and the v1 `score.py` (for the
field-level join only). Every corpus path goes through a guard that refuses anything outside `dev/` and that results
directory. The tests write only `dev-results.json`, next to themselves: if the files move into `word-eval/`, that file
lands there too.

## API

`check_document(original_bytes, export_bytes, groundtruth, chosen) -> {"passed", "questions", "counts", "version"}`.
`chosen[area_id]` is `None` or absent (unanswered), a list of ground-truth option indices (a checkbox: `[0]` ticked,
`[]` answered unticked), or `{"unknown": reason}` (the question is unverifiable). Every choice, multi_choice,
checkbox and checkbox_group area gets `verdict` in pass / fail / unverifiable, a `reason`, the box kinds it read and
the tie mode. `passed` is true only when every such question passes. A document with no such question passes
vacuously: `ticked` can only take documents out.

`join_chosen(groundtruth, matched, fields, answers, related)` turns a profile's answers (keyed by detected field)
into ground-truth option indices, by option text only. `matched` and `related` come from the v1 scorer, which
`ticked.py` does not import.

## How each rule is read

1. **States.** A content-control checkbox is `w14:checked/@w14:val` in {1, true}. A legacy checkbox is `w:checked`
   (absent `@w:val` or a true value), else `w:default`. A printed glyph is read from the fixed table below. A cell mark
   is a cell empty in the original that now holds exactly one of `X x ✓ ✔ ☒`. An inserted mark is a `☒` immediately
   before the option's printed text (whitespace aside) that the original does not have there. A dropdown's shown text
   must equal the chosen option's text, with its list entries unchanged.
2. **Ties** come from the original and the ground truth only. When there is one slot per option, option i is slot i
   and that slot must hold exactly one box or control. Otherwise each option's printed text is found in document
   order (first unused occurrence) and takes the box immediately before it; when no option has a box before it, every
   option takes the box after it; a mixture is unverifiable. Printed options with no box are read by the inserted
   mark. The original and the export are matched per paragraph, token by token (`difflib`), so an inserted `☒ ` does
   not shift which box is which.
3. **Pass** when the ticked set equals the chosen set exactly and every other box in the slots is unticked. For an
   unanswered question, every box keeps its original state.
4. **Unverifiable** when no tie is possible or a state cannot be read. It is reported with the question's id, label
   and reason, and it fails the document.

**The glyph table** is fixed in `ticked.py`:

| Unicode | state |
|---|---|
| `☐` | unticked |
| `☒` `☑` `✓` `✔` | ticked |

| `w:sym` | unticked | ticked |
|---|---|---|
| Wingdings | `6F` `71` `72` `A8` | `FC` `FD` `FE` |
| Wingdings 2 | `A3` | `50` `51` `52` `53` `54` |

Every entry was checked by rendering it as a `w:sym` through LibreOffice's Wingdings recoding (gotenberg:8). The
render is `symcheck/wingdings-sym-render.png`. Anything else is **unreadable**.

## Fail-closed choices where the declaration is silent

Each choice below is pinned by a test. Mutating any of them in `ticked.py` makes the suite fail (see the sensitivity
check below).

1. **Box recognition is wider than box reading.** A long list of box-like characters (`□ ○ ◉ ● ⃝ ◻ ❏ ✗ √ ⊠ …`),
   any private-use character, any `w:sym` outside the table, a picture or shape (`w:drawing`, `w:pict`, `w:object`,
   `mc:AlternateContent`), a run with a character border around nothing but spaces, and a `SYMBOL` / `MACROBUTTON` /
   `EQ` field are all boxes. Their state is **unreadable**. Otherwise a box outside the table would pass for plain
   text, and its option would be read by the inserted mark. Radio circles are therefore unreadable (D03, D28, D38).
2. **Characters in a symbol font carried as `w:t` text are unreadable**, even when their code is in the table. The
   declaration names `w:sym` codes. Fonts are resolved per character class (ascii / hAnsi / eastAsia under a hint /
   cs for complex script), through direct `w:rFonts`, the character style chain, the paragraph style chain,
   document defaults and theme fonts. A private-use character is checked against every font of its run.
3. **Two `w:sym` codes were left out**: Wingdings `78` (⌧) and Wingdings 2 `2A` (☐). They rendered as fallback
   glyphs, so they could not be verified.
4. **List bullets are printed glyphs.** The label from `numbering.xml`, reached through the paragraph or its style
   chain, `lvlOverride` and `numStyleLink`, is read like any other glyph. A list label that cannot be resolved, or a
   picture bullet, is an unreadable box. D28's circles come from numbering.
5. **One slot per option means one box per slot.** An option slot with no box is unverifiable. The sentence "printed
   options with no box at all are read by the inserted mark" is read as belonging to the second bullet only. The
   impact is D04 (23 questions) and several eq-shaped slots in D28, D29 and D30. This is the largest ambiguity; see
   below.
6. **A cell mark needs a cell slot** (`…/tc[k]`) that is empty in the original: no visible text, box, control or
   picture. A paragraph slot inside an empty cell is not a cell box. A pre-marked cell is no box at all.
7. **"Immediately before" allows only whitespace and punctuation** between a box and its option's text. No letter,
   digit, other box, other option or excluded character may sit between them.
8. **Printed option text must be word-bounded.** `No` is not found inside `Not sure`. Matching uses NFKC, casefolding
   and collapsed whitespace. It does not ignore whitespace entirely: `RightLeg` does not match `Right Leg`.
9. **An option found only inside a longer option's printed text is unverifiable.** The declaration's
   first-unused-occurrence rule would otherwise tie `Left` to the start of `Left and Right`.
10. **One box or printed option tied to two ground-truth questions ties neither.** Both questions are unverifiable
    (D24 A29/A32). Without this, two questions sharing a paragraph with the same option words would both read the
    first pair.
11. **Boxes of other questions in the slots count as this question's boxes.** This is literal rule 3 ("every box in
    the question's slots that belongs to no chosen option is unticked"). So does a `☒` inserted anywhere in a whole
    paragraph or cell the slots cover that is not the mark read for one of this question's options. That fails
    closed, but a paragraph shared by two questions can then fail when the other one is answered. See the
    ambiguities below.
12. **Content-control checkbox:** a value outside {0, 1, true, false}, a `w14:checked` without `w14:val`, several
    `w14:checked`, or a shown character that contradicts the state is unreadable. The shown character must be the
    control's `checkedState` / `uncheckedState` character, by default ☒ / ☐.
13. **Legacy checkbox:** several `w:checked`, a value outside {0, 1, true, false, on, off}, or neither a `w:checked`
    nor exactly one `w:default` is unreadable.
14. **Dropdowns.** Rule 2 does not mention them. A question is a dropdown question only when its slots hold exactly one
    dropdown and nothing else. Each ground-truth option must equal exactly one list entry (whitespace collapsed,
    case-sensitive). Showing the placeholder counts as showing nothing. A legacy dropdown reads `w:result`, else
    `w:default`, else 0, and is unreadable if a visible cached field result disagrees with that. A dropdown cannot
    show two answers, so a multi-answer chosen set on a dropdown is unverifiable.
15. **A single checkbox with no options** has one implicit option, and its slot must hold exactly one box.
16. **Unanswered questions with unreadable boxes are unverifiable** even when the XML did not change (literal rule 4).
17. **The inserted mark is exactly `☒`**, readable (not in a symbol font, not hidden). An inserted `☑` / `✓` / `○`
    before an option is unreadable, and an inserted box of any kind that is not an option's mark fails.
18. **Marks that do not print are unreadable.** Hidden (`w:vanish`, `w:specVanish`, `w:webHidden`, direct or from the
    character style), white (`FFFFFF` or theme `background1` / `light1`), or under 4 pt. This applies to a glyph, mark,
    control or cell mark in such a run. Hidden text is not printed option text.
19. **The structure must be unchanged.** A slot that no longer resolves in the export, or holds a different number
    or kind of paragraphs, makes the question unverifiable. So does an original box that the token alignment cannot
    find in the export ("its box is not in the export").
20. **The chosen set is not in the declaration either.** The declaration says "the set the profile chose", but a
    profile answers detected fields in the candidate's own option wording. `join_chosen` maps them by text only,
    never through the engine's option-to-box locator. The field-level match is the v1 scorer's GT-to-field row. The
    answer's text names a ground-truth option by exact equality, else by an equal sequence of letter/digit words,
    else by one word sequence starting the other. Each tier needs exactly one hit; ambiguity stops the search. The
    chosen set is **unknown, and the question unverifiable**, when the matched field is not a choice-like field, the
    answer names no single option, or an *unmatched* answered tick-writing field touches the slots. A field matched
    to *another* question is that question's answer; its ticks here are judged by rule 3 as above.

## Development results (frozen candidate `dev-79a5b2ec6597`, information only)

The ordinary and long profiles give identical counts, because their choice answers are the same.

**Documents (40 per profile)**

| verdict | count | which |
|---|---|---|
| pass | 16 | D01 D05 D07 D08 D09 D11 D12 D13 D14 D15 D25 D31 D33 D34 D37 D39 |
| fail | 2 | D03, D28 |
| unverifiable | 13 | D04 D06 D10 D17 D18 D20 D24 D27 D29 D30 D35 D36 D38 |
| no ticked questions (vacuous pass) | 9 | D02 D16 D19 D21 D22 D23 D26 D32 D40 |

**Questions (1,132 per profile)**

| | pass | fail | unverifiable |
|---|---|---|---|
| all | 538 | 2 | 592 |
| answered (joined) | 518 | 1 | 204 |
| unanswered | 20 | 1 | 58 |
| chosen set unknown (the join) | – | – | 330 |

**Per box kind (ordinary profile)**

| box kind read | pass | fail | unverifiable |
|---|---|---|---|
| legacy checkbox | 394 | 0 | 118 (all "chosen set unknown": D10's candidate options are `2`, `(option 2)`) |
| glyph (incl. list bullets) | 48 | 1 | 240 |
| inserted mark | 27 | 0 | 18 |
| cell mark | 31 | 0 | 11 |
| content-control dropdown | 28 | 0 | 0 |
| content-control checkbox | 10 | 1 | 0 |
| content-control checkbox + glyph | 0 | 0 | 2 |
| picture | 0 | 0 | 16 |
| glyph + picture | 0 | 0 | 1 |
| untied (no tie possible) | 0 | 0 | 186 |

**Why questions did not pass (ordinary profile)**

| count | verdict | reason |
|---|---|---|
| 165 | unverifiable | chosen set unknown: unmatched answered detected fields touch the slots (mostly D28) |
| 122 | unverifiable | chosen set unknown: the answer names no single ground-truth option (118 are D10) |
| 109 | unverifiable | an option is not printed in the slots (105 are D06 cells where Yes/No/NA/ND is *written*) |
| 74 | unverifiable | unreadable glyph (radio circles ○ ⃝, Wingdings 2 in `w:t`, □) |
| 58 | unverifiable | an option slot holds no box (fail-closed choice 5) |
| 41 | unverifiable | chosen set unknown: matched to a text field |
| 16 | unverifiable | a picture in the slots (D20's inline-picture boxes, D29) |
| 2 / 2 / 2 / 1 | unverifiable | several boxes in one option slot / mixture / same option tied to two questions / box not in the export |
| 1 | **fail** | D03 A21: unanswered, but its `Right` box was ticked. The candidate merged A20 and its Right/Left sub-boxes into one 20-option field and answered "Right" |
| 1 | **fail** | D28 A155: an inserted `☒` beside options whose printed radio bullets remain |

Two further real candidate behaviours are visible as unverifiable, not fail. In D28 A142 the candidate replaced a
printed radio circle with an `X`, so the original box is gone. D28's grids were split across 3–7 detected fields per
question.

## Planted mutants (all killed)

Each mutant starts from a base whose target question passes. It is applied to an in-memory copy. Before its verdict
is used, it must prove it applied: the bytes differ, the targeted slot's XML differs, and a kind-specific
post-condition holds. The pre-ticked mutants change both the original and the export.

| kind | mutant | base | verdict |
|---|---|---|---|
| content-control checkbox | chosen box unticked | D03 A50* | fail |
| | tick moved to the neighbour | D03 A50* | fail |
| | two ticks for one single-choice answer | D03 A50* | fail |
| | left and right swapped | D03 A22* | fail |
| | pre-ticked printed default left ticked | D03 A50* | fail |
| | state ticked but the control still shows ☐ | D03 A50* | unverifiable |
| legacy checkbox | chosen box unticked | D09 A11 | fail |
| | tick moved to the neighbour | D09 A11 | fail |
| | two ticks for one single-choice answer | D09 A11 | fail |
| | pre-ticked printed default (`w:default`) left ticked | D09 A11 | fail |
| | multi: one of two chosen boxes unticked | D07 A11 | fail |
| | `w:checked w:val="maybe"` | D09 A11 | unverifiable |
| glyph | chosen box unticked | D15 A16 | fail |
| | tick moved to the neighbour | D35 A11 | fail |
| | two ticks for one single-choice answer | D35 A11 | fail |
| | pre-ticked printed default left ticked | D15 A16 | fail |
| | a box of no option ticked (GT copy without its 3rd option) | D35 A11 | fail |
| | the ticked glyph does not print (`w:vanish`) | D15 A16 | unverifiable |
| cell mark | chosen box unticked | D06 A11 | fail |
| | tick moved to the neighbour | D06 A11 | fail |
| | two ticks for one single-choice answer | D06 A11 | fail |
| | pre-ticked printed default (cell pre-marked) | D06 A11 | unverifiable (a pre-marked cell is no box) |
| | cell holds two marks | D06 A11 | unverifiable |
| inserted mark | chosen box unticked (mark removed) | D33 A1 | fail |
| | tick moved to the neighbour | D33 A1 | fail |
| | two ticks for one single-choice answer | D33 A1 | fail |
| | pre-ticked printed default (`☒ YES` printed) | D33 A1 | unverifiable (a mixture under rule 2) |
| | an inserted ☑ instead of ☒ | D33 A1 | fail |
| | the inserted ☒ does not print (`w:vanish`) | D33 A1 | fail |
| | a mark beside no option | D33 A1 | fail |
| dropdown | dropdown shows another entry | D01 A7 | fail |
| | left and right swapped (right entry shown for left) | D01 A17 | fail |
| | placeholder shown again | D01 A7 | fail |
| | pre-selected default left shown | D01 A7 | fail |
| | a list entry removed | D01 A7 | fail |

\* The base is **synthesized**. The candidate's dev exports answer no content-control-checkbox question in
ground-truth terms, so the base is a copy of its D03 export with the first option's box ticked by hand, `chosen = [0]`.
It passes before mutation. Left/right questions exist in dev only for content-control checkboxes (D03) and one
dropdown (D01 A17), so "left and right swapped" is planted on those two kinds only. For the other kinds, "tick moved
to the neighbour" is the same shape of fault.

**Positive controls.**
- Unmutated D01, D07, D09, D15 and D33 ordinary exports pass whole, each with answered questions.
- Every mutant base passes, including after an lxml re-serialisation.
- With a pre-ticked original and the default correctly unticked, the question passes (four kinds).
- Every dev original checked against itself with nothing answered produces no `fail`.
- Every one of the >20,000 slots the corpus slot tool listed resolves to the element that tool named: kind, text,
  field type and glyph count.
- Synthetic `w:sym` packages read the table correctly and treat codes outside it as unreadable.
- A synthetic legacy dropdown (`FORMDROPDOWN`) passes when it shows the chosen entry. It fails on another entry,
  changed entries, or a change to an unanswered question. It is unverifiable when its cached result disagrees or its
  index is out of range.

**Sensitivity of the self-test.** `codemut_sensitivity.py` plants 16 code mutations in copies of `ticked.py`. It runs
the baseline first; the baseline passes. The fast suite catches all 16:
- the orphan rule
- the content-control display check
- the ☒-only inserted mark
- the inserted-mark scan
- the cross-question conflict guard
- unreadable glyphs read as unticked
- the cell-mark strictness
- the list-entry check
- word-bounded option text
- odd legacy values
- `w:sym` font handling
- symbol-font `w:t`
- hidden runs
- bordered blanks
- list bullets
- the legacy dropdown's cached-result check

The word-bound mutation survived at first, because no dev question exercises it. That is why
`PrintedTextTie.test_tick_on_not_sure_is_not_no` exists.

## Ambiguities for the declaration's owner

1. **Rule 2's first bullet versus "printed options with no box at all are read by the inserted mark".** Read
   fail-closed, an option slot must hold a box, so D04's lettered options (23 questions) and similar slots in D28,
   D29 and D30 are unverifiable. The engine fills these with a `☒ ` prefix, which the other reading would verify.
2. **Wingdings characters stored as text (`w:t`), not `w:sym`.** Read fail-closed, they are unreadable: D05's
   footer box, D28's circles. The table would read many of them if extended to `w:t`.
3. **Overlapping ground-truth questions.** A paragraph shared by two questions makes each question's boxes and marks
   the other's "boxes of no chosen option". Read literally, answering both fails one. D03 (A20 over A21–A25), D17's
   four placeholders in `p[7]`, and D38 `p[5]` have this shape. Exempting boxes and marks that another ground-truth
   question ties would be a deliberate relaxation, and it is not made here.
4. **How "the set the profile chose" is expressed in ground-truth terms** is undeclared. The text-only join leaves 330
   of 1,132 dev questions per profile with an unknown chosen set. Candidate labels like `(option 2)` (D10) can only be
   joined through the candidate's option order, and that order is the locator's; the declaration forbids using it.
5. **Radio circles** (○ ◉ ⃝, Wingdings 2 `81`/`99`) are outside the table the task fixed. Every radio-button form is
   unverifiable until the table is widened.
6. **Written answers in cells** (D06's 105 Yes/No/NA/ND cells, D29's Y/N label cells) are no declared box kind.
   They are unverifiable.
7. **Legacy dropdowns** (`FORMDROPDOWN`) occur nowhere in dev. Their reader is tested only on synthetic packages
   (`LegacyDropdown`). No real form has exercised it.
8. **The empty profile** is left to v1's package-identity check, as the declaration says. `ticked` does not run on it.
