# `docs/foundation/rulings/` — the RULINGS index's archived bodies

**Every file here is a VERBATIM slice of `docs/foundation/RULINGS.md` as it
stood on 2026-08-26.** Nothing was rewritten, renumbered or reworded.

## Why the split happened, and what this file actually was

`RULINGS.md` calls itself *"every war-room decision, **one line each**"*. By
2026-08-26 that was literally true and it was the problem: **371,533 characters
in 254 lines** — 2.5× the 150,000-character read limit — because the *"Verdict,
in one line"* column had become the **full ruling body**. The largest single
table row was **10,330 characters**. There was never a separate index and a
separate body; the index row *was* the body.

`MASTER.md:79` orders every session to **read** this file. `MASTER.md:80` orders
it to **grep** it before any ruling-shaped decision. **The grep survived
truncation; the read did not** — and only the read was broken.

## ⚠️ A defect the split fixes by construction

**41 of the 119 ruling rows sat BELOW the heading `## What is NOT in here,
deliberately`** — including `#109(a)`, `#111`, `#115` and everything through
`#149`. That section's prose explains what does *not* belong in the file, and
then a third of the rulings followed it, because appends land at the end of a
file and that section had stopped being the end.

A session reading by heading would have concluded those rulings were excluded.
Nothing was wrong with any individual append; the structure simply outgrew its
own last section.

## Citations still resolve — this was checked, not assumed

**607 citations across 234 files** refer to rulings **by number only**
(`#137`, `ruling #150`). **Zero** use a path or a line anchor. So a split is safe
exactly as long as the number stays greppable — which it does, in both the live
index and the archived body.

That is why the live head keeps **one genuinely-one-line row per ruling**, using
**the ruling's own words**, never a paraphrase. It is the same shape as
`AGENTS.md`'s CANON INDEX, and the same rule applies:

> **AN INDEX ROW IS A POINTER, NEVER THE RULING.** If a row and an archived body
> disagree, **the body is right and the row is a defect** — fix the row.

## The numbering is intact, and was verified

65 rows carry explicit ids `#93`–`#150` — **no gaps, no duplicates** — and 54
legacy rows predate the numbering scheme and are addressed by their subject.
44 rows are marked **PROVISIONAL**, which `MASTER.md:718` depends on for the
morning report's batch-review list; that marker lives in the title column, which
is what made a clean split possible at all.

**The NUMBER-CLAIM PROTOCOL is unaffected and still governs**: a number is
claimed by **landing on `main`**, and anything unlanded refers to itself by
decision and branch, never by a bare number.

## The census that proves nothing was lost

Identical to the relay archive: `scripts/lib/split-ledger.py` refuses to write
unless the destinations form an **exact ordered partition** of the source, the
in-order reassembly is **byte-identical**, the heading census is **equal in both
directions**, every archive is **under budget**, and the line arithmetic
**reconciles**. See `docs/foundation/relay/README.md` for the full table and the
mutation proofs.

⚠️ This file has **no sub-headings inside its table**, so the splitter fell
through to **line mode** — packing whole rows, never splitting inside one. A row
is a ruling; a half-row is nothing.

## Adding a ruling

Exactly as before: **append a row to the live index in the same commit that
records the decision.** Rotation (`scripts/rotate-ledger.sh`) moves closed
bodies here when the head crosses its budget. Do not hand-edit anything in this
directory — corrections are **appended and dated in the live head**, and
superseded wording is kept.
