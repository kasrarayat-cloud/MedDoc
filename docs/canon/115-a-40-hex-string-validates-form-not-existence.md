# A 40-HEX STRING VALIDATES FORM, NOT EXISTENCE — RESOLVE, NEVER EXTEND

**Canon 2026-09-06, from a wait that finished instantly on a commit that does not
exist.** Full incident: `docs/foundation/board/A-FABRICATED-SHA-MAKES-EVERY-INSTRUMENT-AGREE.md`.

## THE RULE

> **NEVER EXTEND A SHORT SHA. RESOLVE IT, AND PROVE THE OBJECT EXISTS.**

    SHA=$(git rev-parse "origin/main^{commit}")
    git cat-file -e "$SHA" || { echo "🔴 no such object"; exit 1; }

A SHA that came out of `rev-parse` cannot be fabricated. One typed, remembered,
or extended from a short form always can.

## WHY THE EXISTING RULE DID NOT COVER IT

`AGENTS.md` already requires the **full 40 characters**, because
`gh run list --commit <SHORT-sha>` returns `[]` for any abbreviation. **That rule
was obeyed.** It is about the LENGTH of the string, and length was never the
problem — **PROVENANCE** was. A fabricated 40-character SHA satisfies every stated
requirement and is wrong in the only way that matters.

| | |
|---|---|
| what was written | `e11612d2`**`13d8a1a4c1b8a9c8e4b6c9d2f3a5e7b1`** |
| the actual commit | `e11612d2`**`e784c97947bc782fd4d7d6a8cb6d0069`** |
| shared | **8 characters** |

## ⚠️ EVERY INSTRUMENT AGREED WITH THE FABRICATION

**1 · `gh` returns an EMPTY LIST for a commit that does not exist.** The waiter
was *"wait while anything is not completed"*, so *nothing is incomplete* was true
on the first sample. It printed a heading, no rows, and **exit 0**.

> **AN EMPTY CITATION AND A COMPLETE ONE ARE THE SAME SHAPE WHEN THE ONLY TEST IS
> "IS ANYTHING STILL RUNNING?"** Absence of pending is not presence of green.

**2 · `git rev-parse --verify` ECHOED THE INVENTION BACK AND EXITED 0.** On a full
40-hex string it validates the FORM, not the EXISTENCE — so the obvious
confirmation step confirms the fabrication. The tests that ask the object database
are `git cat-file -e` and `rev-parse <sha>^{commit}`.

## THE COMPANION FIX: A WAIT NEEDS A POSITIVE CONTROL ON ITS WATCHED SET

    until [ "$(… | select(.status!="completed") | length)" = "0" ] \
       && [ "$(… | length)" -ge 4 ]; do sleep 60; done

**Nothing pending AND at least four runs registered.** The `-ge 4` refuses to call
a citation complete until the runs it cites actually exist. That closes the
fabricated-SHA hole **and** the propagation-window hole `AGENTS.md` documents —
where a REAL sha legitimately returns zero runs for a few seconds right after a
push, which is precisely when this check gets run.

> **A CHECK WHOSE PASSING CONDITION IS AN EMPTY SET PASSES HARDEST WHEN IT IS
> POINTED AT NOTHING.** Same defect as a green suite with zero collected tests,
> and as a grep scoring 0 because it searched the wrong tree. This is that class
> wearing a commit hash.

⚠️ **AND THIS HOUSE HAS PAID FOR IT ONCE ALREADY.** Canon 61 records a session
reporting the `--commit`/`--branch` divergence as observed and then withdrawing
it, because its `--commit` was empty for the boring reason that **the SHA had been
fabricated from memory**. That one reached a filing before it was caught.
