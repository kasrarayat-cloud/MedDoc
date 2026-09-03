# `table_cell` (and legacy) — ELIGIBLE IS NOT EMPTY

**Filed 2026-09-02 by ruling #171(2). Deferred with its cure named, not shrugged off.**

## The defect

`table_cell` and `legacy_form_field` earn counted blank credit while a printable
carrier survives in the region.

Nothing clears either: `tableCellPatches` and `legacyFieldPatches` rewrite
`w:t` only. A cell holding a carrier and **no** `w:t` yields ZERO patches, takes
the zero-patch `blank` path, and counts — with the mark still in the rendered
`word/document.xml`.

Measured, all counting, all surviving in the output:

| carrier | verdict |
|---|---|
| `w:sym` (a Wingdings tick) | `blank` · counts · **survives** |
| `w:drawing` | `blank` · counts · **survives** |
| `w:pict` | `blank` · counts · **survives** |
| `w:object` | `blank` · counts · **survives** |
| `w:fldSimple` (` QUOTE "…" `) | `blank` · counts · **survives** |

⚠️ **THE DECISIVE CONTROL, and it is what makes this a scoped defect rather than
a mystery:** the SAME `w:sym` inside a `content_control` is **deleted** from the
output. The harm is specific to the two bindings that perform no clearing write.

## It predates the arc that found it

`main` returned `blankEligible: true` hardcoded for both bindings and `blank`
counted, so this counted then too. It is **not** a regression introduced by the
#165–#171 work; that work is what made it visible.

## ⚠️ CORRECTION — THIS DOC MEASURED THE WRONG LIMIT

**Added 2026-09-03 (#172(5)), because the original defect statement was
mis-scoped and the population claim was made about the wrong set.**

The section below measures the **CARRIER** limit (`w:sym`, `w:drawing`, …) and
names its re-arming condition as a glyph, a logo or a signature image. That is
one true limit. **But the guard #171 deleted from these bindings watched
NUMBERING**, and this doc never named a numbered cell.

*"The limit predates this arc"* is true of `main` and obscures that the
immediately preceding commit had closed the numbering half. Both halves are
open again, deliberately, and both belong here:

| shape | `main` | #170 | now |
|---|---|---|---|
| a cell in a `w:numPr` paragraph | counted | **refused** | counted |
| a cell naming a numbered `w:pStyle` | counted | **refused** | counted |
| a legacy field in a `w:numPr` paragraph | counted | **refused** | counted |
| a cell holding `w:sym` / `w:drawing` and no `w:t` | counted | counted | counted |

**THE MEASUREMENT THAT WAS MISSING, supplied by the pass:** of WM IOV's 52
`table_cell` fields, cell paragraphs carrying `w:numPr` = **0** and `w:pStyle` =
**0** — positive-controlled, since **6** body paragraphs in the same file DO
carry `w:numPr`, so the probe is not blind. The population claim is true. It was
made about the carrier set and is now made about both.

## Population, with its re-arming condition

**Zero on every certified template**, measured: the real customer form carries
none of `w:sym / w:drawing / w:pict / w:object / w:fldSimple` in any of its 52
blank-bearing cells.

⚠️ **It re-arms on any upload with a glyph checkbox, a logo, or a signature
image in an otherwise-empty cell** — none of which is exotic in a clinical form.
This is a fact about today's corpus, never a property of the code.

## THE CURE IS ALREADY NAMED

**`w:tc` IS A BOUNDED CONTAINER.** The structure-keep clear that made content
controls provable — keep only the structural skeleton, delete every other node
including unknowns, write nothing, rewrite no start tag — applies to it
directly. That is the whole reason this is a deferral: the mechanism exists and
has been through four adversarial passes on the sibling binding.

`legacy_form_field` does **not** get this cure. Its result is a SPAN between
`separate` and `end` fldChars with no enclosing element, and every attempt to
bound it by walking has been falsified — including #170's, which judged one
paragraph of it. Legacy needs a real container before it needs a guard.

## Definition of done

- `w:tc` content cleared by structure-keep, with the same arms the content
  control path carries;
- `table_cell` re-enters the eligibility guard, with the ALL-quantifier armed on
  a MULTI-paragraph cell (the #170 fixture had one paragraph, so `.slice(0,1)`
  redded nothing);
- the accepted-limit arms in `gate-165-bounded-clearing.test.ts` (`#171 —
  table_cell and legacy LEFT THE SLICE`) are REVERSED in the same commit, since
  they pin today's limit deliberately and will red when it closes.
