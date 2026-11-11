# 151 — A BUILDER THAT FAILS OPEN LEAVES AN ARTIFACT THAT LOOKS BUILT, AND THE REAPER REFUSED EXACTLY THAT ARTIFACT

**Measured 2026-09-09, provisioning eleven lens sandboxes for a refutation round.**

`make-lens-sandbox.sh` exists for one reason, recorded in its own header: on
2026-09-06 a five-lens pass was told in its prompt not to write, and then edited
the tree, committed twice, pushed a branch, opened three pull requests and
merged one. **The environment is the guard, because a prompt is not one.**

A parallel batch of eleven produced **two sandboxes that were checked out at the
right commit and NOT ARMED**:

    .lens-r307-capability  ce5a6182  pushurl=UNSET  hooks=hooks  env=NO
    .lens-a5-guard         ddabee40  pushurl=UNSET  hooks=hooks  env=NO

`remote.origin.pushurl` unset. `core.hooksPath` still pointing at the
repository's **real** hooks. No `.lens-env.sh`, so `gh` keeps its credentials.
**Every guard the file exists to install was absent, and the tree was sitting
there at the right commit looking finished.**

The script had exited non-zero. **The directory stayed.**

## WHY THAT IS WORSE THAN NO SANDBOX

`ls` shows it. `git -C` answers from it. A caller that tests `[ -d "$DIR" ]`
rather than `$?` — the obvious, correct-looking check — hands a lens agent a
tree it can commit and push out of.

> **THE GUARDS DID NOT FAIL. THEY WERE NEVER INSTALLED, AND NOTHING SAID SO.**

The structural cause, and it needs no race to explain it: the script had **zero
`trap`s**, and discarded `git worktree add`'s exit status
(`>/dev/null 2>&1`, no `||`). **Any** failure after the worktree exists leaves
the unarmed tree behind.

## THE COMPOUNDING HALF — THE REAPER REFUSED ITS OWN WRECKAGE

`reap-lens-sandbox.sh` opened with:

    [ -d "$DIR/.lens-hooks" ] || { echo "carries no .lens-hooks — refusing."; exit 1; }

**That refuses precisely the artifact a partial creation leaves.** The two
scripts composed into a deadlock: `make` could produce an unarmed sandbox, and
`reap` was guaranteed to refuse that one and only that one.

It was not hypothetical. `.lens-o2-door-offer` had been sitting in the shared
tree since an earlier session for exactly this reason.

⚠️ **AND `git worktree remove` DOES NOT CLOSE IT EITHER.** It removes *tracked*
files; an **ignored** artifact keeps the directory alive. That orphan held
exactly one file — `apps/transcribe-md/node_modules/.vite/vitest/…/results.json`,
32K, a cache a lens had written. The registration was already gone, so
`worktree remove` had nothing to act on, and the name-based guard refused the
manual path.

## ⚠️ A TRAP MET WHILE DIAGNOSING IT, AND I READ IT WRONG FIRST

`git -C <orphan directory> rev-parse --short HEAD` **answers**. It walks **up**
to the enclosing repository, so an orphan directory inside the repo reports the
**shared tree's** HEAD and reads exactly like a live worktree at that commit.
I recorded it as "a directory at `7445308b`" before checking; it has no `.git`
at all.

> **`git worktree list` is the authority for whether a directory is a worktree.
> `git -C` is not — it will answer about somebody else's repository without
> mentioning that it moved.**

## THE TRIGGER IS UNPROVEN, AND IS RECORDED AS UNPROVEN

A deliberate three-way concurrent reproduction, minutes later on the same box,
**did not reproduce it** — all three came out armed. A race sampled coarsely is
a race missed, so that is not a refutation; **but it is not a demonstration
either, and nothing here claims one.** The artifact was observed twice and
config-verified; the mechanism was not.

**That is why the fix does not chase the race.** It arms against the *shape*,
which is correct whatever the trigger turns out to be:

- the exit status of `worktree add` is checked;
- an `EXIT` trap tears down a partially-created sandbox — **no sandbox, never an
  unarmed one**;
- the script **asserts its own arming** before printing the path (pushurl,
  hooksPath, both hooks executable, `.lens-env.sh`), read back from git and the
  filesystem rather than assumed from the fact the lines above ran;
- the reaper reaps an unarmed or orphaned sandbox, **bounded** to a direct child
  of the shared tree.

Proved by four mutations, each turning exactly **one** arm red while the others
stayed green — trap removed → *"LEFT THE UNARMED SANDBOX"*; assertion disabled →
*"the builder RETURNED SUCCESS"*; refusal restored → *"the deadlock is back"*;
containment removed → *"removed a `.lens-*` dir OUTSIDE the shared tree"*.

## THE GENERAL SHAPE

**A provisioning script that can exit after creating its subject, without
unwinding it, does not fail closed — it fails OPEN, and the artifact it leaves
is the most convincing possible imitation of success.** The question to ask of
any builder is not *"does it work?"* but *"what does the half-built one look
like, and who can tell?"*

And the second half is the one that made this durable rather than transient:
**a cleanup tool whose safety check keys on a property the failure destroys
cannot clean up after that failure.** Guard on identity (this is one of mine,
in my tree), never on integrity (this one is intact) — integrity is exactly what
is missing in the case you need the tool for.
