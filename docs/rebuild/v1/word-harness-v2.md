# Word evaluation harness v2: ticked-option verification (declared before the qualification run)

Declared 2026-09-27, before any output of a repaired candidate on the qualification cohort exists and
before the qualification cohort's ground truth is opened by anyone. This page changes how a
qualification run is scored. It changes nothing already recorded.

## Why

Harness v1 (`word-eval/fill_eval.py`, `final_eval.py`) never checks a choice, multiple-choice or
checkbox answer. Its `landed` check skips them (`fill_eval.py`: answers are looked for only when the
kind is not `choice`/`multi_choice`, and a checkbox answer is `True`, not text). So an export that
ticks the wrong box, ticks two boxes for one answer, or leaves the chosen box empty passes every v1
check. Round 1 of the Word refutation showed each of these shapes was reachable in the engine (left
became right for `Rt.`/`Lt.` options; a box number was ignored; a box could not be unticked). The
engine now reads every answered option back and refuses the export on disagreement
(`word_v3.verify_options`), but that is the engine checking itself with its own readers. The release
gate needs an independent reader.

## What v2 adds: the `ticked` check

For every ground-truth answer area of kind `choice`, `multi_choice`, `checkbox` or `checkbox_group`,
in every filled profile (ordinary and long; the empty profile checks only that nothing changed):

1. **The reader is the harness's own.** It uses `zipfile` and `lxml` only and never imports
   `word_v3` or `core`. It reads the EXPORTED package at the ground-truth slots, and the ORIGINAL
   at the same slots for comparison. A box's state is read as:
   - content-control checkbox: `w14:checkbox/w14:checked/@w14:val` in `{1, true}`;
   - legacy form field: `w:ffData/w:checkBox/w:checked` (absent `@w:val` or a true value), else
     `w:default`;
   - printed glyph: the box character in its run, by a fixed table of ticked and unticked
     characters (Unicode and the Wingdings / Wingdings 2 `w:sym` codes) declared in the harness file;
     any glyph outside the table is **unreadable**;
   - a cell mark: a cell empty in the original that now holds exactly one of `X x ✓ ✔ ☒`;
   - an inserted mark: a `☒` immediately before an option's printed text (whitespace aside) that
     the original does not have there;
   - a dropdown (content control or legacy): the shown text equals the chosen option's text, and
     the list entries are unchanged.
2. **Options are tied to boxes from the original and the ground truth alone**, never from the
   candidate's locator:
   - one slot per option (`len(slots) == len(options)`): option i is slot i, and the slot must hold
     exactly one box or control;
   - otherwise, each option's printed text is found in the slots in document order (case- and
     whitespace-insensitive, first unused occurrence); its box is the one immediately before it in
     the same paragraph with no other option between. If no option has a box before it, the box
     immediately after is used for all; a mixture is **unverifiable**. Printed options with no box
     at all are read by the inserted mark.
3. **Pass, per question:** the set of options read as ticked (or shown) equals exactly the set the
   profile chose, and every box in the question's slots that belongs to no chosen option is
   unticked. For a question the profile leaves unanswered, every box keeps the state it has in the
   original.
4. **Fail closed.** A question whose boxes cannot be tied to its options under rule 2, or whose
   state is unreadable, is **unverifiable**, and an unverifiable question fails the document for
   automatic success. It is reported by name and reason; it is never skipped.

A `ticked` failure is a wrong destination or a changed meaning, so it is release-blocking in the
sense of `word-compatibility-target.md`, whatever the aggregate.

## What v2 does not change

- Every v1 check stays, with its meaning: `ticked` can only take documents out of the success
  count, never add one.
- The first-pass results recorded for candidate 1 on the development set and the holdout
  (`word-candidate-freeze-1.md`, `word-holdout-first-pass-1.md`) are not re-scored in place. If they
  are ever re-scored under v2 for information, that is reported separately and labelled v2.
- The LibreOffice render stays evidence of layout, not of ticks: its text layer does not reliably
  carry glyph or control states, so ticks are judged from the XML only.
- Native Word acceptance still needs the owner's desktop session.

## Order of work, fixed now

1. The `ticked` reader is written in `word-eval/` and self-tested on the **development set only**:
   a candidate export must pass, and planted mutants of it (the chosen box unticked, a neighbour
   ticked, two ticks for one answer, left and right swapped, a pre-ticked printed default left
   ticked beside the answer, a dropdown showing another entry) must each fail. The mutants are
   applied to copies and each is checked for having applied.
2. The harness files' sha256 are committed in a follow-up to this page before any qualification
   output exists.
3. The qualification run uses exactly those files. Every attempt and every failure is reported,
   with the unverifiable questions listed per document.

Until step 2 is committed, no qualification run is started.
