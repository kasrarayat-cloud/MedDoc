# A SURVIVAL CHECK MUST RUN IN THE TREE YOU DESTROYED IN

**Recorded 2026-09-02, from a self-inflicted incident during close-out.** The
operational sibling of [canon 52](52-a-destruction-list-is-a-claim.md) — that
entry says assert what must SURVIVE, and this one says the assertion is worthless
if it runs somewhere else.

## What happened

A scratch sweep ran `find … -name '*.docx' -o -name '*.pdf'` across four
directories under the session sandbox and shredded 90 generated artifacts. Four
of those directories were **git worktrees**, and the sweep took **27 tracked,
committed BLANK FIXTURES** with them — `sample-form.docx`,
`colon_blank_answers.pdf`, the adjudicated May audit PDF, every
`tests/e2e/fixtures/**` and `__fixtures__/**` entry.

That is exactly the allowlist `AGENTS.md` names, and exactly the outcome it warns
of in terms: *"a sweep that eats the blank fixtures breaks the twin work, which
is why they are named here as carefully as what must not survive."*

⚠️ **AND CANON 52's SURVIVAL ASSERTION WAS PERFORMED, AND PASSED.** Immediately
after the sweep:

    ── and the tracked fixture MUST survive (canon 52's other half) ──
      -rw-rw-r-- 52884  WM IOV Template.docx
      -rw-rw-r-- 52884  apps/transcribe-md/tests/e2e/fixtures/sample-form.docx

Both present. Both byte-correct. **Both in the feature worktree, which the sweep
never touched** — while the same filenames were being destroyed in the four
worktrees it did.

> **THE CHECK AND THE DESTRUCTION RAN IN DIFFERENT TREES, AND NOTHING IN EITHER
> OUTPUT SAID SO.** Two paths that read identically in a report are different
> files on disk.

## Why it slipped past a rule written to stop it

Canon 52 says *verify before executing, and afterwards assert what must SURVIVE,
not only what is gone.* Both halves were done. The defect is one level below the
rule: **the survival assertion inherited its working directory from the previous
command instead of from the sweep's own targets.** It is
[canon 87](87-a-ref-is-not-a-tree.md)'s failure in a new costume — a name
mistaken for the thing named — and
[canon 41](41-third-instance-2026-08-23-and-it-came-from-a-cd-in-an-earl.md)'s
`cd`-inherited-path hazard with a destructive verb attached.

**Severity, stated honestly:** every deleted file was TRACKED, so nothing was
unrecoverable — `git checkout --` restored all 27, byte-identical to `HEAD`,
verified by sha256. The shared tree and the feature branch were untouched. The
live hazard was never data loss; it was **a `git add -A` in a swept worktree
turning it into a commit that removes tracked fixtures.**

## The rule

> **Name the trees you are about to destroy in. Run the survival assertion in
> EACH of them, by absolute path. A check that passes in a tree you did not
> touch is not evidence about the ones you did.**

## ⚠️ AND THE MECHANICAL CURE, BECAUSE A HABIT WOULD NOT HAVE CAUGHT THIS

The sweep looked correct. It was scoped to the sandbox, it excluded nothing it
should have kept by name, and its assertion passed. **No amount of care at the
call site distinguishes a scratch `.docx` from a committed fixture with the same
extension** — only git can, and a path check cannot express it, because a
sandbox legitimately CONTAINS git worktrees.

So the reaper asks git, per target, and REFUSES anything tracked:

    git -C "$(dirname "$resolved")" ls-files --error-unmatch -- "$resolved"

Fail-closed: if the path is inside a repository and git claims it, it is not
scratch, whatever it is named and wherever it sits. Proved against the exact
files the sweep ate — both refused — with a positive control showing genuine
scratch is still reaped.
