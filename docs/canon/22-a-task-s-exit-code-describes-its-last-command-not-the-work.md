> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **40 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A TASK'S EXIT CODE DESCRIBES ITS LAST COMMAND, NOT THE WORK

**Standing 2026-08-25.**

> **VERIFY THE WORK, NOT THE WRAPPER.**

A backgrounded task reported **`failed with exit code 1`**. The merge it ran had
**succeeded** — the PR read `MERGED` with its commit sha. The `1` came from the
script's own trailing short-circuit:

    [ "$DONE" = "no" ] && echo "..."     # returns 1 when DONE=yes

The last command's status became the task's status. Nothing was wrong.

⚠️ **THE SAME SHAPE, EARLIER THE SAME DAY:** a checks-runner helper ended with
`[ $rc -ne 0 ] && echo ...`, so a run in which **every check passed** exited `1`.
Twice in one session, from the tidiest-looking line in the script.

**Both directions are live and the second is the dangerous one:**

| | |
|---|---|
| **false FAILURE** | the work succeeded, the wrapper says no — wastes a re-run, or worse, a *repeat of an irreversible act* |
| **false SUCCESS** | the last command was an `echo`, so the script exits `0` over a failed step upstream |

**THE PRACTICE:** when a script's outcome matters, **read the outcome from the
system that owns it** — `gh pr view` for a merge, the database for a write, the
image id for a deploy — not from the exit code of the shell that asked. And end
any script whose status is load-bearing with an **explicit** `exit`, never with a
bare conditional.

⚠️ **AND NEVER RE-RUN AN IRREVERSIBLE ACT ON A WRAPPER'S SAY-SO.** A merge, a
migration, a mutation: establish from the owning system whether it already
happened. This is the `retire-branch` / `merge-pr` refusal-to-claim discipline
pointed at your own scripts.

