# THE #174 PASS — admission is real; its membership and its LOUD half are not armed

**Three lenses, isolated worktrees content-verified before launch (canon 88).**
Every finding below was re-measured by me or is reported with the lens's own
population and controls.

---

## THE TWO ADMISSION COUNTS, INDEPENDENTLY CONFIRMED

Lens B censused **every `.docx` on this host** — 264 files, **91 unique by
content sha256**, 36 with a named producer — and drove all of them through the
real compiler. Encrypted volumes holding uploaded patient artifacts were
deliberately **not** swept.

| probe | result |
|---|---|
| content carrier inside a property block, anywhere | **0 / 18,814 property blocks** |
| controls with two `w:sdtPr` | **0 / 897** |
| controls with two `w:sdtContent` | 3, **all this repo's own probes; 0 real** |
| `UNSUPPORTED_CONTROL_STRUCTURE` in any real-producer document | **0** |
| **admission refusals across 539 real-producer controls** | **0** |

`WM IOV` **28 controls / 0 refusals**; the GI consultation note **35 / 0**. Four
instrument controls fired, plus a non-vacuity floor. **The 56-of-56 shape is not
reproduced.** And by driven test, a refused control's bytes are byte-identical
before and after render, with a neighbouring patched control as the control.

---

## ⚠️ 1 · THE "REFUSE LOUDLY" HALF OF #174 IS UNARMED — AND THE UI DOES NOT DELIVER IT

**Nothing measures the refusal's teeth.** Flipping `clinicallyMaterial` and
`blocksCertification` to `false` leaves **5638 passed, byte-identical to
baseline**. All five `#174` arms read only `ir.unsupported[].code`. With that
flag off, a template containing a control nobody understands **certifies
silently** — which is the exact product the ruling exists to buy.

**And the doctor-facing half is not built.** The compiler assembles the finding —
label `"Anticoagulation"`, the full reason, the XPath — and all of it reaches the
browser. The UI renders `blockingUnsupported.length` and nothing else, at both of
its two sites. It structurally cannot do better: the field list is
`ir.fields.map(...)` and a refused control is deliberately never in `ir.fields`.

So the doctor is told *"N elements can't be safely reproduced — simplify the
template in Word and re-upload"* while the string naming which control sits
unused in the payload. **One refusal disables certification for a 28- or
35-control form.**

⚠️ **MY OWN CODE COMMENT SAYS "visible to the doctor as a per-field finding."
That is not true today.**

---

## 2 · TWO HAND-MAINTAINED LISTS DESCRIBING THE SAME SET — THE ARC'S OWN DEFECT, AGAIN

Verified by me, mechanically:

```
compiler PROPERTY_BLOCKS      : 8   [pPr, rPr, sdtEndPr, sdtPr, tblPr, tblPrEx, tcPr, trPr]
renderer STRUCTURE_KEEP_WHOLE : 17
⚠️ COPIED VERBATIM BUT NEVER SCANNED (9):
   bookmarkEnd, bookmarkStart, commentRangeEnd, commentRangeStart,
   permEnd, permStart, proofErr, sectPr, tblGrid
scanned but not copied: []
```

Measured behaviourally, with a discriminating control:

```
CONTROL carrier in w:rPr (guarded)  refused=1  fields=0                    ✓
fldSimple in w:bookmarkStart        refused=0  fields=1  emptied  COUNTS   ✗
w:sym     in w:proofErr             refused=0  fields=1  emptied  COUNTS   ✗
```

`w:bookmarkStart` is what Word emits as `_GoBack` in essentially every document.
And `w:fldSimple` is **item 9 of the compiler's own `CONTENT_CARRIERS`** — the
compiler classifies the element as content and never looks inside the container
the renderer will copy.

**The terminal fix class closes it** — but the honest form is **one list,
derived, not two re-listed by hand**, or the divergence re-arms the next time
either grows.

---

## 3 · A GUARD THIS COMMIT DISARMED, AND MY OWN COMMENT NOTICED WITHOUT NOTICING

`renderer.ts`'s no-`w:r` refusal is live and reachable — via exactly the 9-name
gap above — and deleting it now reds **0 of 5638**. Demonstrated: a `w:sym`
inside `<w:sectPr><w:r>` goes from `filled` to a **verified `emptied` proof with
the tick still in the document** when the guard is removed.

⚠️ **Its only arm was rewritten BY THIS COMMIT** to assert
`bodyProofs.length === 0`, which the *neighbouring compile-time refusal* now
satisfies. My own test comment says *"this document no longer reaches it"* — and
I did not notice that left the guard unwatched. **Moving a refusal earlier
disarms the later one unless you replace its arm.**

---

## 4 · THE FIX THE MATRIX WAS CREDITED WITH IS ITSELF UNARMED

Last commit's matrix caught the `w:tabs` exemption being dead and I added `tab`
to the carrier set. **The full pre-fix state is green:** dropping `"tab"` reds 0;
widening the exemption to every position reds 0; both together red 0. Only
removing the exemption *while* `tab` stays a carrier reds — which arms the
exemption, not the membership.

⚠️ **And my "NON-VACUITY" control is laundered.** It uses
`<w:pPr><w:r><w:tab/></w:r></w:pPr>` — `w:r` is itself a carrier, so it refuses
as *"contains a w:r"* and **never reaches `tab` at all**. "Verified both ways"
was one way. Canon 62, inside the fix the matrix had just caught.

**More broadly: 24 of 27 carriers and 5 of 8 property blocks are dead members** —
`r` and `t` launder each other, so the sub-case labelled *"w:r in the outer
sdtPr"* passes with `r` removed. Cause: that sub-case asserts only
`refused.length === 1` while its sibling asserts the `detail`.

**And the recursion is unarmed** — every carrier fixture is depth-1, so removing
`propertyBlockCarrier`'s descent reds 0 while admitting
`<w:pPr><w:rPr><w:sym/></w:rPr></w:pPr>`, the paragraph mark's run properties,
where a tick legitimately nests. *Sweep the set, not the instance* was applied
to the renderer and not to the compiler. **4 of 5 type markers are likewise
unarmed.**

---

## ⚠️ 5 · MY `w:tabs` COMMENT IS FALSE IN BOTH HALVES

It claims *"the real customer template carries 52 of them… a flat denylist would
refuse every one of those 52 fields."* Measured on that exact file:

```
WM IOV: 128 <w:tabs> blocks · 28 w:sdt spans · 0 tabs blocks INSIDE a w:sdt
```

`admissionRefusal` only inspects property blocks **inside a control**, so not one
of the 128 can reach it. And the "52" is that template's `table_cell` count,
lifted from the wrong row of my own earlier measurement.

**The exemption is still necessary** — a real Word document on this host has
**12 of 12** `w:tabs` blocks inside its two content controls — which is exactly
why the false justification is dangerous: the next mutation matrix reports it
dead again, and the only argument against deleting it is a sentence that is not
true.

---

## 6 · TWO MORE, BOTH IN INSTRUMENTS I REWROTE

**The canon headline-row rule is defeated by a cross-reference.** Deleting canon
31's own headline row passes, because **canon 74's** headline row links to canon
31 and the check is a substring test. Control: deleting canon 33's row reds.
Same class as the sub-row defect I closed one commit ago, one level up.

**The AST lint misses 9 of 20 realistic spellings** — a named-function
predicate, `Array.prototype.find.call`, an aliased method, `isKind(f,'filled')`,
`list['find'](…)`, `for…of` with an early return, loose `==`, `.shift()`, and:

```ts
const m = list.filter((f) => f.kind === 'x');   // two statements
const one = m[0];                                //  → GREEN
list.filter((f) => f.kind === 'x')[0];           // one expression → REDS
```

⚠️ **All three compliant sites in the corpus use the two-statement form.** The
spelling the house actually writes is the one the lint cannot see.

---

## WHAT IS GENUINELY ARMED

- **Admission itself.** Deleting the early return reds 5 arms; each duplicate
  check reds its own arm asserting the `detail`; renaming the refusal code reds
  3; and **no `#174` arm is vacuous** under forced-empty `refused` or `fields`.
- **The renderer's full branch set** — leading gap, between-sibling, trailing,
  recursion and the self-closing early return each red individually, each naming
  its own arm, and the new arm carries a positive control so it is not vacuous.
  (Two older `#173` arms are negative-only and do survive an empty proof set.)
- **The lint's floor** sits exactly at the corpus and reds at 54; its fixture
  control genuinely touches disk. **The canon floor** reds at 89, passes at 90,
  and a new body with no row reds.
- **The refusal's plumbing:** a refused control yields one `unsupported` entry,
  one `unsupported` node, **zero fields**, no proof; the doctor's bytes survive
  exactly; compilation is idempotent.
