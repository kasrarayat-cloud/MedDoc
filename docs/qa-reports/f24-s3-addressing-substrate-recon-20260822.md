# F24-S3 — THE ADDRESSING SUBSTRATE, MEASURED BEFORE THE BUILD

**Run `20260822-164142-b1`, session 01. Read-only against production and QA; one
new test file, zero production files changed.**

F24-S3's acceptance is *"the census of editor-addressable regions reaches ZERO
gaps on the certified template, **proven by replay** — not by a source sweep."*
The parity recon of 2026-08-21 closed by naming exactly what was missing for
that (`f24-editor-parity-recon-20260821.md:135-137`):

> **No count here says how many of the 80 fields an edit could address today.**

This report does not produce that census either. It establishes the four facts a
census has to be built ON, two of which change the item's design, and it closes
a coverage hole found while establishing them.

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

## ⚠️ FINDING A — THE IR HOLDS NO STATIC TEXT, ONLY ITS HASH

**This scopes a load-bearing sentence in the item's own row.**

`RELAY.md` F24-S3 states: **"NO SCHEMA CHANGE. Everything is already in
`compiledDocumentIr`."**

Measured on production's certified IR:

- `compiledDocumentIr.tables[0].cells[*]` carries `staticTextSha256` — **a
  SHA-256, never the text.**
- `compiledDocumentIr.nodes[*]` likewise carries `staticTextSha256` (null on
  field nodes).
- The IR's top-level keys are `nodes · parts · stats · fields · source · tables
  · unsupported · compilerVersion · irSchemaVersion · structureSha256 ·
  staticContentSha256`. **No key anywhere holds static cell text.**

**The consequence is specific.** The editor's user-facing address is
(section, **ROW LABEL**, column) — `note-table-edit.ts:209` matches
`norm(c[0]) === norm(rowLabel)` against the note's markdown. The row label
("GSV at the SFJ") is a STATIC table cell. **The twin can tell you a field's
identity, its column, its row index and its leg; it cannot tell you what text is
in the label cell the doctor will name.**

So "everything is already in `compiledDocumentIr`" is true **for designs that
never need the label text**, and false for designs that do:

| design | needs label text? | schema change? |
|---|---|---|
| twin **VALIDATES** an address the note resolves (e.g. laterality via `rowLaterality`) | no | **none** — the row's claim holds |
| twin **LOCATES** the row from the doctor's phrase | yes | yes, or a source re-read |
| positional mapping note-row → `rendererBinding.rowIndex` | no | none, **but** it assumes note order tracks document order — the assumption class that produced both of Slice 1's clinical defects |

The bytes are not lost: `template_twin_source_artifacts` retains `objectKey` +
`sha256`, so label text is recoverable by fetching and re-parsing the source
DOCX — a storage read on the edit path, which is a cost F24-S3 should choose
deliberately rather than discover.

**Nothing here says which design is right.** It says the first row is the only
one the current schema supports for free, and that the item's "no schema change"
line should not be read as licensing the second.

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

**What a census must therefore do:** pin its compiled version **by content**
(assert the key is present, and assert the 26/26/28 partition) rather than by
`certificationStatus` or by either version field. A replay that picks a
2026-07-25 QA fixture measures a system in which laterality routing can never
succeed, and every arm would look like a finding about the editor.

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

**Closed by `gate-f24-table-header-shape-contract.test.ts` — 29 arms**, which
pins the truth table (including six inputs where the answer surprises), asserts
the generator→editor contract by running **both real functions**, and pins the
addressability gap and the cross-time failure direction.

### The six divergences, and why they are pinned rather than fixed

Reproduced by running the predicate:

| header | returns | a reader would expect |
|---|---|---|
| `Segment (right leg)` | `true` | label column |
| `Vein Size` | `true` | label column |
| `Site (see key)` | `true` | label column |
| `CFV mm` | `false` | data column |
| `Thickness` | `false` | data column |
| `Grade` | `false` | data column |

**The consequence is bounded, and that is the point of the shared predicate.**
Because ONE function answers for BOTH callers, a misclassification makes the
generator and the editor wrong in the SAME direction, so the grid stays
internally consistent. The cost is a coverage gap (a real data column that gets
no cell and refuses with `column_not_found`) or a redundant column — **never a
write into the wrong cell.** Widening the vocabulary is a product decision about
doctors' headers and belongs to F24-S3 with evidence, not to a tidy-up.

### Mutation proof — three mutations, each asserting its own application

| # | mutation | result |
|---|---|---|
| **A** | widen the SHARED vocabulary (`+thickness`) | truth-table arm **RED**; the addressability-gap arm **also RED — moving toward SUCCESS**, i.e. the gate registers the gap closing. Contract arms stay GREEN, correctly: one predicate keeps both callers in step even when its answer changes |
| **B** | editor stops sharing the predicate (caller drift) | legacy-widen arms **RED** — see below |
| **C** | **partial**: widen on DELTA alone (drop `headerLacksLabelColumn`) | cross-time arm **RED** — this is Slice 1's original clinical defect, a doctor's reflux time written into the diameter cell |

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

## WHAT THIS REPORT DOES NOT ESTABLISH

- **No census.** The addressable-region count does not exist yet, and this
  report deliberately does not estimate one. Findings A and B are the reasons a
  census written yesterday would have been wrong.
- **Nothing was replayed against a real visit.** Every measurement is either a
  read-only database query over template STRUCTURE (no note bodies, no patient
  data) or an in-process call to a shipped function. A real doctor's visit is
  never a smoke target.
- **The gate does not reach the twin.** The editor has no twin awareness today
  (parity recon: 0 twin refs in `chat-edit-visit.ts` / `note-table-edit.ts` /
  `intent.ts`), and inventing one in a test would be asserting the item's own
  unbuilt design.
- **Finding A does not choose a design.** It rules out one option's "free"
  status and prices the other two.
