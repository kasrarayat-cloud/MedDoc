# THE #173 FINAL PASS — the deletion held; the one kept guard did not

**Three lenses, isolated worktrees content-verified before launch (canon 88),
scoped to the only surface the ruling left: structure-keep clearing on
`content_control`.** Every finding below was re-measured by me or is reported
with the lens's own controls.

---

## ⚠️ 1 · THE ONE GUARD #173 KEPT IS BYPASSABLE BY DOCUMENT SHAPE

#173 deleted the numbering apparatus and kept exactly one exclusion: a selection
earns no blank credit, because an emptied dropdown makes the PDF engine fall
back to `w:listItem[0]` and print a value nobody chose.

**Verified by me — the same dropdown, three placements:**

```
CONTROL  direct child of w:sdtPr   irKind=single_select   -> filled  / refused
         inside mc:AlternateContent irKind=narrative_text  -> emptied / eligible / COUNTS
         inside a SECOND w:sdtPr    irKind=narrative_text  -> emptied / eligible / COUNTS
```

The live `w:listItem` **survives in the rendered output** in both bypass cases,
while the placeholder is cleared — precisely #168(b)'s measured harm. Driven to
the product verdict on the real consult-form harness: the bypass **CERTIFIED**
against a **BLOCKED** control.

⚠️ **THE ASYMMETRY IS IN OUR OWN COMPILER.** It resolves `checkbox` with
`descendants` **because Word wraps it in `mc:AlternateContent`** — so the
codebase already knows that wrapper is real — and resolves the other four type
markers with `directChild`.

⚠️ **AND "A SECOND ELEMENT OF THE SAME NAME" IS A CLASS THIS CODE HAS PAID FOR
TWICE.** A second `w:sdtContent` once rendered WARFARIN out of a control proofed
`emptied`; a second `w:pPr` defeated the numbering guard three rulings ago.
Nothing refuses a second `w:sdtPr`.

**The fix lives in the COMPILER — outside the permitted fix class.**

---

## 2 · A KEPT-WHOLE PROPERTY CONTAINER STILL HIDES A PRINTABLE CARRIER

**Verified by me:**

```
CONTROL clean                  -> emptied / eligible / COUNTS
w:sym       inside w:rPr       -> emptied / eligible / COUNTS   src=true out=true
w:drawing   inside w:rPr       -> emptied / eligible / COUNTS   src=true out=true
w:fldSimple inside w:pPr       -> emptied / eligible / COUNTS   src=true out=true
```

This is **#164's measured harm restored one element deeper** — the certification
blank requirement bought by a control that still carries a Wingdings tick.
`subtreeHasNoCharacterData` cannot see any of them: a tick is an *attribute*, an
image is a relationship id, a break is an empty element. The check watches text;
these carry none.

⚠️ **`w:fldSimple` needs no external authority** — this file's own comment says
*"an empty simple field is not inert, because the PDF engine may recompute it
from its `w:instr` and print a value nobody wrote."* It is deleted at a recursed
level and survives verbatim one element inside `w:pPr`.

⚠️ **THESE ARE NOT "TEMPLATE-AUTHORED FORMATTING" UNDER #173's PRINCIPLE.** A
`w:sym` inside `w:rPr` is schema-invalid — not an authoring choice — and the
file's own doctrine already answers it: *"a property block holding a run is a
document we do not understand."* The existing `w:r` refusal says exactly that;
it enumerates one carrier across fifteen kept-whole hosts.

**MEASURED: THE PERMITTED FIX CLASS DOES NOT CLOSE IT.** Removing `rPr` from the
keep-list closed one host while **ten others survived in the same run**;
removing `pPr` loses `w:sectPr` (the failure v1 and v2 died of) and removing
`rPr` re-introduces #168's measured loss of `w:rPr` on all 28 controls of the
real template. The remedy that fits is one more widening of the check already
there — *a kept-whole property container may contain only property elements*.

**And the outer `w:sdtPr` is never inspected at all**: a `w:r` bearing real text
there survives inside the span the proof attests, with `emptied` + credit —
verified by me. Removing `sdtPr` from the keep-list changes **nothing**
(measured), because that set is only consulted inside a function the outer
`sdtPr` never reaches. Honest limit: `docxToText` does not recover that string,
so it is a proof-integrity defect, not a demonstrated print.

---

## 3 · MY OWN CHARACTER-DATA CHECK IS HALF-ARMED, ON EXACTLY THE #164 SHAPE

The rule #173 added has three branches — the leading/between-sibling gap, the
trailing gap, and the recursion. **My three arms land on the trailing gap and
the recursion. The leading gap has no arm: neutering it reds 0 of 2377.**

```
<w:r><w:rPr><![CDATA[WARFARIN 5 MG DAILY]]><w:b/></w:rPr><w:t>…</w:t></w:r>

unmutated  -> filled,  drug in doc, NO credit
mutated    -> emptied, drug in doc, CREDIT    ← and no test sees it
```

That is the exact state the ruling exists to prevent, in the guard the ruling
added, unexercised. ⚠️ **The same shape the matrix caught once already this
commit** — the recursion was unarmed because the fixture tested depth one — and
I fixed that instance without sweeping the branch set.

---

## 4 · THE "READS NO DOCUMENT" ARM PROVES ONLY THE AXES ITS FIXTURE VARIES

The arm varies `pPr` content — `numPr`, `pStyle`, `pBdr`, `shd` — and is real on
those axes. **The CONTAINMENT axis is untested:** every `#173` fixture puts the
control in `<w:body><w:p>`. A rebuilt document-reading guard that refuses any
control inside a `w:tc` passes **2377 / 2377**, while flipping a real in-cell
control from counted to refused. The crude version (refuse whenever the part
holds a `w:tbl`) is caught — **by a `#165` neighbour, not by any `#173` arm.**
Canon 62 again.

**Three of six `#173` arms are also satisfied by an empty proof set** — their
claim is `not.toContain('emptied')` plus `.some(…) === false`, both true of
`[]`, with no non-vacuity floor. Their `#165` siblings carry one.

---

## 5 · BOTH INSTRUMENTS ARE STILL DEFECTIVE AFTER BEING REWRITTEN FOR BEING DEFECTIVE

**The lint:**

- its paren matcher can **run to EOF** when `//` appears inside a string literal
  (the stripper blanks the rest of the line, including the closing `);`), and a
  legitimate keyed selection later in the file then **exonerates the runaway** —
  a real offender goes green because unrelated correct code exists below it.
  *Today's corpus: 92 call sites, 0 runaways — latent, not live.*
- `stripComments` **corrupts real code**: a string containing `/*` opens a fake
  block comment that blanks everything to the next `*/`, demonstrated swallowing
  a real offender.
- **five laundering shapes go unwatched**, and the first is the worst:
  `filter(…)[0]` is **the lint's own remediation message minus the count** — a
  reader complying with the advice lands the identical defect.
- **false positive**: the forbidden shape inside a *string literal* reds the
  gate — the exact "trains the next reader to silence it" failure the comment
  stripping was added to prevent.

**The canon arm:**

- it checks **filename presence in a region, not "has a row"**. Deleting canon
  61's own **headline** row while keeping its `↳` sub-row leaves it **green** —
  and canon 61 is the entry my commit message cites as the mutation proof.
  **22 of 96 entries carry more than one reference, so ~23% of the corpus can
  lose its headline pointer undetected.** Canon 33: text presence is not
  membership.
- ⚠️ **its floor is self-referential and holed at total loss.** I wrote
  `expect(bodies.length).toBeGreaterThanOrEqual(bodies.length > 0 ? 90 : 0)`.
  88 bodies reds correctly; **0 bodies PASSES**, with all three arms green and
  `docs/canon/` emptied of all 96 entries. The message says *"a zero here is not
  health"* and the `: 0` branch exempts exactly zero. The lint's floor **33
  lines above**, `toBeGreaterThanOrEqual(55)`, is the correct unconditional
  form — both shapes are in one file, one screen apart.

---

## WHAT HELD

- The deletion itself: no dead symbols, `tsc` clean, 5631 passing, and the
  merge-base comparison shows counted proofs **identical** with the document
  differing by exactly the intended clearing delta.
- Character data in every form tried — bare text, CDATA in a gap, CDATA at
  depths 1 and 2, `w:delText`, `w:instrText`, `m:t`, entity references — refused.
- Nested `w:sdt` fails closed (`PATCH_OVERLAP`); scanner evasion via quotes,
  unbalanced tags and `<!DOCTYPE` all refused; `w:showingPlcHdr` removed from
  every descendant.
- The `emptied` byte-equality proof: the expectation is computed from the
  immutable source plus only this field's own patches, and a foreign patch in
  the span makes the hashes disagree. The `blank` source-byte-identity check
  held on every path tried.
- The recursion arm is genuine (M3 reds exactly it); the selection arm survives
  on its own first assertion; the lint reds on a real wrapped offender with
  `file:line` and does not flag a keyed selection; its 55 floor is tight.
