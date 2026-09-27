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

## Finished follow-up — cf04596e

**NOTHING FOUND in the bounded finished follow-up.** Reviewed source
`cf04596ed841064bb883af579e64c444cd462a08`, engine SHA256
`3f2ca5136a876d153b045e5c8dd37b8b8b24b303833263966664c63290a3b856`.
The author was adding documentation only; application source matched this hash.
The earlier countersign failure above remains preserved, not replaced.

The follow-up reads the twelve original synthetic artifacts without regeneration
and verifies their hashes. The countersign question now visibly refuses. The
author's exact heading`Report` / question`Please provide the initial` boundary
was independently constructed and also refuses. The ordinary descriptive
source-reference question remains mapped. Signing noun/imperative controls,
1000/1001-codepoint boundaries, complete manual Donor context and unknown-scope
refusal retain the declared outcomes. Eleven original controls and the added
boundary satisfy their checks; the twelfth original sibling/row observation
remains explicitly ungraded, with identical base and finished metadata.

The completed five-case context-ownership probe invokes the actual mapping
validator and actual pure Word locator, using a synthetic blank package and
request-bound compact response. It replaces only the service wrapper and path
lookup, and uses no database or provider:

| Case | Finished result |
| --- | --- |
| Exact locator, including fingerprint and target | Full prior context inherited exactly. |
| Changed prior fingerprint | Newly derived `Actual source section`; prior context not inherited. |
| Changed prior write target | Newly derived context; prior context not inherited. |
| Descendant paragraph destination | New locator and newly derived context; prior context not inherited. |
| Foreign cell destination | ValidationError before adoption. |

Read the final delta for separate question/section signing evaluation and the
narrow temporal/source-reference exception. No additional destination, signing
or context-loss defect was demonstrated in this review. This is a bounded
refutation outcome, not proof of every possible signing phrase or Word layout.

The author reports17 final question-box tests passing and unchanged complete D30
fields/warnings, allowing reuse of its previous workflow evidence. Those tests,
real D30 source and workflow/render checks were not rerun by this reviewer.
Whole D30 and broad Word acceptance remain separate unfinished release gates.

Tracked final evidence: `word-long-independent-evidence-20260927/final/`.
Runtime subdirectory `word-long-refutation-20260927/final/` retains the final
engine and boundary artifact; the parent retains the twelve original artifacts,
first failed engine/outputs, synthetic locator source and exact locator results.
Both finite probes completed normally. No source changes, active process,
database use, provider spend, corpus/holdout access, render/native Word check,
deployment, push or merge occurred.
