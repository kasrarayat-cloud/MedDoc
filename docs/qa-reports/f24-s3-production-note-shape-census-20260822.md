# F24-S3 — WHICH NOTE SHAPE PRODUCTION ACTUALLY HOLDS

**Measured 2026-08-22, FOUNDATION run `20260822-164142-b1` session 03.
READ-ONLY against production `transcribe_visits`. No note body left this
query — every projection is a COUNT, a header's first CELL (a template column
name), or a line CLASSIFICATION.**

RELAY's F24-S3 row named this as *"the single most important open question"* and
*"the next measurement, and it decides which route is worth building."* This is
that measurement.

---

## THE ANSWER, FIRST

> **`captionFor` can return a caption for 9 of 45 production table headers.
> Sixteen more carry prose ONE BLANK LINE above the header, where the shipped
> reader — deliberately — does not look. Meanwhile row ambiguity is the COMMON
> case: 140 of 301 (visit, section, row-label) groups repeat.**
>
> **So the caption route is not worth building on.** Addressing needs a route
> that does not go through `captionFor`, which is what the twin's `rowIndex`
> gives it.

This corroborates session 02's replay finding — *"a single blank line takes the
twin from 40 to 0"* — from a completely independent direction. That one was a
replay over a synthetic matrix; this is a structural census of the real corpus.
Two methods, one conclusion.

---

## 1 · THE UNIVERSE

| quantity | value |
|---|---|
| visits with a non-null `soapFinal` | 50 |
| table headers (a `\|` line whose next line is a rule row) | **45** |
| visits carrying at least one header | **24** |
| rule rows | 45 |
| data rows | **441** |
| all `\|` lines | **531** |

⚠️ **IT RECONCILES: 441 + 45 + 45 = 531.** Every pipe line is a header, a rule
or a data row, and nothing falls outside the partition. **0 data rows have an
empty first cell**, so no filter of mine silently removed anything.

---

## 2 · WHAT SITS ABOVE EACH HEADER — the shape question

`captionFor` (`note-table-edit.ts:162-168`) reads the **adjacent line only** and
returns `null` for a blank, a heading, or another table row.

| line directly above | line two above | headers | visits | `captionFor` |
|---|---|---|---|---|
| **prose** | BLANK | **9** | 5 | **returns the line** |
| heading | BLANK | 16 | 9 | `null` |
| **BLANK** | **prose** | **16** | 8 | `null` ⚠️ |
| BLANK | heading | 2 | 2 | `null` |
| BLANK | table-row | 2 | 2 | `null` |
| | | **45** | | |

> **9 of 45 reachable. 16 of 45 carry prose that a single blank line hides.**

### ⚠️ THE CONTROL ON MY OWN CLASSIFIER, BECAUSE IT IS A RE-IMPLEMENTATION

Classifying "heading" in SQL means re-implementing `HEADING_RE`, and this
programme's own F12-g filing records what re-implementing a shipped matcher
costs. My SQL used `^\s*#`; the shipped `HEADING_RE` is `^\s*#{1,6}\s`. Measured
rather than assumed:

| matcher | headers whose line above matches |
|---|---|
| my loose `^\s*#` | 16 |
| shipped `^\s*#{1,6}\s` | 16 |
| **DIVERGENT** | **0** |

The divergence is empty **on this population**. That is a measurement, not a
guarantee — a note using `#heading` with no space would separate them.

### ⚠️ AND THE LIMIT THAT MATTERS: PROSE IS NOT A CAPTION

**I counted `prose`. A caption is a KIND, and prose is a QUANTITY.** This is
exactly the axis error the canon's "double tap" entry names, so it is stated
rather than glossed: `captionFor`'s own doc-comment says it *"NEVER
distinguished a caption from arbitrary prose — it returns whatever line sits
above."*

So the honest claim is the one about the shipped function: **`captionFor`
returns non-null for 9 of 45 headers and `null` for 36.** Whether those 9 lines
are captions, and whether the 16 hidden ones are, is NOT established here and
would need a read of note bodies.

That limit does not weaken the conclusion. It **strengthens** it: 9 is the
CEILING on what the caption route can reach, and the real number can only be
lower.

---

## 3 · HOW OFTEN IS A ROW ACTUALLY AMBIGUOUS — the price

The caption route only ever matters where a row label appears more than once in
one section. If that never happened, none of this would be worth building.

| quantity | value |
|---|---|
| sections holding 2+ table headers | **14** |
| distinct (visit, section, row-label) groups | 301 |
| **groups that REPEAT — the ambiguous set** | **140** |
| data rows | 441 |

**140 of 301 groups repeat — 46%.** Those groups account for **280 of the 441
data rows (63.5%)**: on the majority of production table rows, a row label alone
does not identify a cell.

⚠️ **280 IS MEASURED, NOT DERIVED.** I first reached it by arithmetic
(`441 − (301 − 140)`) and then re-ran it as its own query — `count(*) FILTER
(WHERE grp > 1)` over a window partitioned by `(visit, section, row_label)` —
because a number produced by subtraction and a number produced by counting are
different claims. They agree: **280 ambiguous / 161 uniquely labelled / 441
total.**

> **Ambiguity is the common case, and the disambiguator reaches 9 of 45
> headers.** That is the gap F24-S3 exists to close, now with a number on it.

---

## 4 · THE HEADER FIRST-CELL CENSUS — and it decides ruling #140's cost

| first cell | header lines | visits | header cells | pre-#140 predicate | #140 classifier |
|---|---|---|---|---|---|
| `DIAMETER (mm)` | 27 | 14 | 2 | true | **data** |
| `Location` | 8 | 4 | 3 | false | **label** |
| `Segment` | 6 | 3 | 3 | false | **label** |
| `Site` | 2 | 1 | 3 | false | **label** |
| `DIAMETER` | 1 | 1 | 2 | true | **data** |
| `Medication` | 1 | 1 | 3 | false | **label** |

> ⚠️ **NOT ONE PRODUCTION HEADER LANDS IN `cannot_tell`.** Ruling #140 is a
> tightening with **zero capability loss on the real corpus**, not a trade.

**And this could have come out otherwise** — a `Vein Size`-shaped value would
have appeared here as a newly-refused header. It is pinned as an arm in
`gate-f24-s3-label-column-from-evidence.test.ts` so it stays checkable.

⚠️ Ruling #140 had already measured *"45 header lines across 24 visits, six
distinct first-cell values"*. **Re-measured here rather than inherited**, per
canon's rule against carrying another report's count forward. It agrees exactly.

### 4b · WHICH HEADERS ACTUALLY REACH THE WIDEN — and it is a closed set of three

The label-column question only arises for a header that is short by exactly one
cell. Measured by comparing each header's cell count against its first data
row's:

| full header line | lines | visits | reaches the widen |
|---|---|---|---|
| `\| DIAMETER (mm) \| REFLUX TIME (ms) \|` | 13 | 7 | **yes** |
| `\| DIAMETER (mm) \| REFLUX TIME (seconds) \|` | 13 | 7 | **yes** |
| `\| DIAMETER \| REFLUX TIME \|` | 1 | 1 | **yes** |
| `Location` · `Segment` · `Site` · `Medication` · one `DIAMETER (mm)` | 18 | — | no — already aligned |

> **27 of 45 headers widen, and they are THREE distinct header lines.** The
> other 18 never reach the label-column question at all.

⚠️ **AND EVERY CELL OF ALL THREE IS AN UNAMBIGUOUS DATA COLUMN** — `mm`, `ms`,
`seconds` are units, and `DIAMETER` / `REFLUX TIME` are made entirely of
measurement nouns. That is what let the adversarial pass's D3 be closed by
requiring **every** header cell to classify as `data` rather than only the
first, at **zero** capability cost on this corpus. The rule was chosen because
this table said it was free — not assumed to be.

---

## 5 · ⚠️ AN UNRECONCILED DISCREPANCY, REPORTED RATHER THAN RESOLVED

F24 Slice 1 recorded a production census of **670 data rows** under detected
headers (`+1 -> 339`, `0 -> 331`), and `build-soap-prompt.ts` quotes it in a
comment. **I measure 441 today, and I cannot reproduce 670.**

Candidates tested and REJECTED:

| theory | result |
|---|---|
| my filter dropped empty-first-cell rows | **0 such rows exist** — the filter removed nothing |
| it counted `soapDraft` as well | `soapDraft` has 496 pipe lines / 45 rules → ~406 data rows; 441 + 406 = **847**, not 670 |

So the gap is **not explained**. Possibilities not tested: a different
population on 2026-08-21, a different row-detection predicate, or a count taken
across an environment other than production.

**I am not asserting Slice 1 was wrong.** I am recording that a load-bearing
census number quoted in a source comment could not be reproduced by a later
session using a predicate that reconciles exactly against its own universe.
Anyone relying on 670 should re-measure first.

---

## 6 · WHAT THIS DOES NOT ESTABLISH

- **Whether the 9 reachable lines are captions.** §2's limit.
- **Whether the 16 hidden lines are captions.** Same.
- **Which template each visit is bound to.** The census is over note TEXT, so a
  header is classified by its own shape, not by the template that produced it.
- **Anything about QA or about notes not yet written.** Production `soapFinal`
  only, at one instant.

## THE COMMANDS

Every figure above came from `docker exec -i meddoc-pro-postgres-1 psql -U meddoc
-d meddoc`, read-only, splitting `soapFinal` with
`regexp_split_to_table(body, E'\n') WITH ORDINALITY` and joining a line to its
successor to detect `header + rule`. No `UPDATE`, no `INSERT`, no `DELETE`, and
no note body in any projection.
