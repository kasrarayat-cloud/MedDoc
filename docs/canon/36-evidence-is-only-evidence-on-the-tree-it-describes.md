> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **70 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## EVIDENCE IS ONLY EVIDENCE ON THE TREE IT DESCRIBES
### A count inherited from another report, then incremented by assumption

**Same family, arriving through arithmetic instead of a command.** A number
carried forward from somebody else's write-up is inherited evidence: it
described *their* tree at *their* moment. Adding to it without re-measuring
manufactures a figure that was never observed by anyone.

> **"A count carried forward from another session's report and then incremented
> by assumption is a fabricated number, however small the increment."**
> — FOUNDATION session 04, 2026-08-10, catching it in its own draft

The instance: a row was drafted saying `nightly-tests` had failed **four**
nights and filed a **fourth** issue. The previous session's report had already
counted the 08-10 run; this one assumed a new failure had appeared overnight and
added one. Re-measured before committing —
`gh run list --workflow nightly-tests.yml` gives **3** failures after 3
successes, and `gh issue list` gives exactly **three** issues.

⚠️ **It was caught in the drafting, not by a check, and nothing would have
caught it later** — a plausible count in a ledger row is indistinguishable from a
measured one once it is committed. **Re-measure any number you did not observe
yourself, in the same pass that you write it down.**


**Every verification chain guards on the state transition it assumes — a rebase's
or merge's exit code, a clean `git status` — BEFORE its numbers count.**
Measurements taken mid-rebase, mid-merge or on a dirty tree are **fabricated by
accident**: they are real outputs of a real command describing a tree that does
not and will not exist.

> **The mechanism is almost always an `&&` chain that does not guard the
> transition.** `git rebase … | tail -1` swallows the failure, the next command
> runs anyway, and its numbers look exactly like success.

⚠️ **REFERENCE CASE, 2026-08-07.** A rebase reported *"Could not apply"*, the
chain continued, and `tsc`/`vitest` printed **"0 errors / 3194 passed" from a
half-merged tree with conflict markers in it.** The push that followed was
harmless — during a rebase the branch ref still points at the original commits,
so the remote received the un-rebased branch — but the EVIDENCE was worthless
while looking authoritative. Re-measured after resolving: the same numbers, now
meaning something.

The shape that prevents it:

    git rebase origin/main || { echo "REBASE CONFLICT — stop"; exit 1; }
    git status --porcelain | grep -q . && { echo "DIRTY — stop"; exit 1; }
    # only now do measurements count

**And when it happens, say so.** Numbers printed from a broken tree must be
withdrawn explicitly, not quietly re-run — a reader who saw the first pair has no
way to know the second replaced them.

