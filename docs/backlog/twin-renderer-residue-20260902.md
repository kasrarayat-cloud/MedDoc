# RESIDUE FROM #165's ADVERSARIAL PASS — measured, not fixed

**Filed 2026-09-02.** Five isolated lenses attacked ruling #165's finished diff.
Nine defects it INTRODUCED were fixed in the same commit, each with an arm that
reds against the pre-pass renderer. What follows is what the pass measured and
the commit deliberately did NOT change, so nobody has to rediscover it.

## PRE-EXISTING — not introduced by #165, and out of its scope

### 1 · `w:lastValue` is an ATTRIBUTE, so the cleanup is dead code

`renderer.ts` looks for a `lastValue` **element**
(`descendantXmlElements(comboBox, 'lastValue')`). ECMA-376 makes `w:lastValue`
an **attribute** of `w:comboBox` / `w:dropDownList`. Measured: a null-cleared
selection ships `<w:comboBox w:lastValue="L">` intact.

**It does not print** — the visible text clears correctly, so no document shows
a stale value and no blank proof is bought falsely. But the control's stored
state still says "Left" on a field the certificate attests as blank, which will
mislead the next person who reads the XML or reopens it in Word.

Fix: `removeXmlAttributePatch` on the combo/dropdown element. One line, plus an
arm asserting the attribute is gone.

### 2 · A checkbox keeps non-`w:t` carriers beside its glyph

A checkbox is deliberately never bounded-cleared — both its states PRINT, so we
write the unchecked glyph on purpose. But a `w:sym` sibling inside its
`sdtContent` survives, so the document can print `☐✔` beside
"Anticoagulation reviewed".

Its proof is `filled` and buys nothing, so certification is unaffected — but the
exclusion rationale ("both of its states print") does not account for extra
carriers, and the document is wrong.

### 3 · The compiler is blind to a cell-level content control

An SDT whose parent is `w:tr` yields **no field and no `unsupported` entry**, and
its content prints. Its row-level sibling is correctly flagged
`ROW_CONTAINER_CONTENT_CONTROL / blocksCertification: true`. `compiler.ts` is
untouched by #165. Two lenses reached this independently and neither could
construct an input that compiles a binding there, so it is recorded as a
structural observation rather than a demonstrated harm.

## INTRODUCED BY #165 AND ACCEPTED, with the reason

### 4 · A bookmark split across the control boundary is orphaned

A `w:bookmarkStart` inside `sdtContent` whose `w:bookmarkEnd` is outside it is
deleted by the clear, leaving an end with no start. `main` kept the start.

**Accepted for now:** Word tolerates the orphan; the cost is a broken
cross-reference to that bookmark. The fix is to carry `w:bookmarkStart` /
`w:bookmarkEnd` through the replacement alongside `w:pPr` / `w:rPr` — they are
non-printing, so they belong on the same allow-list. Not done here only because
no measured document exercises it.

## THE ONE THE OWNER SHOULD SEE — #165 rule 2's check may be unfalsifiable

`roundtrip-verify.ts`'s emptied-only byte comparison **reds nothing when
deleted** (measured: 687 passed with it replaced by `void expected; void actual;`),
and the harm its comment claims to catch is refused earlier by
`STATIC_INVARIANCE_FAILED`.

The structural argument: the verifier already asserts
`output === applyApprovedXmlPatches(source, allPatches)` byte-for-byte for the
whole part, and `assertPatchesWithinApprovedBindings` confines every field's
patches to its own binding span. So the only way an emptied span can diverge
from its expectation is a foreign patch inside it — which means nested bindings,
which die earlier as `PATCH_OVERLAP`.

⚠️ **This is canon 62 — a guard caught by a DIFFERENT guard than the one being
proved is unproved — and it is the same verdict #162(c)'s own isolation
experiment reached.** Ruling #165 reinstated the check on the grounds that its
gap (writer-blindness) was closed by rule 1. That reasoning is sound; what the
pass shows is that the check may have no reachable failure mode of its own.

**Not removed, because the owner ruled it in explicitly and the argument for
keeping it is defence in depth against a future change that weakens the
whole-part equality.** Surfaced here so the decision is made knowingly rather
than inherited.
