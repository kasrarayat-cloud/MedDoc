# ENUMERATE WHAT TO KEEP, NEVER WHAT TO DELETE

**Recorded 2026-09-02, owner ruling #165.** The companion to
[canon 85](85-bound-the-edit-with-the-document-s-own-element.md): that entry says
bound the edit with the document's own element, and this one says what to do
when you must still enumerate something inside that boundary.

## Both directions are lists. Only one of them fails safely.

Five instruments in this arc enumerated **what to DELETE** — the visible carriers
that must not survive a cleared field. Every one was falsified by the next
carrier nobody named: `w:sym`, `w:pict`, `w:drawing`, `w:object`, `w:delText`,
`w:instrText`. The list never closes, and each miss meant **clinical content
printed into a document a doctor signs**.

The sixth instrument enumerated **what to KEEP** — the property containers
(`w:pPr`, `w:rPr`) that define how an empty field looks — and deleted everything
else.

> **AN INCOMPLETE DELETE-LIST PRINTS CLINICAL CONTENT.**
> **AN INCOMPLETE KEEP-LIST COSTS FORMATTING.**

Same shape, same fallibility, incomparable consequence. The keep-list is
*allowed* to be wrong, because being wrong makes the output emptier rather than
fuller.

## ⚠️ AND THE TEST IS NOT WHICH LIST IS SHORTER

The delete-list is usually shorter and always more tempting: it names exactly the
thing you just saw go wrong. That is why five attempts reached for it. Ask
instead:

> **When this list is missing an entry — and it will be — does the mistake make
> the output MORE like the safe state, or LESS?**

Here the safe state is *empty*. A keep-list that forgets `w:rPr` yields a field
that is empty and unstyled. A delete-list that forgets `w:sym` yields a field
that prints a tick beside "Anticoagulation reviewed" while being proofed blank.

## The evidence, both directions measured

**The delete-list direction**, over four rulings: #157(d) matched `w:t` only;
#162(c) added a locus table and an allowlist whose regex read a field the scanner
never populates, hard-failing every empty legacy field; #163 stopped patching and
printed a stale line; #164 counted a label and certified a control holding a
Wingdings tick.

**The keep-list direction**, the same night it shipped: the first version kept
nothing, and an adversarial lens measured the cost through the product's own PDF
converter — row pitch 10.75pt → 14.20pt, table height +32.5%, a 48-row form
spilling from one page to two, and a doctor typing into an emptied control
getting the document default instead of the template's Times New Roman. **Real,
visible, and worth fixing — and not once did content survive.**

## ⚠️ CORRECTION, 2026-09-02 — THE JUSTIFICATION ABOVE OVERSTATES ITS GUARANTEE

The entry says property containers are safe *"because the schema gives them no
printable children — that is a property of the format, not a judgement about a
document."* **The first clause is true of the FORMAT and false of this
IMPLEMENTATION**, because the code copies the property subtree **verbatim**
without validating it against the schema. Nothing in the pipeline does.

Measured by an adversarial lens, a block-level control with a run smuggled
inside `w:pPr`:

    KEEPLIST  src_has_WARFARIN=true  out_has_WARFARIN=true
              proofKinds=emptied  verified=true  countsAsBlank=true

Content survives a control proofed `emptied` and buys the certification blank
requirement — the #164 shape, re-created one layer inside the fix for it.

**HONEST LIMIT, because the severity must not be overstated either:** that input
is schema-invalid, Word will not author it, and no production document is known
to contain it. What is refuted is the entry's ABSOLUTE claim, not the practice.

**What survives, and it is the whole point of the entry:** the ASYMMETRY. A
keep-list that is wrong makes the output emptier; a delete-list that is wrong
prints clinical content. That argument does not depend on the keep-list being
infallible, and this correction is an instance of it — the failure mode of a
wrong keep-list turned out to be "something survived a schema-invalid input",
not "the doctor's note is wrong".

**What must change in how the entry is read:** *"structurally guaranteed safe"*
is a claim about validated input. Where nothing validates, the keep-list is a
judgement about the document like any other, and it should say so — or the copy
should be reconstructed from parsed properties rather than sliced raw.

## The practice

- Write the rule as *"keep X, delete everything else"* wherever the safe state is
  an absence.
- Put only structurally-guaranteed-safe things on the keep-list. `w:pPr` and
  `w:rPr` qualify because the schema gives them no printable children — that is
  a property of the format, not a judgement about a document.
- Say the asymmetry out loud in the code, because the next reader's instinct will
  be to "improve" it by enumerating the other way.
