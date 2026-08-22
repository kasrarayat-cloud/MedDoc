# F24-S3 — THE ADDRESSING SUBSTRATE, MEASURED BEFORE THE BUILD

**Run `20260822-164142-b1`, session 01. Read-only against production and QA; one
new test file, zero production files changed.**

F24-S3's acceptance is *"the census of editor-addressable regions reaches ZERO
gaps on the certified template, **proven by replay** — not by a source sweep."*
The parity recon of 2026-08-21 closed by naming exactly what was missing for
that (`f24-editor-parity-recon-20260821.md:135-137`):

> **No count here says how many of the 80 fields an edit could address today.**

This report does not produce that census either. It establishes the facts a
census has to be built ON, closes a coverage hole found while establishing them,
and reports a **live wrong-cell write** that the mandatory adversarial pass found
in the gate this session wrote.

⚠️ **READ FINDING A FIRST, AND READ IT AS A WITHDRAWAL.** This report's original
Finding A was wrong, confidently phrased, and one merge away from becoming the
next session's premise. It is kept in place — struck rather than deleted —
because the shape of the error is more useful than the fact would have been.

---

## ✅ FIRST, THE FIGURE THAT HELD — re-measured, not inherited

`RELAY.md`'s F24-S3 row says the laterality primitive *"knows a real side for 52
of 52 TABLE CELLS; the 28 `unknown` are content controls with nothing to
disambiguate."* That figure has been **corrected twice already**, so it was
re-run here rather than carried forward.

Measured on **production**, the single CERTIFIED compiled version:

| `rowLaterality` | binding | count |
|---|---|---|
| `left` | table-bound | **26** |
| `right` | table-bound | **26** |
| `unknown` | content control | **28** |
| | | **80** — reconciles |

**The row is CONFIRMED, exactly as written.** 52 of 52 table cells know a real
side. Shape was checked before the count (`jsonb_typeof`, then key presence),
per the standing measurement discipline.

---

## ❌ FINDING A — **WITHDRAWN. IT WAS WRONG, AND THE ADVERSARIAL PASS KILLED IT.**

**This section originally claimed: *"the IR holds no static text, only its hash;
the row label text is NOT recoverable from `compiledDocumentIr`"* — and used it
to scope `RELAY.md`'s "NO SCHEMA CHANGE. Everything is already in
`compiledDocumentIr`" as true only for designs that never need the label text.**

**That is false. `RELAY.md`'s sentence stands exactly as written.**

The IR carries the row-label text on the FIELD, not on the table cell:
`TemplateFieldSchema.originalLabel` (`ir.ts:105`), with
`labelSource ∈ {…, 'left_cell', 'table_header', …}` (`ir.ts:106-115`), set by
`compiler.ts:803-819` from the cell to the LEFT of each measurement cell.

**Measured on production's certified twin, over the 52 table-bound fields:**

| `labelSource` | count | example `originalLabel` |
|---|---|---|
| `left_cell` | **26** | `SSV at the SPJ` · `AAGSV at the Proximal Thigh` |
| `table_header` | 26 | `REFLUX TIME (ms)` |

⚠️ **`GSV at the SFJ` — the exact string this report used as its example of text
the twin "cannot tell you" — is a stored `originalLabel` value.**

And the capability is not merely representable, it is **already shipped**:
`bridge-fill.ts:186-193` and `:215-222` take `vein = diameterField.originalLabel`
and match it against the note's markdown row labels. That is the "twin LOCATES
the row from the doctor's phrase" route the withdrawn section priced as needing
a schema change. It needs none, and it exists.

### Why the enumeration missed it — the failure is a named one

The sweep covered `compiledDocumentIr.tables[*].cells[*]`, `.nodes[*]` and the
top-level keys, found `staticTextSha256` in each, and concluded the text was
absent. **It never opened `fields[*]`.** That is canon's *"the inventory was
taken at the layer I was thinking in, and the thing lived one layer down"* —
committed while reasoning about table CELLS, when the label lives on the FIELD.

**Everything the section said about `tables[*].cells[*]` remains true and is
simply not the question:** those cells do carry only `staticTextSha256`. A true
statement about the wrong container is exactly how this class survives review.

⚠️ **AND IT WOULD HAVE SHIPPED.** The claim was in a merged-ready PR body, a
recon report and a RELAY row, phrased confidently, with a table. Nothing in the
unit suite, the gate or CI could have contradicted it — it was a claim about
data, and the only thing that refutes a claim about data is looking at the data.
The mandatory adversarial pass is the only reason it did not become the next
session's premise.

---

## ⚠️ FINDING B — TWO IR SHAPES ARE IN THE WILD AT THE SAME `irSchemaVersion`

**This is a direct hazard to the acceptance, which is worded "proven by
replay".**

`ir.ts:72`:

```ts
rowLaterality: z.enum(['right', 'left', 'unknown']).default('unknown'),
```

An IR stored **without** the key therefore parses to `'unknown'` — silently, no
error. And `bridge-evidence.ts:236-238` consumes it fail-closed:

```ts
const verdict = rowLateralityVerdict(fact, input.rowLaterality);
if (verdict !== 'ok') return { ok: false, reason: verdict };
```

with `rowLateralityVerdict` returning `row_laterality_unknown` for **every sided
fact** against an `unknown` row (`bridge-evidence.ts:259-262`). So on such an IR,
no sided measurement can fill any row — correct behaviour on a document with no
leg signal, and a **wrong universe** for a replay meant to prove addressing.

**Measured across every compiled version on QA:**

| stored `rowLaterality` key | versions | `compilerVersion` | `irSchemaVersion` | compiled |
|---|---|---|---|---|
| absent | **21** | `template-docx-compiler/1.0.0` | `1` | 2026-07-25 only |
| present | **34** | `template-docx-compiler/1.0.0` | `1` | 2026-07-26 → 08-18 |

**Both shapes report the identical compiler version AND the identical IR schema
version.** The shape changed on 2026-07-26 and neither version field moved, so
**nothing in a row says which shape it is** — it can only be established by
inspecting the content.

⚠️ **I MADE THIS EXACT MISTAKE WHILE MEASURING IT.** My first QA query carried
`limit 1` in its CTE and I reported *"QA's 55 versions carry the key on 0 of
80"*. That was true of **one** row and false as a generalisation; the real
answer is 34 of 55. Caught by re-reading my own query before writing it down.
The count was never wrong — it was answering a narrower question than the
sentence I attached to it.

### `certificationStatus` does not separate them either — and that is the selector a builder reaches for first

| `certificationStatus` | carries `rowLaterality` | versions | sided cells |
|---|---|---|---|
| CERTIFIED | **yes** | **8** | **52** |
| CERTIFIED | **no** | **2** | **0** |
| NEEDS_CONFIRMATION | yes | 26 | 52 |
| NEEDS_CONFIRMATION | no | 19 | 0 |

**55 = 34 + 21 — reconciles with the count above.** So *"pick a CERTIFIED
compiled version on QA"* has a **2-in-10** chance of picking a fixture in which
no row knows its side.

**The good half makes the fix concrete:** the 8 usable ones match production's
partition EXACTLY — 52 sided (26 left / 26 right), 28 unknown content controls.
So a deterministic selector exists, and it is a CONTENT predicate:

    the compiled version whose IR has rowLaterality present
    AND whose sided-cell count is 52

with the 52 asserted as a non-vacuity floor, so a fixture that silently
collapsed to zero cannot satisfy the selector while checking nothing.

**What a census must therefore do:** pin its compiled version by that predicate
— never by `certificationStatus`, never by either version field. A replay that
picks one of the 21 measures a system in which laterality routing can never
succeed, and every arm would read as a finding about the editor.

---

## ⚠️ FINDING C — THE SHARED PREDICATE HAD ZERO DIRECT TESTS. NOW GATED.

`lib/table-header-shape.ts` is F24 Slice 1's "first kill in the five-matcher
drift" and is load-bearing for **both** the generator (`build-soap-prompt.ts:300`
— whether the skeleton needs a label cell) and the editor
(`note-table-edit.ts:323-324` — whether a short header is short at the FRONT).
Its own doc-comment states the invariant: *"They must answer identically or the
generator will emit a shape the editor misreads."*

**It had no test of its own.** Measured with a positive control, so the zero is
an absence rather than a broken matcher:

```
grep -rln isDataColumnHeader   -> 3 files, NONE a test
grep -rln rowLateralityVerdict -> 3 files, ONE a test   (control)
```

Same matcher, same form: it finds tests when they exist.

**Closed by `gate-f24-table-header-shape-contract.test.ts` — 38 arms**, which
pins the truth table (including **eight** inputs where the answer surprises),
asserts the generator→editor contract by running **both real functions**, pins
the addressability gap and the cross-time failure direction, and — after the
adversarial pass — **reproduces the wrong-cell write in Finding E rather than
asserting it away.**

⚠️ **AND THE MODULE'S OWN DOC-COMMENT UNDERCOUNTS ITS CLASS.** *"ONE PREDICATE,
TWO CALLERS"* is wrong: there are **three** sites deciding "does header cell 0
name a data column?", using **two** vocabularies. See Finding F.

### The eight divergences

Reproduced by running the predicate:

| header | returns | a reader would expect | direction |
|---|---|---|---|
| `Segment (right leg)` | `true` | label column | ⚠️ **wrong-cell write — Finding E** |
| `Vein Size` | `true` | label column | ⚠️ **wrong-cell write — Finding E** |
| `Site (see key)` | `true` | label column | ⚠️ **wrong-cell write — Finding E** |
| `CFV mm` | `false` | data column | fails closed (`column_not_found`) |
| `Thickness` | `false` | data column | fails closed |
| `Grade` | `false` | data column | fails closed |
| `**AREA (cm2)**` | `false` | data column | ⚠️ **DECORATION, not vocabulary** |
| `AREA (cm2).` | `false` | data column | ⚠️ **DECORATION, not vocabulary** |

⚠️ **THIS SECTION ORIGINALLY READ "…and why they are pinned rather than fixed",
AND ARGUED THE COST IS "NEVER A WRITE INTO THE WRONG CELL". THAT WAS FALSE** —
the first three rows are exactly the inputs that falsify it (Finding E). The
argument was: *one function answers for both callers, so a misclassification
makes them wrong in the same direction and the grid stays internally
consistent.* ⚠️ **The two callers act at DIFFERENT TIMES.** The generator wrote
the note's header under whatever the predicate said then; the editor asks about
it today. Internal consistency is a property of one generation, not of a note
already in the database — and the widen exists *only* for notes from the other
era.

**The last two rows are a class the first six do not cover:** they are not about
the words at all. `/\([^)]*\)\s*$/` is anchored, so any non-space character
after the parenthetical kills that arm. `AREA (cm2)` is a data column; **bold it
and it stops being one.** Reachable rather than hypothetical, and the proof is
in this repository: `note-table-edit.ts:79` strips `**` from header cells before
comparing, so the editor already expects bold headers in exactly the strings
this predicate cannot parse. A trailing SPACE is fine (`\s*$`); the class is
non-whitespace decoration.

### Mutation proof — three mutations, each asserting its own application

### Mutation proof — three mutations, each asserting its own application

| # | mutation | result |
|---|---|---|
| **A** | widen the SHARED vocabulary (`+thickness`) | truth-table arm **RED**; the addressability-gap arm **also RED — moving toward SUCCESS**, i.e. the gate registers the gap closing. Contract arms stay GREEN, correctly: one predicate keeps both callers in step even when its answer changes |
| **B** | editor stops sharing the predicate (caller drift) | legacy-widen arms **RED** — see below |
| **C** | **partial**: widen on DELTA alone (drop `headerLacksLabelColumn`) | cross-time arms **RED** — Slice 1's original clinical defect |

⚠️ **AND MUTATION C's FIRST FIXTURE COULD NOT DEMONSTRATE THE HARM, WHICH I
FOUND BY RE-READING IT AFTER THE PROOF HAD ALREADY GONE GREEN → RED.** Measured
under the delta-only mutation:

| fixture | asked for | row after | verdict |
|---|---|---|---|
| the original, `\| Segment \| DIAMETER \| REFLUX \|` over a 4-cell row | REFLUX | `\| GSV at the SFJ \| seg \| 6.2 \| 9.9 \|` | the **CORRECT** cell — refusing it is conservative, not protective |
| the reference shape, `\| VEIN \| DIAMETER (mm) \|` over `\| GSV \| 6.2 \| 3.4 \|` | **DIAMETER** | `\| GSV at the SFJ \| 6.2 \| 9.9 \|` | **diameter UNTOUCHED, 9.9 in the REFLUX position** |

The second is the defect quoted verbatim at `note-table-edit.ts:304-312`. Both
arms now ship. **A mutation aimed at the wrong FORM produces a red as empty as a
green that never ran** — canon's *"mutate toward the REAL shape"*, caught on its
own author.

---

## ⚠️ FINDING D — MY OWN GATE WAS BLIND, AND MUTATION B IS WHAT FOUND IT

**Recorded because it is the most useful thing in this report.**

Mutation B replaced the editor's `isDataColumnHeader(rawHeaderCells[0])` with a
predicate that never matches — the two callers drift, which is the exact defect
the module exists to close. **The contract matrix stayed 26 of 26 GREEN.**

The reason is not a weak assertion. It is a **wrong universe**, and it was
created by a fix working correctly: that matrix builds every note from the REAL
generator, and F24 Slice 1 made the generator emit a *matching* header
(`|  | DIAMETER (mm) | …`, with the empty label cell). A grid that already lines
up never needs widening, so `headerLacksLabelColumn` is **unreachable from any
freshly generated note**. The arm's result was predetermined by the generator's
fix rather than by the editor's health — the canon's *"a control aimed where the
answer is predetermined is not a control"*, arriving inside a contract test.

**The widen is LEGACY-ONLY code.** Its population is the 339 of 670 production
data rows Slice 1 measured — notes written BEFORE the generator fix. That shape
is the only input that exercises the editor's half of the shared predicate, so
it is the only input that can prove the two callers still agree. Added as
§3b; Mutation B then reddens exactly those arms.

⚠️ **AND THE GATE REDDENED AGAINST ITS AUTHOR TWICE MORE, ON FIRST EXECUTION:**

1. I asserted the header as `| DIAMETER (mm) | REFLUX TIME (ms) |` — the
   **PRE-Slice-1** shape — while reading the comment that explains the empty
   leading cell. The code was right and my expectation was stale.
2. I put `['Segment']`, a single-column table, in the contract matrix and it
   went red. That looked like a residual of Slice 1. **It is not: it is an input
   the system cannot produce** — `TableStructureSchema.columns` is `.min(2)`
   (`note-template-schema.ts:58`), so a one-column table is refused at parse
   time. Filing it would have been a fabricated finding about an unreachable
   shape. The exclusion is now asserted against the schema itself, so the day
   that floor is relaxed the exclusion stops being true loudly.

---

## ⚠️ FINDING E — A WRONG-CELL WRITE ON SHIPPED CODE. **LATENT, NOT LIVE.**

**Found by the mandatory adversarial pass over this session's own diff, and
verified here before being believed. No mutation is applied — this is `main`.**

A legacy note whose header NAMES its label column is supposed to be refused, and
with `VEIN` it is. But when the label column's text happens to satisfy
`isDataColumnHeader`, the widen fires, the header is padded at the FRONT, and
every column resolves one place to the right:

```
| Vein Size | DIAMETER (mm) |
| --- | --- |
| GSV at the SFJ | 6.2 | 3.4 |

edit DIAMETER (mm) := 7.7
  ->  ok: true,  column: "DIAMETER (mm)",  before: "3.4"
      | GSV at the SFJ | 6.2 | 7.7 |
```

**The diameter is UNTOUCHED. 7.7 landed in the REFLUX TIME cell, destroying a
measurement, and the doctor was told the diameter had changed.**

Reproduced identically for `Segment (right leg)` and `Site (see key)`. Control,
same fixture with `VEIN` or `Segment`: `ok: false, reason: 'ragged_table'` — so
this is a property of the PREDICATE, not of the fixture.

This is verbatim the defect `note-table-edit.ts:295-317` records the
`headerLacksLabelColumn` guard as having closed, **arriving through the guard's
own predicate.**

### The severity, measured rather than asserted

**LATENT.** On production, `note_templates.sections` holds **3 table structures,
and all 3 have `DIAMETER (mm)` as their first column** — which the predicate
classifies correctly. **No production template triggers this today.**

⚠️ **HONEST LIMIT:** that measures TEMPLATE structures, not the headers sitting
in notes already written. A note generated under a template whose columns have
since changed is outside it, and closing that gap would mean reading note
bodies.

**THE TRIGGER, written so it is a lookup and not a judgement:** a doctor's table
whose FIRST column is a row-label column whose text ends in a parenthetical or
contains one of `diameter|reflux|velocity|length|depth|time|size`.

**NOT FIXED HERE, and the reason is not timidity.** The failure is a FALSE
POSITIVE of a heuristic, and the geometry cannot discriminate: for
`| Vein Size | DIAMETER (mm) |` over a 3-cell row, "header lacks a label column"
and "header names its label column and is short a trailing data column" are both
consistent with the delta — which is precisely why the delta was never evidence.
Only the SEMANTICS of the header separate them. Tightening the predicate trades
false positives for refusals (the safe direction) but changes the GENERATOR too,
so it is a product decision about doctors' headers. **It is pinned as a defect
in the gate, with its trigger and its latency, so a fix is deliberate.**

---

## ⚠️ FINDING F — "ONE PREDICATE, TWO CALLERS" IS THREE SITES AND TWO VOCABULARIES

`table-header-shape.ts`'s doc-comment names two callers. There is a third:
`template-twin/bridge-fill.ts:147-152` (`classifyHeader`), consumed at `:425`:

```ts
const labelColumnOffset = roleByCol[0] === 'other' || roleByCol.length === 0 ? 0 : 1;
```

whose own comment describes the identical decision — *"if that column already
classifies as DATA, the header has no label column and every data cell sits one
to the right."* Its vocabulary is `/reflux/` and `/diameter|(^|\W)mm(\W|$)/`.

**Measured divergence, both directions:**

| header | `isDataColumnHeader` | `classifyHeader` | |
|---|---|---|---|
| `DIAMETER (mm)` · `REFLUX TIME (ms)` · `VEIN` | agree | agree | ✅ the real customer form |
| `CFV mm` | `false` (label) | `diameter` (data) | ⚠️ diverge |
| `VELOCITY (cm/s)` | `true` (data) | `other` (label) | ⚠️ diverge |
| `Vein Size` | `true` (data) | `other` (label) | ⚠️ diverge |

**They agree on every column of the real customer form, which is why nothing has
broken.** The generator and the editor can be in step while the TWIN FILL is
not.

⚠️ **NOTHING ASSERTS THIS, DELIBERATELY.** `classifyHeader` is not exported, and
re-implementing a shipped predicate inside a test is the F12-g failure — an SQL
re-implementation answered 19 where the shipped predicate answered 15, and the
19 reached a ledger row. Exporting a symbol for a test's convenience is a
production change. **This is a finding for F24-S3 to reconcile, with its own
adversarial pass.**

---

## WHAT THIS REPORT DOES NOT ESTABLISH

- **No census.** The addressable-region count does not exist yet, and this
  report deliberately does not estimate one. **Finding B is the reason a census
  written yesterday would have been wrong.**
- **Nothing was replayed against a real visit.** Every measurement is either a
  read-only database query over template STRUCTURE (no note bodies, no patient
  data) or an in-process call to a shipped function. A real doctor's visit is
  never a smoke target.
- **The gate does not reach the twin.** The editor has no twin awareness today —
  re-measured on this branch with controls rather than inherited: **0** twin refs
  in `chat-edit-visit.ts` / `note-table-edit.ts` / `intent.ts`, against controls
  of 50 / 42 / 14 on the same matcher. Inventing twin awareness in a test would
  be asserting the item's own unbuilt design.
- **Finding E is not fixed, and its latency is measured over TEMPLATES, not over
  written notes.** Both limits are stated in the finding itself.
- **Finding F is asserted by nothing.** It is prose and a measurement, because
  the symbol is unexported and re-implementing it would be the F12-g failure.
- ⚠️ **Finding A was WRONG and is withdrawn.** It did not merely fail to choose a
  design — it priced a route as needing a schema change when that route is
  already shipped. Anything downstream that read it should be re-derived.

---

## WHAT THE ADVERSARIAL PASS COST, AND WHY IT IS THE ARGUMENT FOR ITSELF

Six claims were put up to be broken. **Five were refuted**, and every refutation
was verified here before being accepted:

| claim | verdict |
|---|---|
| the IR cannot supply the row label | ❌ **REFUTED** — Finding A withdrawn |
| the divergences never cause a wrong-cell write | ❌ **REFUTED** — Finding E |
| one predicate, two callers | ❌ **REFUTED** — Finding F |
| six divergence classes | ❌ **REFUTED** — a seventh and eighth, decoration |
| §4's cross-time arm is protective | ❌ **REFUTED** — it was an artifact of one word |
| the widen is legacy-only | ✅ **NOT REFUTED** on the widen; the *wording* was |

**Every one of those five was in a PR that had passed CI, a11y-ci and
secrets-scan, carried a 29-arm gate, and had been mutation-proved three ways.**
The suite could not see them because they were claims about DATA and about the
CLASS, and a green suite is neither. The PR was converted to a DRAFT at the
moment of doubt, before any verification began.
