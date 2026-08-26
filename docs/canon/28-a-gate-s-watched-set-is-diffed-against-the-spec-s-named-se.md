> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **50 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A gate's WATCHED SET is diffed against the spec's NAMED set

**Sibling of the section above, not a duplicate — and the difference is the
whole point. That one measures the wrong QUANTITY over the right universe. This
one measures the right quantity over the WRONG UNIVERSE.** A check can be
flawless at counting a set that does not contain the thing you were asked to
protect, and its zero is then perfectly true and completely worthless.

> **Before any gate's zero is believed, diff what it WATCHES against what the
> item's acceptance criteria NAME.**

**Reference case — `doctor_edit_patterns`, 2026-08-06.** T5's spec said, in as
many words: *"the guard must also catch `doctor_edit_patterns` (DISCOVERY §B.4),
which is the table a source grep is most likely to miss and the one that LEAKS
WHOLE NOTES."* The table was absent from the guard's `CLINICAL_MODELS` through
all three adoption tranches, so **the ratchet reached zero having never looked at
it** — and `doctor_edit_patterns` stores `originalSoap` and `editedSoap` as full
text, making an unscoped read of it a LARGER disclosure than an unscoped read of
a visit row.

⚠️ **NOTHING WOULD EVER HAVE SURFACED IT.** Both of its reads happen to be
correct. No test failed. No sweep complained. There is no observable difference
between "the guard watched it and found nothing" and "the guard never watched
it" — which is precisely why the spec named the table by hand instead of trusting
whoever built the model list.

It was found by **re-reading the item's own acceptance criteria while writing the
close-out row** — not by any check, and after the gate had already been declared
met. So the discipline is a step, not an instinct:

1. **List what the gate watches.** Literally: the model list, the path globs, the
   route set, the table names. If you cannot enumerate it, that is the finding.
2. **List what the spec names.** Its acceptance criteria, its DISCOVERY
   references, the tables and surfaces it calls out by hand.
3. **Diff the two, in writing, before claiming the gate is met.** Anything the
   spec names and the gate does not watch is an open item, however green the run
   was.

**"The gate passing is not the gate covering what was asked."** A spec is a
checklist, and the most confident-looking zero in a programme is the one produced
over a universe nobody re-checked.

### ⚠️ AND THE SAME SHAPE IN A KILL SWITCH: IT HALTED A LOOP THAT WAS WORKING

**Standing 2026-08-19.** The section above describes a gate whose zero is
worthless. This is the inverse cost: a check that measures the wrong universe
and **fires**, stopping work that was demonstrably happening.

> **A progress signal must be read where progress LANDS.** The FOUNDATION loop's
> no-progress switch hashed the SHARED WORKING TREE's `RELAY.md`, while sessions
> do their work in WORKTREES and land it on ORIGIN.

The shared tree fast-forwards only at session START, so a session's own merges
are invisible to the switch that judges it: `ledger_after` can never differ from
`ledger_before` for work that session landed itself.

⚠️ **MEASURED COST — 2026-08-19T12:44:53Z, 1h45m of dark loop.** Session 04
merged **three** PRs and added **615 lines** to `RELAY.md`, closing F12-g
(#742 merged `12:07:30Z`, thirty-seven minutes before the halt). The switch read
two identical hashes and stopped. Every word of its halt message was true about
the file it hashed and false about the programme.

**Fixed (ruling #132, PR #744) by reading the ledger from `origin/main`**, in
`scripts/lib/ledger-progress.sh`, proved in both directions by
`gate-f20-ledger-progress-universe.test.ts`: a session that lands on origin
counts as progress *even with the tree left behind*, and an idle pair still
halts. **The idle arm is the one that matters** — anyone can stop a switch
firing, and a fix that made the loop unstoppable would be strictly worse than
the bug.

⚠️ **TWO SESSIONS FIXED THIS INDEPENDENTLY, AND THE COMPARISON IS THE USEFUL
PART.** A supervised session built the same fix by capturing
`$(git show origin/main:$LEDGER)` into a variable. The loop's version PIPES
instead, and its comment says why: **`$(…)` STRIPS TRAILING NEWLINES**, so the
captured form hashes something that is not the blob — deterministic, working,
and wrong in a way nobody would ever notice. The supervised PR was closed as
superseded. *A convergent fix is a chance to diff two solutions, not a
duplication to regret.*

⚠️ **AND THE PIPE ITSELF CARRIES A TRAP, WHICH IS WHY THE SHIPPED VERSION ASKS
`git cat-file -e` FIRST.** On failure `git show` writes nothing and exits
non-zero — **and the pipe runs anyway**, so `sha256sum` hashes EMPTY STDIN and
returns the constant `e3b0c442…855`. A valid-looking hash, **identical on every
broken read**, so two blind sessions would compare equal and reproduce the very
false halt the function exists to prevent. The shipped lib makes that
unreachable by proving the blob exists before piping, and returns
`CANNOT-TELL:<reason>` sentinels rather than a bare blank, so a blind
instrument never halts a loop that may be working.

> **Piping a command into a hasher discards its exit code and converts a
> FAILURE into a stable, plausible VALUE.** Any `X | sha256sum`, `X | wc -l`,
> `X | jq` has this shape.



