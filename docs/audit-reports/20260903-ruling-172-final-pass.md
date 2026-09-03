# THE #172 PASS — the acceptance number measured none of the delta

**Three lenses, isolated worktrees content-verified before launch (canon 88).**
Every number below was re-measured by me or is reported with the lens's own
stated population and controls.

---

## ⚠️ 1 · THE CORRECTION THAT REFRAMES EVERY ACCEPTANCE I HAVE REPORTED THIS ARC

**`WM IOV 52/52` measures NONE of the #172 renderer delta.**

```
WM IOV proof tally, re-measured:
  filled | content_control | blankEligible=undefined | counts=false : 28
  blank  | table_cell      | blankEligible=eligible  | counts=true  : 52
```

All 52 counted proofs come from `table_cell`, which since #171 returns a
hardcoded `'eligible'` and **never calls** `blankEligibilityOf`,
`paragraphIsInert`, `tableStyleAllows` or `defaultParagraphNumbering`. The 28
`content_control` fields — the only ones this delta touches — are all `filled`
and count for nothing.

⚠️ **THE CLAIM IS TRUE AND IT WAS DOING MISLEADING WORK**, which is this
programme's own recorded phrase for exactly this shape. The only real-document
evidence for the delta is the owner's form (35/35, `content_control`) — and its
table-rule cost measured zero **because that form contains no `w:tbl` at all**,
an answer predictable from the fixture rather than earned from it.

---

## 2 · #172(2)'s ALLOW BRANCH IS DEAD ON THE REAL WORLD — CENSUS, N STATED

Lens B deduped every `.docx` on this machine by content sha256: **91 parseable
documents**, 43 with a named producer (Word 16 ×20, Word 14 ×12, Mac Word ×2,
pandoc ×2, LibreOffice ×1, 7 third-party templates).

| measurement | value |
|---|---|
| `w:tbl` elements | **95** in 49 documents |
| …naming no style (out of scope) | 39 |
| …**naming a style** | **56** |
| of those 56, verdict **ALLOW** | **0** |
| of those 56, verdict **REFUSE(basedOn)** | **56 — 100%** |
| `w:style[@w:type="table"]` definitions | **297** |
| …carrying `w:basedOn` | **255 (85.9%)** |
| …carrying `w:numPr` **anywhere** | **0** |

Arithmetic reconciles (56+39=95, 255+42=297). **`TableGrid` — what Word applies
to every table made via Insert → Table — carries `basedOn="TableNormal"` in
every document that defines it**, WM IOV included.

Driven against the customer's own `styles.xml`:

```
CONTROL not in any table       -> emptied, counts=1
CONTROL table naming NO style  -> emptied, counts=1
        table names TableGrid  -> filled,  counts=0   ← credit lost
        table names TableNormal-> emptied, counts=1
        table names an ABSENT style -> filled, counts=0
```

> **THE TRADE, STATED PLAINLY: the `basedOn` arm refuses a hazard with 0 of 297
> instances, at the price of refusing 56 of 56 real named tables.**

Today's cost is **zero** — 0 of 897 content controls in the corpus sit inside a
style-naming table. But a clinical form laid out as a table is the commonest
form idiom there is, and such a template would lose credit on every control in
it, silently, labelled `filled`. **That is the exact failure mode #172(1) exists
to prevent, reintroduced one layer over.** The second hop that would clear
`TableGrid → TableNormal` is forbidden by the no-walk doctrine, so this is a
product decision and not a bug to patch unilaterally.

---

## 3 · MY NOUN-NARROWING OPENED A FALSE GRANT — MUTATION-PROVED AS A REGRESSION

A **default table style** carrying `w:basedOn` to a numbered table style, in a
table that names **no** style, earns a verified `emptied` proof with credit.

| placement of the same numbering | verdict |
|---|---|
| directly on the default table style | refused ✅ |
| reached through a **named** `w:tblStyle` | refused ✅ |
| **reached through the DEFAULT table style** | **counted** ❌ |

Reverting exactly `isParagraphDefault &&` restores the refusal, so it is a
regression this commit introduced, not a pre-existing hole.

⚠️ **AND MY ARM FOR IT IS CANON 31's PREDETERMINED CONTROL.** It asserts
*"TABLE default + basedOn, **no numbering anywhere** → ELIGIBLE"*, and the
"no numbering anywhere" clause does all the work — the base style is
deliberately clean, so the result is predictable from the fixture alone. The
complementary row, where `basedOn` reaches a base that IS numbered, is absent.

**Population: 0 live instances** (2 of 91 documents have a default non-paragraph
style with `basedOn`, both pandoc, whose base is undefined; 0 of 297 table
styles carry `numPr`). It re-arms with one producer change.

---

## 4 · SIX FURTHER `content_control` ROUTES — AND THE FALLBACK CLOSES THREE

Lens A measured each against the rebuilt collapse by mutating the guard, not by
arguing.

| route | closed by the collapse? |
|---|---|
| **character data in a KEPT-WHOLE subtree** — CDATA inside `w:rPr`; #172(3)'s rule was applied to sibling GAPS only. Verified by me: `emptied` · eligible · counts, **and the drug string is in the output**; the identical bytes as a gap are refused | yes |
| a **default** table style's `basedOn` (§3 above) | yes |
| duplicate `w:tblPr` / `w:tblStyle` — `directXmlChild` takes the first; the exact class #172(4) ruled a refusal for on the paragraph axis | yes |
| **entity-encoded attributes** — verified by me: `w:default="&#49;"` and `w:type="&#112;aragraph"` both **count**, while `w:default="1"` is refused. `readXmlAttribute` returns a raw slice and nothing decodes references | **NO** |
| `w:sdtPr` / `w:sdtEndPr` are skipped, so the ratified "a property container must not hold a run" check never sees them | **NO** |
| `w:docDefaults/w:pPrDefault/w:pPr/w:pStyle` naming a numbered style — pre-existing, unchanged by this delta | **NO** |

⚠️ **AND A FINDING ABOUT THE FALLBACK ITSELF, MEASURED.** Applied as a
**replacement** for the eligibility predicate, the collapse makes a default
paragraph style carrying `w:numPr` — and one carrying `basedOn` to a numbered
style — count again. **That is ratified #171 R1 and R4 regressing.** It must be
ANDed with the existing inherited-verdict check, never substituted for it. Even
then it closes three of six, and its `w:tbl` arm makes every content control in
a table cell ineligible.

---

## 5 · THE MECHANISM I BUILT TO REPLACE REMEMBERING DOES NOT WORK

**The #172(5) lint reports 0 offenders. I measured 4 live ones in its own
scanned directories, and it catches none of them.**

```
gate files scanned: 55
MISSED  blank-proof.test.ts:94      MISSED  blank-proof.test.ts:127
MISSED  compiler.test.ts:66         MISSED  picks-bridge.test.ts:139
```

It scans line by line; every real offender is wrapped, which is house style for
any call long enough to matter. Of ten offender forms, it catches two.

⚠️ **AND ITS GREEN WAS BELIEVABLE BECAUSE ITS CONTROLS ARE CANON 31's
PREDETERMINED KIND.** They test the regex against a string literal in memory —
never against a file — so repointing the scan at filenames instead of contents
leaves **both controls passing and the gate a total no-op**. Its floor
(`scanned > 10`) sits far below the real 55, so deleting an entire watched
directory also passes.

**A control that cannot fail in the dimension the instrument fails in is not a
control for that dimension.** The fix is a control that plants a real offender
in a real scanned file and asserts the gate finds it.

**The canon-index arm has the sibling defect:** it greps the WHOLE of
`AGENTS.md`, so canon 61 — cited once in the live-rules section — stays green
with **both** its index rows deleted, while the arm's own message claims to be
checking the index.

---

## 6 · FOUR MORE UNMEASURED PROPERTIES IN THE NEW CODE

Each mutation reds **0 of 104**:

| property | the mutation nothing catches |
|---|---|
| the ancestor walk covers **nested** tables | stopping at the innermost table (the code is right; the arms are single-table) |
| the subtree walk has **no depth limit** | capping at depth 2 — both #172(4) fixtures are depth 2, and a depth-3 `w:drawing` survives into a credited region |
| `styleType` is **case-folded** | dropping `.toLowerCase()`; the arm titled *"an OMITTED or oddly-cased `w:type`"* is caught by R4, which is type-blind by design — **canon 62, fifth instance** |
| `byId` is not **last-wins** | a duplicate `styleId` makes the verdict depend on document order — the defect this same function's comment records as already fixed one layer over, reintroduced in the commit that quotes it |

---

## 7 · TWO FALSE REFUSALS WITH MEASURED COST

- **An empty or whitespace-only CDATA section is refused.** `<![CDATA[]]>`
  contributes zero characters and cannot mark a page. Deleting the stripper was
  wholesale where unwrapping (`'$1'`) would keep the documented refusal exactly.
  **Cost today: 0** — zero `<![CDATA[` occurrences across all 91 documents.
- **The subtree widening refuses inert paragraph-mark formatting** — `w:u`,
  `w:i`, `w:lang`, `w:noProof`, `w:rStyle`, none of which renders a glyph.
  Measured both directions: **976 → 975** eligible paragraphs corpus-wide (one
  loss), and **delta 0** across the 421 paragraphs that actually contain a
  control. `w:u` appears in 21 of 91 documents and is the natural shape of an
  underlined fill-in-the-blank.

---

## VERIFIED — no finding

- Both acceptance claims hold as stated: WM IOV **52** counted, `Normal` has no
  `basedOn`; the owner's form **35/35**, 0 `w:tbl`.
- **#172(1)'s premise is real**: pandoc's shipped `reference.docx` has a
  `w:default` table style with `basedOn` and **zero `numPr` anywhere**; under the
  previous code it was a document-wide refusal, and the narrowing fixes it.
- **"The list did not grow" is exactly true** — WM IOV's cell `w:pPr` subtrees
  contain exactly the 16 shipped names, confirmed by two independent routes.
- **The double-`w:pPr` refusal costs nothing**: 0 occurrences in 91 of 91
  documents, and `CT_P` permits one.
- **The nested-table ancestor walk is correct** — outer-styled/inner-clean,
  outer-clean/inner-styled, a `w:tblStyle` with no `w:val`, an empty `w:val`,
  and a misplaced `w:tblStyle` all behave correctly.
- All 16 allowlist members are individually load-bearing; the three rescoped
  `find()` sites are genuinely stronger; the `#172` arms are not vacuous under
  an emptied proof set (5 of 5 red).
