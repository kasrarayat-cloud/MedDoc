# BOUND THE EDIT WITH THE DOCUMENT'S OWN ELEMENT, NOT WITH YOUR SCAN

**Recorded 2026-09-02, owner ruling #165, after FOUR falsified attempts at one
requirement.** Sibling of
[canon 75](75-three-falsifications-is-data-about-the-instrument.md), which says
three falsifications are data about the instrument. This entry is what to do
once you have that data: it names the instrument that was failing, and the class
of instrument that was not.

## The four attempts, and the single thing they had in common

The requirement never moved: prove that a template can render a field EMPTY, so
a stale default cannot print into a signed clinical note.

| # | the construction | how it was falsified |
|---|---|---|
| #157(d) | "the region contains no `w:t`" | never looked at the right span for a legacy field, and enumerated VISIBLE element kinds — a list that grows forever |
| #162(c) | a locus table plus an allowlist | the attribute regex read a field the scanner never populates, so every empty legacy field HARD-FAILED the render |
| #163 | stop patching nulls entirely | a legacy stale line printed while being proofed blank — worse than what it replaced |
| #164 | count the proof's LABEL | a control holding a Wingdings tick was proofed `emptied`, verified, and BOUGHT the blank requirement while still printing the tick |

> **EVERY ONE OF THEM TRIED TO ESTABLISH EMPTINESS BY READING THE OUTPUT.**

And each died the same death: the next carrier nobody enumerated. `w:sym`,
`w:pict`, `w:drawing`, `w:object`, `w:delText`, `w:instrText`. **The list never
closes**, so an instrument built on it was never going to converge — which is
why the fifth attempt had to be a different KIND of instrument, not a better
version of the same one.

## The two moves that ended it

**1 · BOUND THE EDIT WITH THE DOCUMENT'S OWN ELEMENT.** A null now replaces the
whole `w:sdtContent` subtree. `startTagEnd..endTagStart` come from the XML
scanner; they are the control's own boundary. There is no carrier list, because
**a glyph, an image, a field code or a tracked deletion inside the control
cannot survive when nothing inside the control survives.**

⚠️ **THE DISTINCTION IS NOT "A BIGGER SPAN" — IT IS WHOSE SPAN IT IS.** #163's
falsification was widening a HAND-WALKED span to the part root, which on an
unbalanced `w:fldChar` ran past the field and erased a patient's allergy line
with every guard green. A wider scan of your own is more dangerous, not less.
The element's own bounds are the document telling you where it ends.

**2 · PROVE IT BY COMPARING BYTES YOU WROTE.** The writer records the sha256 of
the binding span as it intended to leave it; verification is one comparison
against the output. Stale content, a glyph, another field's patch and tampering
all diverge identically, and a correct empty passes by construction.

## ⚠️ AMENDED 2026-09-02 — THE MECHANISM ABOVE IS v2 AND WAS ITSELF FALSIFIED

**Superseded wording is kept, because in this programme the correction is the
point.** The entry says *"a null now replaces the whole `w:sdtContent` subtree"*
and *"nothing inside the control can survive, because NOTHING inside the control
survives."* Ruling #167 replaced that mechanism, and both sentences are now
false as written.

**What was wrong with it:** replacing a subtree means WRITING one, and a writer
must model everything it rebuilds. Two adversarial passes found seventeen ways it
did not — a hardcoded namespace prefix that made LibreOffice refuse the document;
`w:sectPr` kept only from the first paragraph when it conventionally sits on the
last; multi-paragraph content collapsed to one, moving a signature block 164pt; a
wrapped table deleted outright.

**v3 writes NOTHING and rewrites no start tag.** It emits deletion patches for
every node inside the control that is not structural skeleton, and keeps a
declared set of structural kinds — read `STRUCTURE_KEEP_WHOLE` and
`STRUCTURE_RECURSE` in `renderer.ts` rather than a count repeated here, which
went stale three times in one day. So *"nothing inside survives"* is replaced by something weaker and
true: **nothing inside survives EXCEPT declared skeleton, and skeleton is
required to be non-printing.**

**What SURVIVES from this entry, and it is the durable half:** *bound the edit
with the document's own element, not with your scan.* v3 still does exactly that
— the bounds are the control's own children, from the scanner. And the composition
argument below is unchanged: a correct write with no proof is an assertion, and a
proof with a blind writer is writer-blind. Only the shape of "correct write"
moved, from REBUILD to DELETE.

## ⚠️ NEITHER HALF IS SUFFICIENT, AND THAT IS THE PART TO CARRY

Byte-equality alone is **WRITER-BLIND**: it certifies faithfulness to the
writer's intention, so a writer that leaves a glyph behind bakes that glyph into
the expectation and the comparison passes. #162(c) shipped this half and its
blindness was its only gap.

A correct write alone is an **ASSERTION**: nothing checks that the output is
what the writer meant.

The guarantee is the composition — *make the intent correct by construction,
then prove the artifact equals the intent* — and either half shipped alone is
one of the four rows above.

## The generalisable test

> **When an edit's correctness depends on a list of things that might be there,
> you have the wrong instrument.** Ask instead: does the format give this region
> its own boundary? If it does, use it and the list disappears. If it does not —
> as with a legacy form field, whose result is a SPAN between two `fldChar`s
> with no enclosing element — then say so, and do not pretend a walk is a
> boundary. That honesty is why `legacy_form_field` is excluded rather than
> "handled".
