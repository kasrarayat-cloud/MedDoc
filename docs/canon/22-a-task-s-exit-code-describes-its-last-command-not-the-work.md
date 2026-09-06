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


---

## ⚠️ AND THE WRAPPER CAN BE ONE **YOU** ADDED — A PIPE REPLACES THE EXIT CODE

**Appended 2026-09-05, from the merge of PR #946.**

Everything above is about a script's own trailing line. This is the same defect
one layer further out, and it is the **false SUCCESS** direction the table calls
the dangerous one: **the wrapper was not in the script. It was in how I invoked
it.**

A backgrounded merge helper was run as

    bash <helper> 946 | tail -20

so the status the harness reported was **`tail`'s**. `tail` succeeds on any
input, including none. The notification read **exit code 0** for a script that
had **exited 1** after retrying for fifty minutes and giving up.

> **A PIPELINE'S EXIT STATUS IS ITS LAST COMMAND'S — so every pipe you add is a
> new wrapper, and yours is invisible in the script you are reading.**

`set -o pipefail` is off by default and does not reach a pipeline typed at a
prompt. `PIPESTATUS` holds the answer and nobody consults it. Neither the script
nor its author was careless here; the defect was introduced by the `| tail` I
added to keep the output short.

⚠️ **NOTHING IN THE OUTPUT DISAGREED WITH ITSELF.** A clean `exit code 0` over
twenty tidy lines of log is not a contradiction to notice — which is why this
one cannot be caught by reading harder. It was caught by **this entry's own
practice**: asking the system that owns the outcome. `gh pr view 946` returned
**`state=OPEN merged=NO`**, and #946 was still unmerged an hour after the
wrapper said it was done.

**The harm the practice prevented was not a repeated irreversible act — it was
worse-shaped than that.** The next steps in the queue were sequenced *behind*
#946. Believing the wrapper would have meant continuing to merge on a premise
that was false, with every later citation resting on it.

**So the practice gains a clause:** when a script's status is load-bearing,
**do not pipe it.** Redirect to a file and read the file, or capture
`${PIPESTATUS[0]}` — and still confirm the outcome with the owning system,
because the pipe is only the wrapper you can see.

⚠️ **AND IT RECURRED TEN MINUTES AFTER THIS PARAGRAPH WAS WRITTEN, IN THE
SESSION THAT WROTE IT.** Probing whether `gh pr edit --base` works in this
build, I ran it as `gh pr edit 954 --base main 2>&1 | head -5` and reported
**`exit=0`**. That zero was `head`'s. Re-measured without the pipe, the command
**exits 1** — so for one turn the record said a broken door worked.

**The rule did not fail because it was disputed or forgotten; it failed while
being actively written about.** That is [canon 93](93-a-rule-that-depends-on-remembering-has-a-failure-rate.md)'s
shape exactly — *writing a lesson down does not cause obedience to it, nor does
having just written it* — and it is the argument for the mechanical form over
the remembered one. **A pipe is added for readability, at the end, by reflex,
to a command whose exit code you were about to trust.**
