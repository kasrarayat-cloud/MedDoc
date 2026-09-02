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

## The practice

- Write the rule as *"keep X, delete everything else"* wherever the safe state is
  an absence.
- Put only structurally-guaranteed-safe things on the keep-list. `w:pPr` and
  `w:rPr` qualify because the schema gives them no printable children — that is
  a property of the format, not a judgement about a document.
- Say the asymmetry out loud in the code, because the next reader's instinct will
  be to "improve" it by enumerating the other way.
