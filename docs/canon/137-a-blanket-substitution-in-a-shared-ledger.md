# A BLANKET SUBSTITUTION IN A SHARED LEDGER REWRITES **EVERY LANE'S** ROWS

**Ratified 2026-09-07.** A renumbering that was correct in intent and scoped by
the wrong unit.

Two ruling numbers had to move because a peer lane landed first (#219: *a branch
is a claim, a merged row is a fact*). The rewrite was scoped to **the files my
own commits had touched** — which sounds careful, and is the wrong unit:

> **`docs/foundation/RULINGS.md` is ONE FILE containing EVERY LANE'S ROWS.**
> File-level scoping does not exist there. Scope is per-ROW.

The substitutions were length-preserving (`#233` → `#246`, `canon 128` → `canon
131`), so they fired inside **other people's verdict text** wherever a row
happened to cite those numbers — and silently altered **eight rows**: `#106`,
`#109`, `#115`, `#116` twice, `#131` twice, and `#237`.

**Nothing looked wrong.** Same line count, same lengths, valid markdown, and a
`git diff --numstat` showing only the additions expected from a renumber.

## ⚠️ AND KEY-BASED REPAIR WAS NOT ENOUGH EITHER

The obvious fix — index main's rows by `(date, number)` and restore any that
differ — **cannot work when a key recurs**, and here `#116` and `#131` each
appear twice. A map keeps the last one and silently drops the other.

> **When the keys recur, stop repairing and REBUILD FROM THE FACT:** take the
> other lane's file verbatim, re-append only your own rows, and then PROVE it —
> every one of their rows byte-present, zero lost, exactly your N added.

That is a construction whose correctness is checkable in one command. The repair
was an argument.

## ⚠️ A GATE FOUND IT, AND ONLY BECAUSE IT COMPARED BYTES

`gate-ruling-row-identity` asserts a ruling row is **the same bytes** in the head
and in its archive. It reported `#237` drifting — one row — and pulling that
thread surfaced all eight. A gate comparing *presence*, or *numbers*, or *row
counts* would have passed: every row was present, correctly numbered and
correctly counted. **It was the text inside them that had changed.**

**The rule:** in a file other lanes write to, edit **by key**, never by pattern —
and when a key is not unique, rebuild from their copy rather than patch yours.
