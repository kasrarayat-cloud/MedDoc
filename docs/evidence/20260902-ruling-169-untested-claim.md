# The claim I have NOT tested — ruling #169's guard

**Written 2026-09-02, at the moment the four lenses were launched and BEFORE any
finding had returned.** Canon 27 asks for this *before* the pass; the honest
timing is *at launch*, which still precedes every result and so cannot be tuned
to them. Recorded here rather than smoothed, per the same logic §2.5 applies to
a deploy declaration: the value is that the answer was fixed before the evidence
existed.

## The claim

> **That the four resolution routes `paragraphNumbering` walks — the cleared
> region, the containing paragraph, the `pStyle` chain to its root, and the
> default paragraph style — are ALL the routes by which a numbering mark can
> reach a field's paragraph.**

Six routes have been found by measurement, each after a fix that closed the one
before it. **I have no evidence that the seventh does not exist.** What I have is
an inversion that is supposed to make the seventh harmless: anything the walk
cannot resolve is INELIGIBLE, so a route I failed to imagine should surface as a
refusal rather than as a false grant.

**That safety property is itself untested in the only way that matters** — I
cannot construct the route I have not thought of, so I cannot demonstrate the
inversion catches it. The argument is structural, and it is stated here as
structural rather than dressed as a measurement.

## What would refute it

A document where numbering reaches the rendered page and `paragraphNumbering`
returns `clear` — not `unresolved`, `clear`. That is the whole target, and it is
the one claim all three numbering lenses were pointed at.

## The second, smaller untested claim

**That `numId="0"` is safe to keep as the sole exclusion.** It is Word's
documented "no list" and the reasoning is explicit. But its cost is real — Word's
built-in `Subtitle` carries that shape — and I verified only that neither tracked
customer template applies `Subtitle` to a control-bearing paragraph *today*. That
is a population fact, not a property of the code, and the path re-arms the moment
a doctor applies that style. Named here so it is not read as more than it is.
