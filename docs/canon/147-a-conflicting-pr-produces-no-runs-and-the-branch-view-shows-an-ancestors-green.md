# A CONFLICTING PR PRODUCES NO RUNS — AND THE BRANCH VIEW SHOWS AN ANCESTOR'S GREEN

**Standing 2026-09-08. Found on PR #1018, after two pushes that cited nothing.**

> **A pull request whose `mergeable` is `CONFLICTING` creates NO workflow runs at
> all. Not queued, not skipped, not failed — never created. Nothing anywhere
> says so, and the branch view keeps answering with the last green it saw.**

Every required workflow here takes a bare `pull_request:`, which checks out
`refs/pull/<n>/merge`. GitHub cannot build that ref while the PR conflicts, so
it does not schedule the run. There is no annotation, no check listed as
skipped, and no line in the PR's own checks tab — the tab is simply empty of
anything new.

## THE MEASUREMENT

Two pushes to `feat/review-defaults-omit-door` — `dd21ed75` and `27d87bd2` —
created **zero** runs. Actions was healthy the whole time: a push to
`feat/union-ledger-resolver` at `23:04:43Z` fired all four, and a peer's branch
fired at `22:57`. The repo-wide queue was two in-progress and one queued, so
there was no backlog to blame. Polled for nine minutes after the second push:
still zero.

| PR | draft | `mergeable` | `mergeStateStatus` | runs on the pushed sha |
|---|---|---|---|---|
| #1018 | yes | **`CONFLICTING`** | `DIRTY` | **0** |
| #1071 | yes | `MERGEABLE` | `BLOCKED` | 4 |

⚠️ **BOTH WERE DRAFTS**, which is what excludes the obvious suspect. Draft state
is not the cause; the conflict is.

**AND THE CONVERSE WAS MEASURED, NOT ASSUMED.** Merging `origin/main` to clear
the conflict and pushing `49e618a6` fired all four within **fifty seconds**, on
the same branch, same workflows, same day.

## WHY THE TWO-VIEW CHECK CANNOT SEE IT

This is the part that makes it dangerous rather than merely annoying.

    gh run list --branch feat/review-defaults-omit-door
    -> completed success  e2e / secrets-scan / CI / a11y-ci

Four green runs. It reads exactly like a quiet, fully cited branch. They
belonged to `f8b19b0a`, an ancestor from **fourteen hours earlier**. Only
reading `headSha` off each row showed that the commit just pushed had nothing.

⚠️ **THE BY-COMMIT VIEW WAS RIGHT HERE, AND THAT IS THE TRAP.** It returned
empty, correctly. But a session that has internalised the documented
propagation-window defect — *"`--commit` under-reports right after a push"* —
will read that empty as the known lie and trust the branch view instead. **Two
readings are available and only one is right**, so the tell cannot be either
view on its own:

> **FOUR GREEN RUNS ON A BRANCH IS NOT FOUR GREEN RUNS ON YOUR COMMIT.**
> Compare `headSha` against `git rev-parse HEAD`, or the check is theatre.

It is the WATCHED-SET failure, not the broken-instrument one: the right question
asked of the wrong universe, with the instrument answering perfectly. The
existing entry on that distinction says a positive control cannot catch it, and
that holds here — the runs API was working, and answering about an ancestor.

## THE CHECK, AND IT IS ONE LINE

    gh pr view <n> --json mergeable,mergeStateStatus

`CONFLICTING` means **your last push cited nothing**, however long ago it was.
Not denied by `.claude/settings.json`, which carries no allowlist for `gh` and
denies only `gh pr merge` — verified by running it.

⚠️ **AND THE COST GROWS SILENTLY WITH TIME.** A branch can sit conflicted for
hours accumulating pushes, each one believed to be cited, while the checks tab
shows the same stale green. The longer it sits, the more confident the wrong
reading becomes — and a merge taken on that reading ships commits no gate has
ever seen.
