# The claim I have NOT tested — ruling #170

**Written at the moment the four lenses launched, before any finding returned.**
Same honest timing note as #169's: *at launch* rather than *before the pass*,
which still precedes every result and so cannot be tuned to them.

## The claim

> **That `INERT_PARAGRAPH_PROPERTIES` — seven element names measured off one
> customer template — contains nothing that can put a mark on a page.**

Six of the seven are self-evidently typographic. The one I cannot fully
discharge is **`w:rPr`**, because it is a CONTAINER: it is the paragraph mark's
run properties, and I have asserted its inertness by asserting that no `w:r`
appears anywhere under `w:pPr`. That backstop is a claim about the SHAPE of what
hides there, not a proof that every possible `rPr` child is silent.

**What makes this weaker than it looks:** the allowlist is checked over DIRECT
children only. `w:rPr`'s own children are unchecked except by the `w:r`
backstop. If any `rPr` child can render — I know of none, and I have not proven
none exists — the guard grants credit over it.

## The second untested claim

> **That deleting the style-chain walk removed only a liability and not a
> capability.**

`w:pStyle` is now disqualifying, so no style is ever resolved. That is
strictly more refusing, which is the safe direction — but I have measured its
cost on exactly TWO documents. Both happen to carry no `pStyle` on any
control-bearing paragraph. **I do not know what fraction of real-world templates
put a `pStyle` on a control paragraph**, and on those the entire binding earns
nothing. The population is two, and two is not a distribution.

## The third, and it is the one that would hurt

> **That `unevaluated` is never written where a real verdict was available.**

Five paths carry `'unevaluated'`, chosen because the guard genuinely does not
run there. If I am wrong about even one of them — if it CAN reach a `blank`
proof on a document that deserves credit — the cost is a silent, permanent
refusal on a shape nobody will think to test, and it will read as "this template
just cannot certify."

## What would refute the first claim

A document where `blankEligibilityOf` returns `eligible` and the rendered
`word/document.xml` still carries a visible mark in that field's region. That is
what lens A is pointed at.
