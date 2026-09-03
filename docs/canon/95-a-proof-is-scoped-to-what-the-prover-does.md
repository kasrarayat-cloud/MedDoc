# A PROOF IS SCOPED TO WHAT THE PROVER DOES

**Standing 2026-09-03, ruling #173. The arc that produced it ran six rulings.**

> **State the claim the prover is in a position to make. Anything wider is a
> question for a different instrument, and building it into this one produces a
> guard that fails forever.**

## The arc, compressed

A renderer clears a field in a doctor's template and emits a proof that the
field is blank. The proof was written as *"this field renders blank"* — a claim
about the PAGE. Six formulations tried to establish it from the renderer's
chair:

| # | the rule | what falsified it |
|---|---|---|
| 1 | search the cleared region for numbering | the mark was on the containing paragraph |
| 2 | add the containing paragraph | it was on a named `w:pStyle` |
| 3 | resolve the style | it was reached through `w:basedOn` |
| 4 | walk the chain | it was on the DEFAULT style |
| 5 | read the default style | the zero-patch path never consulted the guard |
| 6 | invert to an inert-property allowlist | `w:docDefaults`, ST_OnOff spellings, an omitted `w:type`, the table-style layer, entity-encoded attributes, a second `w:pPr`, a carrier one level deeper |

Every fix was correct. Every one was evaded. **That is data about the
instrument, not about the diligence** — the same reading
[canon 75](75-three-falsifications-is-data-about-the-instrument.md) reached
after three.

## The resolution was a product statement, not a better algorithm

**Template-authored formatting is the TEMPLATE'S OWN CONTENT.** A list marker, a
border, a shaded cell, a style's `lvlText` are the author's choices, visible in
the author's own document — the same class as author-written default text the
renderer had always been allowed to leave in place.

So the claim was rescoped to what the writer actually knows:

> *the renderer wrote nothing into this field, and its region is byte-identical
> to the empty form the author uploaded.*

The guard was deleted. **Eligibility became a pure function of the field — kind
in, verdict out, no document reading** — and the absence of a document parameter
is the design, not an omission.

## ⚠️ WHAT MADE THE DELETION AN ENDING RATHER THAN A RETREAT

Three measurements, and without them this would have been a retreat:

- the apparatus **never reached `main`** — it lived entirely on one branch;
- on the only real customer template it guarded **nothing**: all 52 counted
  blank proofs came from a binding that never called it;
- it refused **56 of 56** real named tables in a 91-document census, because
  85.9% of table styles carry `w:basedOn` and the style Word applies to every
  inserted table is one of them.

**Deleting a guard is only safe when you can say what it was protecting.** Here
the answer was nothing, and it took a census to know that.

## The practice

- Write the proof's sentence first, in the prover's own terms. If it contains a
  verb the prover does not perform — *renders*, *displays*, *prints* — the
  instrument is already wrong.
- One exception survived the deletion, and its shape is the test: a cleared
  dropdown makes the PDF engine fall back to `listItem[0]`, printing a value
  nobody chose. **That is a false attestation produced by the writer's own
  write**, so it is inside what the prover answers for. The list marker was
  not.
- ⚠️ **A rescoped proof must SAY so where it is consumed.** The certification
  record states the narrower claim in words; a proof that quietly means less
  than its readers think is worse than one that refuses.
