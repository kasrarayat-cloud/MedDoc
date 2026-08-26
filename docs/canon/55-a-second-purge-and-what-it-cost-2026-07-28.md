> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **121 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ Close-out hygiene — reap the scratch, every session ▸ A tracked clinical file means a HISTORY REWRITE, not `git rm`**.
> Why the split: `docs/canon/README.md`.

#### A second purge, and what it cost — 2026-07-28

`docs/smoke-test-2026-05-04/phase-C/export.docx` and `export.pdf` were tracked
FILLED exports. The content was plainly synthetic ("Dr. Smoke Tester MD",
patient "Smoke TestPatient One"), and the ruling was that **it makes no
difference**: the close-out rule treats a filled clinical export as PHI
regardless, so there is no adjudication class and no argument to have at the
moment one is found. They were purged by `git filter-repo`. Do not re-add them;
the rest of `docs/smoke-test-2026-05-04/` is untouched and stays.

**It was ~200× the work of the first purge, for the same two files' worth of
content, purely because it had been sitting there longer.** The twin export was
four days old: one branch, ten tags, one commit pruned. These were committed on
2026-05-04 in PR #108, so by the time they were removed they were in **75 of
141 branches and tags**, 104 local branches, 31 stale clones on the box — and,
permanently, in **300 `refs/pull/*` refs**, one per PR opened since. That last
number is the one that does not come back down: `refs/pull/*` is GitHub-owned
and unpushable, so the residual grew by one ref per PR for every day the files
stayed. The cost of a tracked clinical file is not fixed. It compounds.

