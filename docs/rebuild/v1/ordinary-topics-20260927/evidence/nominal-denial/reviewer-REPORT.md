# Independent finished ordinary-topic refutation

Reviewer: Astra `/root/word_recovery`.
Candidate source: `af8d45ab2f42c25d188a432c1ad3ea0281565e4f`, clean tree `/opt/meddoc-pro/.worktrees/v1-ordinary-topics`.
Base: `90808d5a3032286bedd9be2961dcabb6480a0358`.
Exact generation SHA-256 before/after: `b20785d78b780451d49cfacc5cdfa4e8bbdfea4612fae4d1118e4b52d9b84d45`.

## One introduced clinical release: a negative nominal Plan stops governing the opposite Assessment

`core/generation.py:2450-2458` treats a single complete colon-labelled nominal Plan as a narrative boundary after shape checks. At lines 2470-2473 this can establish a safe boundary even when the nominal statement contains explicit denial. The previous plain-value route did not grant that independence. The literal question-reference coupling does not link the statements because the Plan repeats the finding, not the printed question name `Assessment`.

Exact synthetic input on a form with unique Assessment and Plan long-text fields:

```
Assessment: infection.
Plan: no infection.
```

The provider simulation selects each complete labelled unit for its own field. Candidate output:

| Field | Status | Text |
|---|---|---|
| Assessment | supported | `infection.` |
| Plan | supported | `no infection.` |

The complete reviewed answers return no refusal from the shared decision reader. Independently constructed stored supported answers with exact full-unit evidence also remain supported on the page and return `[]` from `governed_decisions`.

Exact base holds Assessment as conflict/blank. The forced stored Assessment is also held by the base page reader, and its decision reader returns `['Assessment']`. Plan itself remains supported on the base, so the regression is the newly released Assessment context, not altered Plan wording.

A second exact-wording variant reproduces the same introduction:

```
Assessment: active bacterial infection.
Plan: no active bacterial infection.
```

This is a positive finding followed by its literal negation, with no medical synonym or inferred diagnosis needed. The source is internally contradictory or mislabelled and requires visible review; the new nominal boundary silently removes the previous review requirement. Both complete texts are retained, but their simultaneous supported status and lack of shared contextual refusal falsely treat the opposite findings as independent.

This report does not claim to implement or require a general semantic contradiction classifier. It demonstrates one unsafe release caused by the newly widened nominal boundary. The narrower positive medication/dose/physiotherapy example should stay useful when the boundary is repaired. Root must independently reproduce the finding before accepting it.

## Bounded controls that behaved as claimed

Ten synthetic repeated-topic cases used the real engine's two-knee fixture mappings. The ordinary settled-comment example now supports unique Indication while all repeated Pain/Comments destinations remain held. Left/Lt/(L), fullwidth and invisible-character side variants retain their holds, as do direct Indication references, correction, other-knee prose and a pointer.

Eight nominal-Plan cases compare exact candidate and base. The positive full naproxen dose/instructions remains intact and now releases the independent Assessment as intended. Question, pointer, correction, literal Assessment reference and conditional variants stay held. The two negation variants above are the only demonstrated unsafe new releases in this finite set.

A separate three-case forced-stored comparison confirms both negation variants in page/finalization governance and retains the positive Plan control. No repeated-destination assignment or text/offset loss was demonstrated in this pass.

## Evidence / reproduction

Runtime `/opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/ordinary-topics-independent-20260927/` retains:

- `probe.py`, `candidate.json`, `base.json`: all 18 finite generation controls.
- `nominal-forced.py`, `nominal-forced-candidate.json`, `nominal-forced-base.json`: the three stored-state comparisons.
- `generation-base.py`: exact reviewed base source; `generation-candidate.py`: exact candidate source.

```
/opt/meddoc-pro/.worktrees/v1-release/rebuild/.venv/bin/python \
 /opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/ordinary-topics-independent-20260927/nominal-forced.py
```

The script explicitly imports the topics tree and uses managed synthetic settings, fixture selections and unreachable database port 1. Override runs name the exact preserved base source; their disk hash still identifies the import location and is not the executed-base identity. No provider, database transport, unseen corpus, render, broad suite, app source edit, payment or deployment occurred. Sessions 55052 and 36226 completed exit 0; no reviewer process remains.

Next safe action: root verifies the exact same-phrase denial, author bounds nominal-topic independence accordingly, then replay these retained positives and refusals. All failed evidence remains preserved. B-G1 and broad V1 qualification remain open.
