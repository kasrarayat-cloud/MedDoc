> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **122 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A BLOCKING ROW NAMES THE ARTIFACT THAT WOULD DISCHARGE IT — AND THE POINTER RUNS IN THE READER'S DIRECTION

**Standing 2026-08-25.** Canon already says an exemption is written with the
condition that retires it, so that checking is a **lookup rather than a
judgement**. That rule governs how the condition is WRITTEN. This is the failure
one step later: **the condition was met, the artifact that met it exists, and
the row went on reading as blocked for nine days.**

> **A LINK IN THE WRONG DIRECTION IS NOT A LINK. The reader travels from the
> QUEUE to the world; a pointer from the world back to the queue is invisible to
> them, because nothing tells them to go and look.**

⚠️ **REFERENCE CASE — F8, and it was sitting under the ledger's own "F8 OPENS."**

`RELAY.md`'s F8 row read *"build waits on the owner's Figma"* and *"The tab
builds **ONLY** on the Figma delivery"*. Measured:

| when | what |
|---|---|
| `2026-08-16T07:05:34Z` | the row lands — commit title *"recon measured **before any design**"*, **true at that moment** |
| `2026-08-16T07:40:22Z` | `f8-icd-tab-design.md` lands: *"This document is the build's contract."* |

**Thirty-five minutes.** Then nine days in which every reader inherited a
satisfied condition as an open one.

⚠️ **AND THE LINK EXISTED — POINTING UPSTREAM, WHICH IS THE PART THAT
GENERALISES:**

    f8-icd-tab-design.md:201  ->  "F8's row in docs/foundation/RELAY.md"     1
    RELAY.md                  ->  f8-icd-tab-design.md                       0

**The artifact knew about the row. The row did not know about the artifact.**
The doc's author did the courteous thing and cited the row; nobody reads the doc
to find out whether the queue is unblocked, because the row gives them no reason
to open it.

**THE PRACTICE, and it is one grep:**

1. **A row that states a blocking condition NAMES THE ARTIFACT CLASS that would
   discharge it** — a path, a filename pattern, a flag, a migration id. *"Waits
   on the owner's Figma"* names a **medium**, not an artifact, and a medium
   cannot be looked up. (The delivery here was markdown, not a Figma frame —
   so even a diligent reader searching for `figma.com` would have found
   **0**, correctly, and concluded the opposite of the truth.)
2. **When you land the discharging artifact, EDIT THE ROW IN THE SAME COMMIT.**
   Citing the row from the artifact is not the same act and does not substitute.
   This is *"a ratified change of scope lands before the build finishes"* pointed
   at a queue row: `RELAY.md` is the builder's input.
3. **The check is `grep -c <artifact> <ledger>` → a zero is the finding.**

⚠️ **IT IS THE `DEPLOYMENT_RUNBOOK §5.6` SHAPE AIMED AT THE QUEUE.** §5.6 was
false for two months and cost six hours. This was false for nine days and its
cost would have been **the queue head parked on a discharged gate** — a session
reading *"F8 OPENS."*, then the row, and correctly standing down.

**SIBLING MECHANISM:** F30's `check-retirement-conditions.sh` does exactly this
for `INBOX.md` entries — registry, set-equality, report-only. **This entry is the
same problem for `RELAY.md` queue rows and is NOT yet mechanized.** Filed as
such: a row's blocking condition is prose, and prose decays silently.

