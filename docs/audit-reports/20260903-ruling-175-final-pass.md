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

---

# LENS B — THE REFUSAL REACHES THE DOCTOR, OR IT IS ONLY A COUNT

Three findings, all on the surface #175(2) exists to build. All fixed in this
commit; each carries its own arm and its own mutation proof.

## B1 — a refused control on the REAL customer template had no name

`compiler.ts` passed `identity.label` — `alias ?? tag` — on the refusal path,
while `chooseFieldLabel`, forty lines below **in the same function**, falls back
to the container's own text.

**Measured on the real form: 28 controls, ONE alias, ONE tag, TWENTY-SEVEN with
neither.** So every refused control on that document would have rendered as
*"Unnamed control"*, and #175(2)(b)'s entire product — a count becoming a list a
doctor can act on — survives exactly one layer down: three identical rows
carrying no more information than the number did.

Fixed by using the same derivation as the admitted path. Arm:
`gate-175-derived-keep-list.test.ts` — a control with no alias and no tag must
still be labelled from its container.

## B2 — a `checkbox` could buy blank credit, and all three guards passed by construction

The renderer writes TWO things for a null checkbox — `w:val="0"` and the `☐`
glyph — so a `blank` proof about one asserts something demonstrably false.

⚠️ **Every guard written to catch a forged `blank` passes for a checkbox BY
CONSTRUCTION**: `resolvedNull` is satisfied (it genuinely is null),
`blankEligible` is whatever the writer wrote, and the kind list did not name it.
Measured through the real `certifyAndActivateTemplateTwin`: **two token edits —
relabel to `blank`, add `blankEligible: 'eligible'` — took a template from
BLOCKED to CERTIFIED**, with no hash needed, because `blank` returns before the
expectation check.

`'checkbox'` joins `BLANK_INELIGIBLE_KINDS`. The arm drives `countsAsBlankProof`
under both the `blank` and `emptied` labels, with a `narrative_text` row for
non-vacuity.

## B3 — "Preparing your format…" was shown to templates the system had already given up on

Auto-certify is enqueued ONLY when `blockingUnsupportedCount === 0`; with any
blocking finding it logs SKIPPED and stops. The `preparing` derivation did not
consult that count — and `preparing` **replaces** the status pill.

So a template carrying refusals showed *"Preparing your format…"* for the full
window, **suppressing the one signal that leads to the findings list**. It is the
mirror of the defect the comment above it already named, and it is the worse
direction: it tells the doctor to WAIT when the correct instruction is to ACT.

The clause is fail-closed (`?? 1`): an unknown count must not read as "nothing is
blocking". Two arms, both mutation-proved — one that the count is consulted, one
that the default never becomes `0`.

---

# LENS C — THE ARMS AND THE INSTRUMENTS

Lens C audited the **committed** tree (`07af70c2`); several of its findings were
already closed by uncommitted work in this branch. ⚠️ **Every finding was
re-measured against the tree that actually ships before anything was changed** —
a finding verified on the wrong tree is canon 87 wearing a report's clothes.

| # | finding | against `07af70c2` | against THIS tree | action |
|---|---|---|---|---|
| 1 | `w:sdtEndPr` scanned by nothing | 0 red | **1 red** | already closed |
| 2 | the keep-list loop never checks WHICH container the refusal names | 0 red | **0 red** | FIXED |
| 3 | 23 of 27 carriers undetectable on deletion | 0 red | 33 of 43 covered | FIXED (the other 10) |
| 4 | the shared keep-list can lose two members silently | 0 red | **0 red** | FIXED |
| 5 | the structural arm is pinned to a name the drift never wore | 0 red | **0 red** | FIXED |
| 6 | the doctor-facing list can disagree with its own count | 0 red | **0 red** | FIXED |
| 7 | the REASON is unbound; only the LABEL is | 0 red | 1 red | closed; per-ROW arm added |
| 8 | the AST lint is file-wide and name-only | 5 FN + 2 FP | reproduced | FIXED |
| 9 | dead code in the keep-list loop | present | absent | already closed |
| 10 | a refuted figure survives in an arm's TITLE | present | present | CORRECTED |
| 11 | the canon arm reds on a reflow; blind in reverse | present | present | FIXED |

## C4 + C5 — the two arms watching the keep-list both missed its real failure

A **size floor of `>= 15` on a 17-member set licenses losing exactly two.**
Removing `permStart`/`permEnd` redded **0 of 756**, and the renderer then deletes
them from every cleared control — the silent capability loss v1 and v2 died of.

The structural arm forbids re-declaring `const STRUCTURE_KEEP_WHOLE` **by name**.
The historical drift was called `PROPERTY_BLOCKS`, so the regex is pinned to a
spelling the bug has never worn: import the shared symbol, ignore it, read a
local `KEEP_WHOLE_LOCAL`, and both regexes are satisfied.

> **Both are the same defect one level up: they assert things ABOUT the list
> instead of the property the list exists to buy.**

That property is a fact about the OUTPUT DOCUMENT, and it is cheap to state
directly — **clear a control holding each container, and the container is still
there afterwards.** A member lost by deletion, by a size the floor tolerates, or
by a local copy under any name now reds, because the renderer really does delete
it and the arm really does look. Non-vacuity: the doctor's stale text must be
gone from the same document, or every survival above is vacuous.

## C3 — a set cannot be its own witness

The carrier loop iterates `CONTENT_CARRIERS`, **so deleting a member deletes its
own test.** `RUN_INNER_CONTENT` — a list written from the OOXML schema — already
covered 33 of the 43 members. The other ten are the block and field constructs;
they now have their own list, for the same reason.

⚠️ **AND ONE ENTRY OF THAT LIST WAS REFUTED BY MEASUREMENT AND REMOVED** (canon
17, the refutation being the useful part). `w:tc` was on it on the reasoning that
a table cell carries content. It does — but ONLY through `w:p`, which is already
a member, so a `w:tc` holding a doctor's stale text refuses today with `tc`
absent from the set: **1 refusal, identical to the `w:tbl` control.** Asserting
it would have pinned a member the code does not need.

⚠️ **WHAT THE NEW LIST CLAIMS, EXACTLY** — it is a DELETION DETECTOR, not a proof
that each member is independently NECESSARY. Several are reachable only through
members that are already present, so a neighbour would refuse without them
(canon 62). That limit is written into the arm.

## C8 — the lint's zero was a fact about a VARIABLE'S NAME

The two-statement escape scanned the **whole source file** for any
`<bound>.length`, by identifier text, with no scope and no ordering. Eleven
probes through the real predicate measured it wrong in **both** directions —
five false negatives (a same-named variable in another function; `.length` as a
truthiness guard; as a for-loop bound; asserted after the take; a weak
`toBeGreaterThan(0)`) and two false positives (an unrelated same-named take
elsewhere; `.at(3)` counted as taking the first).

⚠️ **THE IN-SITU DEMONSTRATION IS THE ARGUMENT.** Planting a genuine offender in
a watched gate file left the gate **GREEN** — because `refused.length` appears
**twelve times elsewhere in that file** — and renaming the variable to `zzRows`,
the code otherwise identical, **redded it**.

> **The semantic question is abandoned rather than refined (canon 75).** Deciding
> whether a `.length` reference constitutes an ASSERTION is the judgement that
> was falsified five times; the next counterexample always exists.

The escape now requires the one spelling that cannot mean anything else —
`expect(<bound>.length` — in the SAME enclosing function, textually BEFORE the
take, and not under an "at least" matcher. A guard, a loop bound and a later
assertion are all correctly refused, because none of them is that.

**And the predicate now has probes of its own.** "Every gate file is clean" is a
fact about the CORPUS; it says nothing about whether the predicate works. All
twelve rows — including four controls, so a predicate that flagged nothing could
not pass — are folded into the gate permanently.

## C10 — a refuted figure, stated as fact, in a place a grep would find it

The arm was titled *"a w:tab inside w:tabs is a tab STOP, not a carrier — 52 real
fields depend on it"*. **That number was false in both halves**: the real
template carries 128 `w:tabs` blocks and **zero** inside a `w:sdt`, and the "52"
was a `table_cell` count lifted from the wrong row. The compiler comment was
corrected when that was measured; the refuted figure survived in a test NAME.

The exemption is kept on its own merits — a tab stop is paragraph geometry and
prints nothing — which needs no field count, so the number is **gone rather than
corrected to 0**. The superseded wording is kept as a dated note.

---

## MUTATION MATRIX — re-run in full, because arms were rewritten

⚠️ **Canon 98: a green matrix is a TIMESTAMP, not a property.** It measures the
pair (code, arms); this commit changed both halves, so the earlier matrix was
retired and re-run from scratch.

| mutation | arms red |
|---|---|
| keep-list drops `sdtEndPr` | 1 |
| keep-list drops `permStart` + `permEnd` | 1 |
| carriers drop `txbxContent` | 1 |
| carriers drop `delText` | 2 |
| the refusal misnames the container | 1 |
| the refusal loses its teeth (`blocksCertification: false`) | 1 |
| the refusal label falls back to alias/tag only | 1 |
| a `checkbox` may buy blank credit | 1 |
| the component lists the unfiltered set | 1 |
| the component hard-codes one reason for every row | 1 |
| `preparing` ignores the blocking count | 2 |
| `preparing`'s unknown-count default fails OPEN (`?? 0`) | 1 |
| the renderer reads a local keep-list under another name | 117 |
| a canon index row points at a file that does not exist | 1 |
| a canon index row is REFLOWED (must NOT red) | 0 ✅ |

**12 of 12 named arms red; both directions of the canon arm behave.**

⚠️ **TWO MUTATIONS IN THE FIRST RUN DID NOT APPLY, AND BOTH GREENS WERE
DISCARDED, NOT READ.** The anchors missed; the script asserted its own
application and said so, and the runs that followed were re-done with correct
anchors rather than believed. This is the trap the canon names — an assertion
error and a green scrolling past in the same output.

⚠️ **AND THE MATRIX HARNESS DAMAGED THE TREE, WHICH IS WORTH RECORDING.** It
mapped backup files to paths by BASENAME with an `endsWith('.tsx')` branch, so
`settings/page.tsx` was restored to `settings/note-format/page.tsx` — clobbering
a tracked file with another file's contents and leaving the real one unrestored.
Caught because a `grep` for a clause I had just written returned **0**. Both
files were repaired (the clobbered one proven byte-identical to the clobber
source first, so nothing of mine was in it), and the tree was then re-verified
by CONTENT, fix by fix, before any number below was believed.

> **An ambiguous predicate is how a restore becomes a write.** The keep-file map
> should have been explicit paths; a basename is not an identity.

---

## ACCEPTANCE — the two real customer forms, as numbers

Compiled with this commit's compiler. The owner's form was fetched read-only
from object storage and **verified against the `sourceSha256` recorded on its
row** before being used.

| form | fields | controls | admission refused | blocking total |
|---|---|---|---|---|
| **Gastroenterology Consultation** (owner's live template) | 35 | 35 | **0** | **0** |
| **WM IOV Template** (the customer's blank form) | 80 | 28 | **0** | **0** |

The owner's 35 reconciles with the field count on its compiled row, read by a
separate route (canon 18).

> **Neither real form loses a single control to the new fail-closed admission
> rules.** That is the number that matters: #174 refused *56 of 56* real named
> tables on its first attempt, and an admission rule that refuses real documents
> is not fail-closed, it is broken.

**Suite: 5663 passed, 4 skipped, 2 todo, across 401 files. `tsc --noEmit` clean.**

---

## WHAT THIS COMMIT DOES NOT CLOSE

1. **The compile-time-only limit stands**, exactly as recorded above for lens A.
2. **`w:tc` is deliberately NOT in the carrier set** — refuted by measurement,
   recorded rather than dropped silently.
3. **A total refusal still renders as "no fillable fields"** rather than as a
   list — the opposite instruction to the doctor. Source quarantined; filed as a
   backlog item, not fixed here, because it is not a shape leaving the admitted
   set and #175(4) permits no further pass.
4. **The new structural-carrier list asserts PRESENCE, not NECESSITY.** Said in
   the arm and repeated here so the gate is not read wider than it is.
