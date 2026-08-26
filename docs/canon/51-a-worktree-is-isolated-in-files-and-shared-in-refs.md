> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **108 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A WORKTREE IS ISOLATED IN **FILES** AND SHARED IN **REFS**

**Standing 2026-08-14, and it is the half nobody expects — because the whole
reason anyone reaches for a worktree is isolation.**

> **`git checkout` / `git reset --hard` inside a worktree moves the branch ref
> for EVERY worktree sharing the repository.** The files are private. The refs
> are not.

⚠️ **REFERENCE CASE — R5's merge, and it came one `git commit` away from
undoing the entire item.** After merging PR #652 I was still standing on the
retired branch, so `retire-branch.sh` correctly refused to delete the local copy
("left in place — not claiming success"). To move off it I ran, IN MY WORKTREE:

    git checkout -B main origin/main && git reset --hard origin/main

That moved the SHARED `main` out from under `/opt/meddoc-pro`, which had `main`
checked out. Its HEAD jumped to the merge commit; its FILES stayed at the
previous one. `git status` there then showed 53 modified, 6 deleted — and **ten
files staged as ADDED that were exactly R5's deletions**: `rx-tab.tsx`,
`rx-warning-card.tsx`, `override-confirm-modal.tsx`, both `dev/rx-warnings`
files, `rxGate.ts`, and E2E scenarios 24 and 25.

**A `git commit` in that tree would have resurrected the whole deleted surface**
— in a tree that looked superficially normal, minutes after the merge, with the
deploy still ahead of it.

### THE SAFE EXIT, AND THE REPAIR

- **Leaving a branch you are retiring: `git checkout --detach` first.** It moves
  no shared ref. Only then delete the branch.
- **Repairing a tree whose HEAD moved under it: ESTABLISH WHAT IS TRUE BEFORE
  CHOOSING A REPAIR.** `git diff --quiet <the commit the files should match>`
  proved the working tree was byte-identical to where the other session left it,
  so nothing uncommitted existed to lose — *then* the reset was safe. Capture
  the staged-add list (`git diff --cached --name-only --diff-filter=A`) before
  resetting, so the cleanup is computed rather than guessed.
- ⚠️ **DO NOT REACH FOR `git clean` ON A TREE YOU HAVE JUST BROKEN.** It is the
  instrument most likely to convert a recoverable ref confusion into permanent
  loss, and at that moment you do not yet know what is untracked-and-precious
  versus untracked-and-residue.

This is the "restore from BACKUP, not from git" rule arriving one layer up: the
question is not which command restores the file, it is **what was true before
you touched anything**, established first and in writing.

