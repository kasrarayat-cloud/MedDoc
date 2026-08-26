> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **85 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ THE SHARED TREE IS A DEPLOY SURFACE, NOT A WORKSPACE**.
> Why the split: `docs/canon/README.md`.

#### ⚠️ THIRD INSTANCE, 2026-08-23 — AND IT CAME FROM A `cd` IN AN EARLIER COMMAND

A supervised session ran `git merge --ff-only origin/main` intending the shared
tree, **in a WORKTREE** — the `cd` had carried over from a merge two commands
earlier. It then reported *"tree head == origin/main"* from that worktree and
moved toward the deploy.

**The SHARED tree was still four commits behind at `cea1823c`.**
`deploy-prod.sh` reads the shared tree's HEAD, so the deploy would have shipped
`cea1823c` **under a declaration naming `25cab8e7`** — the wrong-commit
declaration this section already names as *worse than no declaration, because it
looks like evidence*.

⚠️ **THE TELL WAS IN MY OWN SUMMARY LINE AND IT READ AS CONFIRMATION.**
"tree head == origin/main" was TRUE of the tree it measured. Caught only by
running `git rev-parse` **in `/opt/meddoc-pro` specifically**, one command before
the deploy — checking the tree about to ship rather than trusting a sentence
written about a different one.

> **Before a deploy, resolve the shared tree BY ABSOLUTE PATH.** `git -C
> /opt/meddoc-pro rev-parse HEAD`. A relative check inherits whatever `cd` ran
> last, and the failure is silent because the answer it gives is true about
> something.

**Neither was caught by a check. Both were caught by somebody re-reading state
they had no particular reason to re-read** — which is exactly the property you
cannot schedule. Hence the rule instead: keep the deploy surface boring, and put
the work somewhere that cannot reach it.

⚠️ **AND THE COORDINATION MOVE IS TO ASK, NOT TO FIX IT YOURSELF.** The correct
response to finding the shared tree on someone else's branch is to ask that
session to move it — never `git checkout` under another actor. On 2026-08-14
that ask paid for itself twice over: the other session, forced to commit before
switching, read its staged file list and found a migration written to
`apps/transcribe-md/packages/db/prisma/migrations/` — a path Prisma would never
have read and `assert-migrations-applied` would never have known to look at. It
would have surfaced in production as *"the column does not exist"*.

