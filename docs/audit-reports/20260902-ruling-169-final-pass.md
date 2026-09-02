# THE FINAL DELTA PASS — ruling #169, and the escalation it fires

**Four lenses, isolated worktrees created and content-verified before launch
(canon 88). Three attacked one claim — *find any numbering the guard cannot
see*. One attacked whether the newly-armed fixes measure anything.**

Every finding below that carries a number was **re-measured by me**, with
controls, before being believed.

---

## THE VERDICT: THE PRE-DECLARED ESCALATION FIRES — AND FOR A LARGER REASON THAN A SEVENTH ROUTE

#169 said a seventh evasion changes the INSTRUMENT rather than the guard. The
pass found the seventh, eighth and ninth. But the finding that matters is not
another route:

> **THE GUARD WAS BUILT FOR A BINDING THAT SUPPLIES NONE OF THE BLANK CREDIT ON
> THE ONLY REAL-WORLD TEMPLATE THIS PROGRAMME HAS.**

Measured by me on `WM IOV Template.docx`, all-null render through the real
compiler and renderer:

```
bindings       content_control 28 | table_cell 52
proof kinds    filled 28          | blank 52
COUNTED blank  52  — all 52 from table_cell; content_control contributes ZERO
blankEligible=false entries: 0     ← the guard never refuses anything here
```

`table_cell` and `legacy_form_field` return `blankEligible: true` **hardcoded**
(`renderer.ts:671`, `:683`) and never consult the guard. `countsAsBlankProof`
then returns `true` for `kind === 'blank'` at `blank-proof-count.ts:154` —
**before** the binding allowlist at `:180` that would have excluded them.

⚠️ **TWO INDEPENDENT LENSES FOUND THIS SEPARATELY**, from opposite directions
(document-side and plumbing-side), having never seen each other's work. That is
convergence, not correlation.

**So #168(a) and #169 — the entire numbering arc — have been measuring nothing
on the real template.** Not detecting weakly: not running.

---

## THE SECOND STRUCTURAL FINDING: A SENTINEL THAT CONFLATES *NO* WITH *DON'T KNOW*

The same class was found at two different layers by two different lenses:

| layer | FILE:LINE | the conflation | resolves to |
|---|---|---|---|
| style resolution | `renderer.ts:964`, `:1044` | `defaultId = ''` — *no default style declared* **vs** *declaration not understood* | `clear` → GRANT |
| proof plumbing | `blank-proof-count.ts:131`, `renderer.ts:170` | `blankEligible` ABSENT — *guard approved* **vs** *guard never ran* | eligible → GRANT |

Both fail OPEN, in a guard whose entire premise is that inability-to-resolve
means INELIGIBLE, at the two hops with nothing behind them. `true` encoded as
absence is what makes the first finding invisible: a binding that never computes
the verdict is indistinguishable from one that computed it and said yes.

Measured against the real function — only the exact boolean `false` refuses:

```
blankEligible: undefined -> counts   "false" -> counts   null -> counts
               0 -> counts    "" -> counts    [] -> counts    {} -> counts
```

---

## THE FAIL-OPEN CLUSTER IN THE STYLE TABLE — verified by me, with controls

| input | real counter | should be |
|---|---|---|
| control: plain document | counts ✓ | counts |
| control: inline `w:numPr` | refused ✓ | refused |
| control: numbered `w:pStyle` | refused ✓ | refused |
| `w:default="1"` on a numbered default style | refused ✓ | refused |
| **`w:default="true"`** | **COUNTS** | refused |
| **`w:default="on"`** | **COUNTS** | refused |
| **`w:type` omitted / `"Paragraph"`** | **COUNTS** | refused |
| **`w:docDefaults/w:pPrDefault` numbering** | **COUNTS** | refused |

`w:default` is `ST_OnOff` (ECMA-376 §22.9.2.7) — `1|0|true|false|on|off`. The
guard compares the literal `"1"`. **This is not a missed route; it is the route
already ratified as harmful, re-opened by respelling one attribute.**

Also reported, not independently re-measured by me: table styles
(`w:tblStyle`/`w:tblStylePr`) are never consulted; duplicate style ids and
duplicate `w:default="1"` resolve LAST-WINS, so the verdict flips on document
order alone.

---

## THE THIRD FINDING: #164's ORIGINAL HARM IS ALIVE ON THE UNGUARDED BINDINGS

`tableCellPatches` keys emptiness on `w:t` presence only. So on `table_cell` and
`legacy_form_field`, a cell containing a Wingdings tick (`w:sym F0FE`), a
`w:drawing`, or a `w:pict` returns `blank` and **counts**.

That is the exact harm that falsified #164 — a control holding a Wingdings tick
proofed blank while still printing the tick — **still live, one binding
sideways**, on the path that supplies 100% of the real template's credit.

**Population today: zero.** I measured all 52 empty WM IOV cells for
`w:sym / w:drawing / w:pict / w:object / w:fldSimple / w:instrText /
w14:checkbox / w:sdt / m:oMath` — **all zero**, positive-controlled (the same
scan finds 28 `w:sdt` elsewhere in the document). **It re-arms the moment any of
those 52 cells gains a checkbox glyph, an image or a bullet.**

---

## ⚠️ AND THE ESCALATION'S OWN WORDING IS FALSIFIED BY MEASUREMENT — canon 66

#169 pre-declared the collapse as *"blank credit only from fields in paragraphs
with no `pStyle` and no `pPr` beyond the trivial."* **It does not define
trivial, and the whole template turns on that word.**

| | control paragraphs carry | under the strictest reading (no `pPr` at all) |
|---|---|---|
| **the owner's form** (`87223c49`, 35 fields) | **NO `w:pPr` whatsoever** — 0 `pStyle`, 0 `numPr` | **35 of 35 survive** |
| **WM IOV** (52 blank-bearing cells) | `w:pPr` on every one, 16 children: `widowControl`, `tabs`, `autoSpaceDE/DN`, `adjustRightInd`, `jc`, `rPr`+`rFonts`/`b`/`bCs`/`color`/`kern`/`sz`/`szCs`, `w14:ligatures` | **0 of 52 survive — the template stops certifying** |

Every one of those 16 is pure formatting. **None can put a mark on the page.**

⚠️ **THIS IS CANON 66 EXACTLY: an order's QUANTITIES are a snapshot, its
INSTRUCTIONS are the authority, and the failure mode is OBEDIENCE.** The
instruction's intent is unmistakable — *stop enumerating routes; require a shape
so simple nothing can hide in it.* Its literal wording assumed control
paragraphs are usually bare. That is true of the owner's form and false of every
Word document that has been formatted.

**The owner's form is untouched either way.** The entire cost of the strict
reading lands on the tracked fixture.

---

## HONEST LIMITS

- **Every claim about what WORD or the PDF ENGINE would render is UNVERIFIED.**
  No lens drove Word. The guard-level results are all demonstrated; the harm
  claims rest on `w:numPr` semantics as specified, not as observed.
- **`numberedStyleIds`' `readable: false` arm remains unreachable** — the
  package layer rejects a malformed `styles.xml` with `XML_INVALID` first. Two
  lenses confirmed this independently. It stays labelled defence-in-depth with
  no demonstrated caller, exactly as recorded when it was written.
- **Whether any production template other than WM IOV has a numbered empty table
  cell today is NOT MEASURED.** The lenses had no production DB access.
- My first two verification harnesses were **broken and caught by their own
  controls** — one used the wrong accessor, the other never applied its
  `styles.xml` at all. Both reported every case identically. The findings above
  are from the third harness, the one whose controls discriminate.

---

## WHAT THE GUARD DID HOLD AGAINST

On `content_control`, the battery that failed to break it is worth recording:
sdt inside `w:hyperlink`, `mc:AlternateContent/mc:Choice`, `w:ins`,
`w:customXml`, `w:smartTag`; a block-level sdt wrapping a numbered paragraph;
a control in `word/header1.xml`; and a whole document re-prefixed `x:` instead
of `w:` — **prefix-agnosticism verified rather than assumed.** Numbering present
only inside `w:pPrChange` is correctly read as historical and granted.

**The guard is good. It is installed on one of the three doors.**
