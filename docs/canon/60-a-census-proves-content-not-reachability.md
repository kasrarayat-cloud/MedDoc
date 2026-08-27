# A CENSUS PROVES CONTENT, NOT REACHABILITY

**Ratified 2026-08-27, and it is the general rule behind a specific night.**

> **A content-preservation census answers "was anything LOST?". It cannot
> answer "can anything still be FOUND?" Those are different questions, and only
> the first one is ever asked.**

**EVERY LEDGER SPLIT SHIPS WITH ITS READER SWEEP, IN THE SAME PR.** Every
mandated route the split breaks is updated in that same PR. The template is:

> **WATCHED SET = HEAD + ARCHIVES.**

⚠️ **REFERENCE CASE.** The 2026-08-26 split of `RELAY.md` (1,830,324 → 20,339
chars) and `RULINGS.md` (375,008 → 44,935) was proved content-preserving: **0
lines lost in both directions, 33,386 == 33,386.** That proof was TRUE, and was
independently re-derived by a second route — 23 of 25 archives byte-verbatim,
spans contiguous, the 2 exceptions differing only by two sections promoted into
the head, both verified verbatim there.

**Nothing was lost. Five readers broke anyway**, and each returned a number that
reads as an answer rather than as a wrong question:

| reader | before | after the split |
|---|---|---|
| `check-retirement-conditions.sh` | `present=1`, due 4, exit 1 | `present=0`, due **2**, NOT-DUE bucket **gone**, exit 2 |
| `grep 'OWNER RULING' RULINGS.md` | 23 | **0** |
| `grep PROVISIONAL RULINGS.md` | 47 | **1** |
| `grep rollback RELAY.md` | 145 | **0** |
| `rotate-ledger.sh --apply` | — (never run against the new shape) | FATAL, every ledger, every time, moved nothing |

⚠️ **THE DIRECTION OF THE FAILURE IS WHAT MAKES IT DANGEROUS.** Every one of
those zeroes reads as ***"there are none"***, never as ***"you looked in the
wrong place"***. A session asking *"is this an OWNER RULING I may not
overturn?"* gets `0, exit 1` and proceeds. A session building the morning report
writes a PROVISIONAL block with **zero rows** while 47 rulings await review.
**That is the CONTRADICTION failure the ledger exists to prevent, arriving
through the file that prevents it.**

**AND ONLY ONE OF THE FIVE WAS CAUGHT BY CI** — the retirement sweep, because it
happened to be driven by a gate. The other four were watched by nothing, and the
split's own new gate was green throughout, correctly, because its watched set
was the file pair and the rules' named set was *what a grep returns*. That is
the standing *"a gate's WATCHED SET is diffed against the spec's NAMED set"*
entry, met in the wild at full scale.

## THE SWEEP, AS A CHECKLIST

Before a split lands, enumerate and TEST each class — by running the command,
not by reasoning about it:

1. **Scripts** that read the path — by literal, by variable, by composed name.
2. **Gates**, including the ones that reach the file INDIRECTLY through a script.
3. **Instruction files** — `MASTER.md`, `AGENTS.md`, `INBOX.md`, canon. *This is
   the half nothing executes, so nothing would ever have caught it.*
4. **The file's own banner**, which is now describing a size it no longer has.
5. **Citations by line number**, if the index promises they resolve.
6. **The rotation tool itself**, against the shape the split just created —
   a manifest of headings written for a file nobody ran it against.

⚠️ **AND STATE THE STATUS CONTRACT EXPLICITLY.** If a grep of the head is a
mandated route, the head must keep answering it: the cure here was one status
token per index row, in a column of its own, so `grep '[|] PROVISIONAL [|]'`
returns the row count and cannot be inflated by the word appearing in prose.
**An index that preserves content and drops the grep contract has preserved the
wrong thing.**
