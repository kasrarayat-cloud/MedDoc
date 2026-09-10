# ⚠️ A COMMIT VANISHED BETWEEN `git commit` AND `git push`, AND THE PUSH REPORTED SUCCESS

**Filed 2026-09-06 by the custom-file session, from losing 1,127 lines of its
own finished work for ninety seconds.** Recovered in full. Nothing shipped
wrong. The filing is about the ninety seconds.

## WHAT HAPPENED, FROM THE REFLOG — the part that is not in dispute

Worktree `/opt/meddoc-pro/.wt-omit`, branch `feat/review-defaults-omit-door`:

| at | ref | what |
|---|---|---|
| `17:48:12` | `refs/heads/…omit-door` | **commit `564c95b5`** — six files, 1,127 insertions |
| `17:48:47` | `refs/heads/…omit-door` | **`reset: moving to HEAD~1`** → back to `0e7ddd02` |
| `17:48:49` | `refs/remotes/origin/…omit-door` | **`update by push`** → `564c95b5` |
| `17:49:3x` | *(server, via `git ls-remote`)* | **`0e7ddd02`** |
| `17:49:59` | `refs/heads/…omit-door` | `reset: moving to 564c95b5` — the recovery |

**I ran no reset.** The command that straddles `17:48:47` was a single
`git push -u … && cat > body.md && gh pr create`, and none of its parts resets a
branch. Thirty-five seconds after the commit, the branch was one commit shorter
and the six files were back in the working tree as uncommitted changes.

## ⚠️ AND THE PUSH SAID IT WORKED

    * [new branch]        feat/review-defaults-omit-door -> feat/review-defaults-omit-door

That line names a **ref**, not a **commit**. It is emitted whenever a ref is
created, whatever it points at. Nothing about the output distinguishes *"your
1,127-line commit is on origin"* from *"an empty branch at `main` is on origin"*.

The failure surfaced one command later and by luck, as:

    pull request create failed: GraphQL: No commits between main and
    feat/review-defaults-omit-door

> **`gh pr create` refusing an empty branch is what told me the work was gone.
> Nothing else did.** Had the branch carried one earlier commit, that refusal
> would not have fired, the PR would have opened, and the missing work would
> have been discovered — if ever — by somebody reading the diff.

## ⚠️ THE INSTRUMENT LESSON, WHICH IS THE REUSABLE HALF

**`refs/remotes/origin/<branch>` is a CACHE OF A BELIEF, NOT AN OBSERVATION OF
THE SERVER.** At `17:48:49` the remote-tracking ref recorded `564c95b5`. Seconds
later `git ls-remote --heads origin <branch>` — which asks the server —
returned `0e7ddd02`. The two disagreed about the same ref at almost the same
moment, and **the local one was the confident one.**

    git ls-remote --heads origin <branch>     # asks the SERVER
    git rev-parse origin/<branch>             # asks a LOCAL CACHE

This is the same shape this repository has already recorded three times in a
week under a different costume — `gh run list --commit` answering correctly
about a set the server had not finished populating; a scan of `origin` for a
file that was local; a grep of `main` for a gate that lived on a branch. **A
right question asked of the wrong universe, answered with no hint that the
universe was wrong.**

> **VERIFY A PUSH BY THE SHA YOU MEANT, AGAINST THE SERVER:**
>
>     git push origin "$B" && \
>       [ "$(git ls-remote --heads origin "$B" | cut -f1)" = "$(git rev-parse HEAD)" ] \
>       || echo "🔴 origin does not carry what you just built"

## WHAT I CANNOT DEMONSTRATE, SAID PLAINLY

**I do not know what ran the reset, and I am not going to guess in a filing.**

What is established: the reset happened, it was not mine, and two other
`claude --dangerously-skip-permissions` processes (pids `814702` and `859606`,
started `17:10:05` and `17:16:57`) were live in `/opt/meddoc-pro` at the time.
No `post-commit` hook exists; `core.hooksPath` carries only `pre-commit` and
`pre-push`.

What is **not** established: whether the server ever briefly held `564c95b5` and
was moved back, or whether the push delivered `0e7ddd02` while the tracking ref
recorded the pre-reset value. The two readings differ in whether a force-push
occurred, and the evidence I have does not separate them. **Recording a
mechanism I cannot show would make this filing the third unreliable instrument
in its own story.**

## THE HABIT THIS EARNS, AND IT IS CHEAP

**A commit in a shared tree is not durable until origin confirms it by sha.**
The window between `git commit` and a *verified* push is a window in which
finished work can disappear with no error anywhere.

1. **Push immediately after committing**, not after the next step.
2. **Confirm by sha against `ls-remote`**, never by the push's own output.
3. **Pin anything expensive with a tag** — `git tag pin/<thing> <sha>` and push
   the tag. A tag survives a branch reset, no workflow in this repo triggers on
   tags (measured: zero `tags:` filters across `.github/workflows/*.yml`), and
   pushing one therefore cancels nothing. This is what made the recovery here a
   ninety-second inconvenience.

## ⚠️ AND IT IS A NEW FACE OF A NAMED CLASS

`AGENTS.md` § *THE SHARED TREE IS A DEPLOY SURFACE* says **two sessions, one
working tree, is a CLASS — not two incidents**, and names two faces: a deploy
shipping the wrong commit, and a worktree deploy breaking ingress. Both are
about a session reading state another session moved.

**This is the third face, and it is the one that bites while you are working
correctly:** a session's own *committed* work, in its own dedicated worktree,
moved underneath it — with the standard tooling reporting success throughout.
The existing entry's advice ("all feature work happens in an isolated
worktree") was followed here in full. It was not enough, because the isolation
git provides is of the *index and working tree*, never of the *refs* — every
worktree of a repository shares one `refs/heads/`.

> **A worktree is not a sandbox. `git worktree` isolates the checkout; the
> branch namespace stays shared, and a branch is what a commit lives on.**
