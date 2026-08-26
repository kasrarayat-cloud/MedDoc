> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **93 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## "RESTORE FROM GIT" AND "RESTORE FROM BACKUP" ARE NOT THE SAME OPERATION

**Standing rule for every mutation proof.** Before the FIRST mutation, copy
**every file the proof will touch** to scratch, and assert the copies exist. The
restore step then reads from those copies — never from git.

> **`git checkout -- <file>` restores the file to HEAD. On a dirty tree that
> DELETES uncommitted work, silently and unrecoverably.**

⚠️ **REFERENCE CASE, 2026-08-08 — B0-a, mid-proof.** Three files were backed up
to scratch and restored from there. A fourth, `anthropic.ts`, carried the
session's entire uncommitted rewire and was restored with
`git checkout -- packages/ai/src/anthropic.ts`. It reverted to HEAD; three
rewired call sites and two markers vanished. Nothing errored — the command
succeeded, which is exactly what it was asked to do.

The tell that it happened at all was a test count: the suite went from 4 passed
to 3 failed on a "restore" step. **Had the mutation under test been one that
leaves the suite green, the loss would have been silent** and the branch would
have been committed missing its own feature.

Two things generalise:

1. **The backup list is the file list, not the interesting files.** The three
   backed up were the ones the mutations targeted. The one lost was merely *the
   file being tested* — not obviously part of the proof, and the only one that
   mattered.
2. **Assert the backups before mutating**, the same way a scripted edit asserts
   its occurrence count. A restore that reads a file that was never written is
   a second silent failure stacked on the first.

