# FUTURE — template hygiene, gated on a principled printed-region model

**Filed 2026-09-02 by ruling #164 item 3, which RETIRED the first attempt.**

## The concept, which is still worth having

A doctor's template can carry content in a field that prints on every note where
that field is unfilled — a stale default, a placeholder, a leftover tick. Telling
them at UPLOAD, once, where they can fix it, is better than discovering it on a
signed note.

## Why the first attempt was retired rather than repaired

It shipped as two rules — a BLOCKING one (a selection control resting on one of
its own options) and a FLAGGING one (any visible leftover content). Both were
withdrawn. Six spellings of the same clinical state produced six different
verdicts:

| spelling | verdict it produced |
|---|---|
| `w:t` tick vs `w:sym` tick | blocked vs merely flagged |
| English vs localised placeholder | ignored vs **all 28 dropdowns blocked** |
| checkbox state elements present vs omitted | correct vs fail-open **and** false-positive |
| text vs a `REF` field code beside it | blocked vs missed |
| content control vs legacy | seen vs structurally invisible |
| scalar vs repeating | seen vs unreached |

⚠️ **The root cause is one question the implementation never actually answered:
WHAT PRINTS?** Every defect above is a different wrong answer to it. `visibleText`
is a *labelling* helper — it counts `w:instrText`, which is a field code and
never prints — and `w:ffData` is a field's *declaration*, not its result region.

## The gate on doing it again

**A principled printed-region model**, per binding type, that can say what a
given field renders when unfilled — and that is testable against the real
customer template rather than a fixture built by its author.

Until that exists, this stays filed. See
[canon 83](../canon/83-a-blocking-rule-may-never-rest-on-a-text-heuristic.md)
for the standard any BLOCKING version must meet, and
`renderer-legacy-clearing.md`, which needs the same model.
