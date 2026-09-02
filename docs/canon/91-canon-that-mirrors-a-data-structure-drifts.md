# A CANON ENTRY THAT MIRRORS A DATA STRUCTURE IS A SECOND COPY, AND IT DRIFTS

**Recorded 2026-09-02, after one list went stale three times in a single day.**

## The specimen

A canon entry documenting a renderer's keep-list wrote the membership out:

> *"the keep-list is thirteen STRUCTURAL kinds — `p tbl tr tc sdt sdtContent`
> recursed, `pPr tblPr … commentRange*` kept whole — and **`w:rPr` is not among
> them**"*

Across three owner rulings on one day the real lists went **13 → 16/14 →
17/15**, and `w:rPr` was added back. Each time, the entry was correct when
written and false within a commit. At one point a **governing canon body stated
in bold the opposite of the shipped code**, while an amendment lower in the same
file discussed the change without retracting the claim — so a reader landing on
the earlier line got the wrong answer with no signal.

## Why it is a class and not a lapse

The lists were not *described* in the entry, they were **transcribed**. A
transcription has no mechanism keeping it true: nothing fails, nothing reds, and
prose does not participate in a refactor.

> **The moment a document repeats a value the code owns, there are two copies
> and only one of them is executable.**

This is the sibling of *an exemption's reason is prose, and prose decays
silently* — but worse, because a list LOOKS authoritative. A reader who finds
thirteen named elements does not go and count them.

## What belongs where

| in canon | in code |
|---|---|
| the ARGUMENT — why a keep-list rather than a delete-list; which direction an incomplete list fails in | the MEMBERSHIP |
| the measured EVIDENCE that made the argument — the specimens, their numbers | the current values |
| a POINTER, by symbol name, to where the membership lives | — |

The corrected entries say: *read `STRUCTURE_KEEP_WHOLE` and `STRUCTURE_RECURSE`
in `renderer.ts`.* That sentence cannot go stale, because it names a symbol
rather than its contents.

## ⚠️ THE COUNT IS THE WORST PART OF ALL

"thirteen" is the single most brittle thing such an entry can contain: it is
falsified by ANY change to the list, including one that does not affect the
argument at all, and it invites a reader to treat the enumeration as complete.
**If a number is not load-bearing for the argument, leave it out.** Where it IS
load-bearing — *"28 of 28 controls"*, *"1 of 28 prints"* — it is a MEASUREMENT
with a date, which is a different thing from a mirrored constant.
