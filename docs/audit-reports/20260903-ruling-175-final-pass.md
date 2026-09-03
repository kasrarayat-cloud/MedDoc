# The #175 final pass — the admitted set loses two shapes it never understood

**Date:** 2026-09-03 · **Lens:** adversarial, terminal pass of the ten-ruling arc
**Worktree:** `/opt/meddoc-pro/.p175-a` · **Base:** `07af70c2`

**Verdict: NOT `NOTHING FOUND`. Two findings, both demonstrated end-to-end
against the real compiler and the real renderer, both closed in this commit by
the pre-declared remedy — a shape LEAVING the admitted set.**

The single question was: *find a content control that is ADMITTED, where content
survives into the rendered output while the field earns COUNTED blank credit.*
It answers YES twice. In both cases the control compiled to a `narrative_text`
field, the content survived **verbatim into `word/document.xml` inside that
field's own binding span**, the field earned an `emptied` proof with
`blankEligible: 'eligible'`, `countsAsBlankProof()` returned **true**, and
`rendered.verification.verified` was **true**.

---

## FINDING 1 — `CONTENT_CARRIERS` was meant to be `EG_RunInnerContent` and was missing fourteen of its members

**`src/lib/note-template-docx/compiler.ts:312`** — `CONTENT_CARRIERS`.

### Input

```xml
<w:sdt>
  <w:sdtPr><w:id w:val="900"/><w:alias w:val="Anticoagulation"/><w:text/></w:sdtPr>
  <w:sdtContent>
    <w:p><w:r><w:rPr><w:dayLong/></w:rPr><w:t>Enter anticoagulation</w:t></w:r></w:p>
  </w:sdtContent>
</w:sdt>
```

### What happens

`refused=0 · fields=1 · proof=emptied/eligible · countsAsBlankProof=true ·
verified=true · <w:dayLong/> present in the output`.

The position is not arbitrary — it is the one the **#174 pass already measured**
a `w:sym` surviving and printing from. `w:r` is in `STRUCTURE_RECURSE`, so the
run shell is kept; its `w:rPr` is in `STRUCTURE_KEEP_WHOLE`, so it is **copied
verbatim**. `subtreeHasNoCharacterData` (renderer.ts:862) passes — a
self-closing element is not character data. `propertyBlockCarrier`
(compiler.ts:421) passes — `dayLong` was not in the set.

Measured admitted-and-counted, one row each: **`w:cr`, `w:pgNum`,
`w:dayShort`, `w:dayLong`, `w:monthShort`, `w:monthLong`, `w:yearShort`,
`w:yearLong`, `w:annotationRef`, `w:footnoteRef`, `w:endnoteRef`,
`w:contentPart`, `w:subDoc`** — plus `w:delInstrText` and `w:altChunk` by the
same route, and `w:lastRenderedPageBreak` which is inert.

### What should happen

Every one of these is a **legal child of `w:r`** — the schema itself says they
print. Each should refuse at admission, exactly as `w:sym` and `w:br` do.

### Why harmful

Six of them render **text into a field the certificate attests is blank**.
`w:pgNum` prints a page number; the six date elements print **today's date** —
so a signed clinical document carries a date nobody dictated, in a field whose
certification says it is empty. `w:contentPart`, `w:subDoc` and `w:altChunk`
pull an entire external part into the note. `w:cr` prints a line break.

⚠️ **AND THE COMPILER ALREADY KNEW ABOUT ONE OF THEM.** `visibleText` in
`xml.ts:135` maps `w:cr` to a newline **beside `w:br`** — the text extractor
classified it as content while `CONTENT_CARRIERS` did not. That is the #175
defect itself, one file over: two lists describing one set.

### Does the pre-declared remedy close it

**YES — names joining `CONTENT_CARRIERS`, which is the remedy's first arm
verbatim.** Fixed **by ground, not by hit** (canon 68): the enumeration is
completed against the whole `EG_RunInnerContent` group, including
`w:lastRenderedPageBreak`, which failed in no probe but sits on the same wrong
side of the same boundary.

---

## FINDING 2 — character data in the control's OWN `w:sdtPr` / `w:sdtEndPr` was invisible to BOTH gates

**`compiler.ts:421`** (`propertyBlockCarrier` skipped `#text`) **and
`renderer.ts:1090`** (`sdtBoundedClearPatches` skips those two children
outright).

### Input

```xml
<w:sdt>
  <w:sdtPr><w:id w:val="900"/><w:alias w:val="Anticoagulation"/><w:text/>WARFARIN 5 MG DAILY</w:sdtPr>
  <w:sdtContent><w:r><w:t>Enter anticoagulation</w:t></w:r></w:sdtContent>
</w:sdt>
```

### What happens

`refused=0 · fields=1 · proof=emptied/eligible · countsAsBlankProof=true ·
verified=true · WARFARIN 5 MG DAILY present in the output`. Identical result
for the same bytes written as `<![CDATA[…]]>`, as `<w:rPr>…</w:rPr>` inside
`sdtPr`, as `<w:delInstrText>`, and in `w:sdtEndPr`.

### What should happen

Refused. The **byte-identical string one element over** — inside
`w:sdtContent` — is a hard refusal, and has been since #172(3) and #173.

### Why harmful

This is the one hole **no addition to `CONTENT_CARRIERS` could ever have
closed**, because character data has no element name. And it is the arc's own
already-ruled harm arriving through the one door nobody guarded:

| guard | what it covers | why it missed this |
|---|---|---|
| `gapIsInvisible` (renderer.ts:833), #172(3) | sibling gaps, CDATA deliberately NOT stripped | runs only inside `w:sdtContent` |
| `subtreeHasNoCharacterData` (renderer.ts:862), #173 | any depth in a kept-whole container | runs only inside `w:sdtContent` |
| `propertyBlockCarrier` (compiler.ts:421), #174 | carrier ELEMENTS in any property block | skipped `#text` |

`sdtBoundedClearPatches` skips `w:sdtPr` and `w:sdtEndPr` before
`structureKeepDeletions` is ever called, so **neither renderer guard has ever
looked at them**, and admission had not either. Three guards, all correct, all
aimed one element to the right.

### Does the pre-declared remedy close it

**YES — the remedy's second arm, a stricter admission predicate**:
*character data in a property block is a refusal* (compiler.ts:413–440).
Whitespace-only text is explicitly not a refusal — pretty-printed XML puts a
newline between every pair of elements, and refusing that would refuse every
control in a formatted document. Same threshold `gapIsInvisible` already uses.

---

## A THIRD OBSERVATION — the gate's own watched set was two names short of its named set

**`__tests__/gate-175-derived-keep-list.test.ts`** — the `#175(1)` loop asserted
*"EVERY container the clear copies verbatim refuses a carrier inside it"* and
then `continue`d past **`sdtPr` and `sdtEndPr`**, because they cannot be placed
in the content. Those two are **exactly where finding 2 lives**.

Canon 28 in its purest form: the loop was correct about the containers it
watched, its failure message named a strictly larger set, and the gap was the
whole finding. They are now exercised at their **legal** position via
`admissionOf`'s third argument, instead of being excused.

---

## THE HARM PATH IS ALSO REACHABLE WITHOUT A WRITE — recorded, not a separate finding

A control whose content is **entirely skeleton** produces zero deletion patches,
and `renderer.ts:142` then emits a **`blank`** proof carrying the same
`blankEligible: 'eligible'`. Measured: `<w:sdtContent><w:p><w:r><w:rPr>
<w:dayLong/></w:rPr></w:r></w:p></w:sdtContent>` → `proof=blank/eligible ·
counted=1`, with the content surviving **byte-identically** (which is precisely
what a `blank` proof asserts).

Same carriers, same credit, no write at all. It is not a second defect — it is
the reason the fix had to be at **admission** rather than in the writer: the
writer never ran.

---

## CONTROLS — stated so no arm is read as more than it is

**Every batch carried both directions.**

| control | result |
|---|---|
| clean narrative control | admitted, `emptied/eligible`, counted, placeholder **gone from the output** — before and after |
| `w:sym` in `w:rPr` (known-bad) | refused, before and after |
| `w:r` in `w:sdtEndPr` (known-bad) | refused, before and after |
| bare text in `w:bookmarkStart` inside the content | renderer refuses the clear → `filled`, **counted=0** — the #173 guard is alive |
| repeating-row inner control, `w:sym` in its `pPr` | refused — admission does reach repeating prototypes |
| table-cell-level control, `w:sym` in its `pPr` | refused |
| whitespace-only text between `sdtPr` children | **admitted and counted** — the false-refusal direction |

### The false-refusal control, measured on real Word documents

Compiled **before and after**, byte-identical results on all nine:

| document | fields | unsupported |
|---|---|---|
| `WM IOV Template.docx` (the customer's, via `sample-form.docx`) | **80** | none |
| `sample-operative-note.docx` | 17 | none |
| `sample-note.docx` | 0 | none |
| six genuine `Microsoft Office Word` `reference.docx` files on this host | 0–2 each | unchanged |

**Zero false refusals. The 80-of-80 wall is intact.** No conformant document can
put an `EG_RunInnerContent` element or raw text inside a property block, which
is why the addition costs nothing real.

---

## MUTATION PROOFS — each arm reds against the defect it was written for

Backup taken **after** the change (canon 23); every mutation asserted its own
application before the run was believed (canon: *a mutation proof asserts its
own application*); restore verified in both directions.

| mutation | applied | result |
|---|---|---|
| M1 — remove the character-data refusal | ✓ | **1 failed** / 10 passed |
| M2 — remove ONE added carrier (`pgNum`) | ✓ | **2 failed** / 9 passed |
| M3 — remove ALL sixteen added carriers | ✓ | **2 failed** / 9 passed |
| M4 — stop scanning the control's own `sdtPr`/`sdtEndPr` | ✓ | **2 failed** / 9 passed |

M4 is what proves the third observation's fix: with the loop's old `continue`
in place, that mutation was invisible.

**Regression:** `src/lib/note-template-docx` + `src/lib/template-twin` —
**63 files, 752 passed, 2 todo, 0 failed.**

---

## WHAT I TRIED THAT WAS ALREADY CAUGHT — the negative half, so the pass is falsifiable

Caught by admission before the fix, and still caught after:
`w:smartTag`, `w:hyperlink`, `w:bdo`, `mc:AlternateContent` and `w:customXml`
inside a property block (each holds a `w:r`, and `propertyBlockCarrier` recurses
to unbounded depth); a nested `w:sdt`; `oMath`/`oMathPara`; a bare `w:tab`
character; `w:fldSimple` in a `w:bookmarkStart` (the #175 case). Caught by the
renderer: character data inside any kept-whole container in the CONTENT, in
either text or CDATA syntax. Namespace prefixes do not help an attacker —
`localName()` splits on `:` — and XML forbids entities in tag names.

Structural doors that turned out to be shut: a repeating-row prototype's inner
control, a table-cell-level control, and a header/footer control all reach
`processContentControl` and are admitted normally. A nested control fails
earlier, on overlapping approved bindings.

### ⚠️ NAMED RESIDUE — admitted, survives, counted, and I could NOT demonstrate a wrong output

Two shapes remain admitted and **are not fixed here**, deliberately:

- **bare VML** — `<v:shape id="…"><v:imagedata r:id="…"/></v:shape>` inside a
  `w:pPr`;
- **`w14:checkbox`** inside a `w:pPr`.

Both are admitted, survive verbatim, and the field counts. **What I cannot
demonstrate is that either PRINTS.** Neither is a `w:r` child, so unlike the
fourteen names above the schema does not say they render; VML reaches a Word
page only through `w:pict` or `w:object`, and **both of those are already
carriers**. Any claim that a PDF engine or Word draws them there is
**UNVERIFIED** — I did not render either to a page.

They are recorded rather than fixed because an invented finding is worse than
none, and because the obvious wider predicate — *refuse foreign namespaces in a
property block* — **would break real Word documents**: `#174`'s own measurement
is that Word wraps its checkbox in `mc:AlternateContent` **inside `w:sdtPr`**,
which is a property block. The element-name enumeration is the correct
instrument here, and these two sit outside what I can demonstrate.

**What would close them:** a measured render showing either mark on a page.
The remedy would then be the same first arm — `shape` and `checkbox` joining
`CONTENT_CARRIERS` — with no new machinery.

---

## HONEST LIMITS

1. **The fix is COMPILE-TIME ONLY.** IRs compiled before this commit were
   admitted under the old rules and keep their fields; the renderer has no guard
   for the outer `sdtPr`/`sdtEndPr` at all. This is the same accepted position
   `#175` already records for the `w:r`-in-a-property-block backstop. Closing it
   would require re-compiling stored templates — not done here, and not in the
   pre-declared fix class.
2. **No claim is made about what Word or a PDF engine draws.** Every result
   above is measured on the compiled IR, the emitted proofs, `countsAsBlankProof`
   and the rendered `word/document.xml` bytes. The clinical reading — that a
   date element prints a date — rests on the OOXML schema and on #174's own
   prior measurement of a `w:sym` in the identical position, **not on a render I
   performed**.
