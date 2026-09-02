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

The sixth instrument enumerated **what to KEEP** — the structural skeleton — and
deleted everything else.

⚠️ **AMENDED 2026-09-02: the keep-list is no longer `w:pPr`/`w:rPr`.** That was
v2, which rebuilt the container and copied two property elements into what it
wrote. Ruling #167's v3 writes nothing, so the keep-list is thirteen STRUCTURAL
kinds — `p tbl tr tc sdt sdtContent` recursed, `pPr tblPr tblGrid trPr tcPr
sectPr sdtPr sdtEndPr tblPrEx permStart permEnd bookmarkStart bookmarkEnd
proofErr commentRange*` kept whole — and **`w:rPr` is not among them**: a run's
own properties go when the run goes, because the run is content. The asymmetry
argument is untouched by that; only the list changed.

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

## ⚠️ REFINEMENT, 2026-09-02 (ruling #168) — SOME PROPERTIES ARE CONTENT GENERATORS

The asymmetry above says a wrong keep-list makes the output **emptier**. That
holds for properties that only DESCRIBE how content looks. It fails for a
property that CAUSES content to appear, and there are at least three:

| kept as a property | what it generates |
|---|---|
| `w:numPr` | a list marker from `numbering.xml` — and `w:lvlText` is arbitrary literal text, measured printing `ANTICOAGULATED 1.` |
| `w:dropDownList` / `w:comboBox` | the engine falls back to `w:listItem[0]`, printing a value nobody chose |
| `w:showingPlcHdr` | tells Word to re-display the template's own prompt |

For these, keeping is **not** the safe direction: the output gets FULLER.

> **BEFORE PUTTING SOMETHING ON A KEEP-LIST, ASK NOT "IS IT A PROPERTY?" BUT
> "CAN IT PUT A MARK ON THE PAGE BY ITSELF?"** A property that generates is
> content wearing a property's schema position.

**AND THE RESOLUTION IS NOT ALWAYS TO DELETE IT.** Removing `w:numPr` renumbers
the doctor's list *beyond* the field — damage outside the thing being cleared,
which is the failure mode #163 died of. So #168 splits the question:

- **the RENDER keeps it**, because deleting it damages more than it fixes;
- **the COUNT refuses it** — a field whose cleared region carries a generator
  cannot claim blank, with no parsing and no heuristic about which generators
  are "harmless".

`w:showingPlcHdr` is the third case and resolves the other way: it generates,
removing it damages nothing, so it is deleted outright.

**The asymmetry survives, restated:** an incomplete keep-list costs formatting
*provided every member is inert*. Membership is the claim that needs the
evidence, and "it sits where a property sits" is not that evidence.

## The practice

- Write the rule as *"keep X, delete everything else"* wherever the safe state is
  an absence.
- Put only structurally-guaranteed-safe things on the keep-list — **and read the
  2026-09-02 correction above before trusting that phrase.** The schema gives
  property containers no printable children; the CODE copies them verbatim and
  validates nothing, so the guarantee is about the FORMAT and not about the
  input. v3 therefore adds one structural check rather than trusting the claim:
  **a kept-whole property container must contain no `w:r`.** A run is the
  universal carrier of printable content, no property block legitimately holds
  one, and a document that does is refused rather than repaired.
- Say the asymmetry out loud in the code, because the next reader's instinct will
  be to "improve" it by enumerating the other way.
