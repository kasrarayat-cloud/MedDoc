> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **32 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## WORK PRODUCED WHILE A CITATION RUNS IS STAGED, NEVER PUSHED INTO IT

**Standing 2026-08-23. The constructive half of the batching rule.**

The batching rule says *hold the first push until the session's remaining
commits are written*. It does not cover the case where the first push has
ALREADY gone out and the session keeps working — which is most sessions, because
a citation takes half an hour and nobody sits idle through it.

> **Once a branch is pushed and its runs are in flight, that branch is CLOSED to
> this session. Further work is written to scratch and lands as its OWN PR.**

The failure it prevents is the one this file has paid for five times: a second
commit pushed minutes into a run cancels `CI`, `e2e` and `a11y-ci`, and the cost
scales with how late it lands. Staging costs nothing — the work is written
either way; only the push is deferred.

⚠️ **AND WHERE BOTH TOUCH THE SAME FILE, BRANCH THE SECOND PR OFF THE MERGED
FIRST — not off the current `main`.** Two branches editing `AGENTS.md` from a
common ancestor manufacture a conflict that neither change required. Waiting for
the merge is not politeness; it is the cheaper merge.

