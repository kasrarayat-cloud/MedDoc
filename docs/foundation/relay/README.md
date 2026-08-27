# `docs/foundation/relay/` — the RELAY ledger's archived arcs

**Every file here is a VERBATIM slice of `docs/foundation/RELAY.md` as it stood
on 2026-08-26.** Nothing was rewritten, reworded, summarised or reordered.

## Why the split happened

On 2026-08-26 `RELAY.md` was **1,793,436 characters against a 150,000-character
tool read limit** — **twelve times over** — on a file `MASTER.md` STEP 0 orders
every session to READ. Only about **8%** of it fitted in one read.

⚠️ **And the ledger's truncation was the worse kind.** A rulebook truncated at
the top still returns *some* live rules. `RELAY.md` is **append-only**, so the
front of the file is its **oldest** content: a plain read returned the stale
beginning, omitted every current arc, and **announced nothing**. A confident,
well-formed, obsolete answer.

The head-of-file queue table — the thing `MASTER.md:480` calls *"the
authorization"* — survived inside that readable 8% only because a queue happens
to read well at the top of a file, not because anyone arranged for truncation to
spare it. And by 2026-08-26 every row in it was closed.

## What is in the live head, and what is here

| where | what |
|---|---|
| **`docs/foundation/RELAY.md`** | the LIVE head: the current queue, open items, `## Rules`, `## Invariants re-checked every item`, the reconciliation of reused item ids, and the index pointing here |
| **here** | every closed arc, verbatim, one file per dated span |

**The index in the live head points by TITLE, never by line number.** That is
not a style preference — it is measured. `RELAY.md:31563` cited a section at
line 27621; the citation was correct against the *parent* commit and wrong by 16
lines against the commit that wrote it, because that same commit added 16 lines
above it. **A line number in an append-only file is stale before it lands.**

## The census that proves nothing was lost

The split was performed by `scripts/lib/split-ledger.py`, which **refuses to
write anything** unless five proofs pass:

| | |
|---|---|
| **P1** | the destinations form an **exact ordered partition** of the source line range — no gaps, no overlaps, covering every line |
| **P2** | reassembling that partition **in order equals the source byte-for-byte** |
| **P3** | the heading census is equal **in both directions** — nothing lost, nothing invented |
| **P4** | every archive is itself **under the budget** — otherwise the split solved nothing |
| **P5** | the line arithmetic **reconciles** |

Byte-identity is a *consequence* of P1 rather than a separate hope. Each proof
was mutation-proved: break the splitter one specific way and the specific proof
that exists to catch it must fire. CI holds all of it in
`gate-ledger-rotation.test.ts`.

## This does not happen again by hand

A one-time split is a **treadmill**. Measured on the day: a head keeping only
*"2026-08-25 onward"* was already **155,689 characters** — **the ledger adds more
than the entire read budget per day.** The second lap would have arrived inside a
week.

So rotation ships with the split. `scripts/rotate-ledger.sh` is **banner-
triggered** — it asks `scripts/check-read-budget.sh` (F32) whether a file is over
and never re-implements that budget — picks the **oldest** cutoff that still
fits, so no more context is archived than necessary, and runs this same proven
splitter with all five proofs mandatory. It **never merges and never deploys**:
it produces a working-tree change to be landed as a normal item, with a PR, a
citation and a ledger row. Rotation is not a privileged operation.

## Adding to this directory

You do not, by hand. Run `bash scripts/rotate-ledger.sh --apply` and land what it
produces. If you are tempted to hand-edit a file here, the thing you actually
want is an **appended, dated correction in the live head** — archived bodies are
never rewritten, because in this programme the correction is the point.
