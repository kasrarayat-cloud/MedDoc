# A BRANCH THAT NEVER MET CI CARRIES AN UNMEASURED CLASS

**Recorded 2026-09-03, from the first CI contact of the ten-ruling #165–#175 arc.**

## The measurement

The arc was built over many sessions in a `git worktree` on the production VPS and
**never pushed**. When it finally went up, **46 commits met CI for the first time in
one go**, and produced exactly **one** red:

```
ENOENT: no such file or directory, open '/opt/meddoc-pro/WM IOV Template.docx'
```

A gate opened the customer's Word template by **absolute host path**. It had passed
locally for days, on every run, for one reason: the VPS working tree *is*
`/opt/meddoc-pro`. On a GitHub runner the repo lives at `/home/runner/.../MedDoc`
and the read cannot resolve.

⚠️ **THE REASON IT SURVIVED IS THE PART TO REMEMBER.** Every local instrument was
green, repeatedly:

| instrument | verdict locally | could it have seen this? |
|---|---|---|
| the **5663**-test suite | green | no — ran in `/opt/meddoc-pro` |
| `tsc --noEmit` | green | no — the path is a string |
| the full mutation matrix | green | no — same directory |
| three adversarial lenses | findings, none this | no — same directory |

All four ran from the **one directory where the path is correct**.

> **A PATH THAT IS RIGHT ON THE AUTHORING MACHINE AND NOWHERE ELSE IS INVISIBLE TO
> EVERY CHECK THAT RUNS ON THE AUTHORING MACHINE.**

## The class is wider than paths

Anything true of the authoring environment and nowhere else belongs to it: an
absolute path, an installed binary, a locale, an env var present in one shell, a
service reachable only from that host. **CI is the only instrument that samples a
DIFFERENT environment** — so a branch that has never met CI has not had that class
measured weakly. It has not had it measured at all.

## The practice, ratified with this entry

> **LONG-LIVED BRANCHES PUSH EARLY AS DRAFTS.**

A draft PR owes no citation and opens no merge door, so pushing early costs nothing
that matters and buys continuous sampling of the environment class — a few commits
at a time, where the offending line is obvious, instead of at 46-commit first
contact where it competes for attention with a clinical fix.

## The fix was by ground, not by hit

Per [canon 68](68-fix-by-ground-not-by-hit.md), the repair is not the one read that
CI happened to catch.

- The offending read now resolves from `__dirname` to a committed **in-app fixture**
  that is byte-identical to the root template — **sha256 verified, both tracked**.
- A new arm walks **every test file under `src/` and `tests/`** and refuses a
  filesystem call whose argument begins with an absolute host root: `/opt`, `/home`,
  `/Users`, `/var`, `/srv`.

⚠️ **AND IT STRIPS COMMENTS FIRST, OR THE GATE REPORTS ITS OWN DOCUMENTATION.**
Dozens of comments and strings legitimately *name* such paths — they document VPS
layout — and naming one is not calling one. A scanner that reads prose as code
reds on its own prose, and the next reader silences it rather than obeying it. Same
requirement as [canon 96](96-a-control-that-never-touches-a-file-cannot-guard-files.md).

**It carries a floor: the walk must have scanned at least 200 test files.** Without
one, an empty offender list is a fact about the walk, not about the tree.

**Mutation-proved:** restoring the exact absolute path CI caught reds the new arm,
and the failure message names it.

## Honest limits

- The arm watches **test files**, not application source. A production module
  reaching for an absolute host path is not covered by it.
- It matches five roots by prefix. A sixth root, or a path composed at runtime from
  a variable, passes — that is [canon 30](30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md)'s
  token-list defeat, and this arm has it.
- Pushing early samples **one** other environment: a GitHub runner. It says nothing
  about a third.
- **The entry claims nothing about the 46 commits' other content.** CI's one red is
  evidence about this class, not a clean bill for everything the branch carried.

## The cheap mechanical move

Open the draft PR on the first commit of any branch you expect to live more than a
day. The environment class is then measured continuously, by the only instrument
that can measure it, at the point where a single line is the whole diff.
