# Independent long-question/signing refutation

## Frozen90c5 candidate — one concrete introduced finding

Reviewed `/opt/meddoc-pro/.worktrees/v1-word-long-questions` commit
`90c5aa7bfbab8e24722beb1189eee6043bd73ac3`, base
`e37e17f041cb9e080f2a8f176b2ad8b6930aa880`.
Engine SHA256 `92098300e175ba7cd8c5d7718e2bc6a6089dcc95ffe828580430157f98dc36b9`.
The worktree was clean and the engine snapshot was captured before author repair.

**Finding:** `rebuild/documents/word_v3.py:1988–1996` removes `the initial report`
before deciding whether the question is a signing area, then checks only the
whole word `sign` in its new explicit guard.

Concrete input: body paragraph `Please countersign the initial report?`, followed
by one empty, directly bordered, unmerged cell table. The exact base refuses the
box with a signing warning. The candidate emits one **automatic long_text field**
at `b/tbl[0]/tr[0]/tc[0]`, labelled with that full question, **without any warning**.
Countersigning requests an additional signature, so treating that destination as
an ordinary generated narrative area violates the stated signing boundary.

This case, original DOCX, both engines and outputs are preserved. Root and author
received it. The author's separately found cross-paragraph `the initial` + heading
`Report` case is not claimed as my independent discovery. Source ownership was
returned after capture;90c5 is not a passed finished review.

## Bounded controls already captured

Twelve synthetic cases were fixed before execution. The ordinary descriptive
initial-report question maps; plain sign, imperative initial and signature-noun
controls refuse. The exact root long-heading `DONOR ONLY` case now retains its
full187-character source context; the baseline context is empty. A1000-codepoint
astral question maps without shortening, while1001 refuses; manual1000-character
context stays complete and1001 refuses. Unknown heading ancestry visibly refuses.

A local/sibling table-heading probe produces `PATIENT ONLY > DONOR ONLY` on both
base and candidate. It is retained as raw evidence, **not an introduced finding
or a passed ownership claim**: the left cell also supplies a row label, so that
fixture does not independently resolve which source role should dominate.

Runtime: `/opt/meddoc-pro/.worktrees/v1-patient-evidence/rebuild/.runtime/word-long-refutation-20260927/`.
It retains `probe.py`, predeclared manifest, twelve blank synthetic documents,
full results/log, exact engine snapshots, and the root manual-context probe/red
result. No real corpus, holdout, provider, database, renderer or native Word was
used. Network connections were denied. No source edits were made in the author
worktree. Final verification awaits the repaired frozen identity.
