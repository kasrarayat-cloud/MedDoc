# Finished paired-cell spacing diff: REFUTED

Candidate a921dfc312acbd6b9ad08b198720a08253481301, base4caa34431a60e6ce3409ecadbbb6989b50659d7b.
Engine SHA2569a25be7e3fd947e2069fc0be6cc6bc3c3bb964fe26dbb3ec52daf011fab67bd1.
Author tree was read-only. Exact git source snapshots, synthetic originals and
first outputs remain in `/opt/meddoc-pro/.worktrees/v1-notes-workflows/rebuild/.runtime/word-paired-independent-20260927/`.
No corpus, patient, provider or DB operation.

## Demonstrated finding

`rebuild/documents/word_v3.py:2135` defines the markers that prevent suppression;
`word_v3.py:2233` discards the detected left paragraph when all blanks pass that
check. The marker set omits paragraph/run shading, highlight and numbering.

Input: one two-cell table row. Left cell has `Past medical history:` and one
empty paragraph with direct `w:shd w:fill="D9D9D9"`; right cell is empty. The
marked paragraph is an answer area under the label, or at least an ambiguous
marked area requiring visible review. Exactbase exposes the left paragraph
`b/tbl[0]/tr[0]/tc[0]/p[1]` and right answer cell. Candidate silently returns only
`b/tbl[0]/tr[0]/tc[1]`, with `notes: []`. This contradicts preservation of marked
and ambiguous areas.

The same2→1 omission is reproduced for inherited paragraph shading, a highlighted
run of spaces, and empty List Number/List Bullet paragraphs (their visible list
markers come from numbering rather than `w:t`). No input or expected meaning was
changed between base and candidate. Plain spacing correctly changes2→1; an
underlined-space positive control keeps both fields. All7 first outcomes are in
`probe.json`; `probe.py` rebuilds the independent synthetic controls.

No integration approval. Lead was asked to independently reproduce; repairs
need a new frozen candidate and bounded replay of these exact artifacts.

## Final bounded follow-up — finding closed

Final649f65c2bd32b5b994611de91f9cb24cd6522034, engineSHA256
`c82ef298b59780238c4f995c6da4056d87ca939282b62c15e74ef185f362cad8`.
Read the finished marker-set-only follow-up. Independently replayed all7 exact
original synthetic DOCX bytes (hashes asserted before inspect). All5 marked
failure variants now equal base fields/notes; the underlined control remains
unchanged; unmarked spacing still yields only the intended right answer cell.
`replay-final.json` retains every actual map and expected-equality assertion.

**NOTHING ELSE FOUND** within this bounded finished-diff/source-marker scope.
Earlier failed candidate and every first result remain. This is not a corpus,
render, native Word, clinical-generation or whole-document compatibility result.
