# Fixed hyperlinks in Word content controls — September 28 continuation

This isolated repair continues `c55f5ffb` and the prepared workflow candidate `3ee445b8`.
It is local reviewed source, not an installed release or whole-document qualification.

Independent refutation demonstrated that a placeholder content control could remove a fixed
hyperlink, that a linked checkbox glyph could be changed, and that a native checkbox content
control could erase linked contact text. The first repair still allowed the native-checkbox
case; that failure was independently reproduced before the second repair. All first results
remain separate from the repaired outcomes.

Content controls containing fixed hyperlinks now expose their separately identifiable parts
instead of treating the whole control as one answer. A checkbox group that would change a link
is visibly left unassigned with its source location. Historical whole-control and linked-glyph
writers refuse before touching the protected content. Blank historical answers preserve the
original package. Ordinary blank areas, normal controls, and checkboxes beside linked option
text remain fillable and preserve the link text and relationships.

The previously added hyperlink test module was missing from the explicit CI document list.
It is now included, with the partition contract updated in the same change.

## Validation

- Final affected Word/question-box/hyperlink and dependency/CI/cost union: **157 tests passed,
  0 skipped, 93.640 seconds**. The earlier 155-test pass predates the native-checkbox repair
  and is retained with that scope, not counted again.
- Final focused hyperlink suite: **16 methods passed**. New coverage includes inline/block
  controls, text/dropdown/date controls, historical mappings, refusal before mutation, linked
  glyphs/native checkboxes, and positive controls for separate adjacent answers.
- Independent finished-diff refutation: **nothing further found within the bounded claims**.
  Six exact original documents plus the two first-repair checkbox originals were replayed.
  Original harmful mappings refuse with `protected_hyperlink`; positive controls still fill.
  Root separately reproduced the initial failures and replayed its captured originals.
- Final `word_v3.py` SHA256:
  `bc7933b67b044197c3ff632530af09ca5c8f9f32090a1f671b70fc46b6ebc7ff`.

The first author fixture included an unrelated trailing-colon answer area in its block case;
it was corrected before implementation and both runs are retained. The independent examples
were unaffected. No failure log or original observation was overwritten.

[Independent report](evidence/REPORT.md) and [text-evidence manifest](evidence/manifest.json)
retain the exact scope and provenance. Filled synthetic documents stay in the private runtime
listed by the independent artifact manifest and are not committed.

This covers OOXML hyperlink elements. Field-code hyperlinks, all other fixed instructions,
whole-form mapping, actual model generation, rendering/native Microsoft Word, and launch
acceptance are not established by these checks. D30/D31 original results and compatibility
counts are unchanged. No provider call, payment, deployment, main merge, or data reset occurred.

## Separate held batching work

Read-only refutation of `36d23068` found two additional whole-form constraint bypasses:
a preserved scalar priority can duplicate another answered priority, and an unrecognized
printed dropdown value can be treated as unselected. Root independently reproduced both.
That implementation is not included here. Original results and the exact probe are retained
under this worktree's `rebuild/.runtime/independent-batch/`; a separate isolated repair is in
progress and still requires its own finished-diff refutation. D10/R-T3 and ordinary context
work likewise remain held; no source from a dirty peer tree was integrated.
