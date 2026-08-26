> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **118 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ Close-out hygiene — reap the scratch, every session ▸ A tracked clinical file means a HISTORY REWRITE, not `git rm`**.
> Why the split: `docs/canon/README.md`.

#### `refs/pull/*` is the namespace the rewrite cannot reach

A force-push fixes branches and tags. It does nothing to `refs/pull/*`, which
GitHub owns and serves read-only. After the 2026-07-27 purge reported success,
a `git clone --mirror` of origin **still returned the blob** — from 11 pull refs.
Two distinct traps:

- **`refs/pull/N/merge` on an OPEN pr.** GitHub continuously recomputes a
  test-merge of every open PR *into the base branch*. Eight dependabot PRs that
  had never touched the file got merge refs carrying it, because GitHub merged
  them into a `main` that was still poisoned. **The poison arrives from the base
  side.** So "no open PR touched the file" is the wrong check and will clear a
  repo that is not clean — the right check is to enumerate every ref on origin
  and test each one. Closing the PR drops its `/merge` ref (verify against a
  closed PR as a negative control); dependabot regenerates it against the
  rewritten base.
- **`refs/pull/N/head` on a CLOSED or MERGED pr is permanent.** It cannot be
  pushed, deleted or expired, and because it is a *live ref* the object is
  reachable — GitHub's GC will never collect it. Only a **GitHub Support
  request** removes it. Budget for this: a rewrite is not finished when the
  push lands.

Verify with `git clone --mirror` and scan every ref, not with a plain clone —
a default clone does not fetch `refs/pull/*` and will look clean either way.
And shred the mirror afterwards; it is a blob-carrying copy.

`filter-repo`'s `commit-map` disappears with `.git/filter-repo/`, but GitHub's
**workflow-run history survives the rewrite** and still pairs pre-rewrite head
SHAs with commit titles — use it to repair dangling SHA references in docs.

**Filled exports never belong under `docs/`.** Nothing that renders a patient's
note belongs in the repository at all — not as evidence, not as a QA artifact,
not "just this once". Reference it by path in a report; do not commit it.

A pre-commit guard blocks added `.docx`/`.pdf` outside the fixture allowlist
(`scripts/hooks/pre-commit`). It installs itself — the root `prepare` script
sets `core.hooksPath` on `npm install`, because a guard that depends on every
future contributor remembering a setup command is a guard that is off.

It is a backstop, not the rule. The rule is the paragraph above.

