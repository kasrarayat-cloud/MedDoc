# `$$` IN A TOOL SHELL IS A FRESH SUBSHELL — THE SESSION ID IS THE IDENTITY

**Standing 2026-09-07, amending ruling #206 (adopted as ruling #213, PR #1032).**

## THE DEFECT

Ruling #206 required a lens sandbox to carry a marker file naming **its owner
session id and pid**, so a reaper could refuse to remove a tree whose owner is
still alive — *alive-checked, never assumed*.

> ⚠️ **THE PID IS DEAD BEFORE THE MARKER FINISHES BEING WRITTEN.**

Each tool invocation runs in its own shell. `$$` expands to **that** shell,
which exits when the command returns. So a marker stamped `pid=$$` records a
process that has never outlived the act of recording it, and an aliveness check
against it returns **dead** — reliably, immediately, and for every marker ever
written.

## ⚠️ WHY IT IS WORSE THAN A COIN FLIP

The check does not fail randomly. **It fails in one direction, and it is the
direction that destroys somebody else's work**: a reaper asking *"is the owner
alive?"* is told *no*, and reaps a live tree.

And it fails **hardest when the owner is busiest**, because a session mid-pass
stamps its marker and then spends the next twenty minutes in other subshells —
never re-touching a pid that was already meaningless. **The guard is least
effective exactly when it matters most**, which is canon 121's shape: an
intermittent guard whose existence is what stopped anyone building the real one.

Two lens trees were destroyed mid-pass under #206's original form. Both lenses
noticed, rebuilt read-only trees with `git archive`, and recorded the
interruption in their provenance notes — **the agents behaved better than the
tooling**, which is the only reason those results were usable.

## THE RULE

> **THE SESSION ID IS THE IDENTITY. `$$` IS NOT AN IDENTITY, IT IS AN
> IMPLEMENTATION DETAIL OF THE CURRENT COMMAND.**

The marker carries the **session id** — the thing that actually spans the work —
**and the tree's start-time**, which is what makes a stale marker
distinguishable from a live one without asking the kernel about a pid.

And the refusal is an **OR**, because either half alone has a hole:

> **Refuse when the owner's marker is FRESH *OR* when ANY process holds the
> tree.**

- **marker-only** misses a live worker whose session stamped its marker long ago
- **process-only** misses a session that is simply between commands — which is
  most of the time

## THE GENERALISATION — AND IT IS NOT ABOUT `$$`

**Ask what your identifier is an identifier OF, and for how long it stays one.**
This programme has met the same shape repeatedly under different costumes:

| the identifier | what it is actually an identifier of |
|---|---|
| `$$` in a tool shell | the shell that has already exited |
| an abbreviated SHA to `gh run list --commit` | nothing — it returns `[]` for any short SHA |
| a 40-hex string not resolved against the object store | a *form*, not a commit that exists (canon 115) |
| `origin/<branch>` | a cached belief about the remote, not the remote |
| a display string used as a lookup key | whatever the display happens to say today (canon 120) |

In every case the instrument answers correctly about the wrong thing. **A probe
that names the wrong universe is not a broken probe, and it will not present as
one** — which is why the identity, not the reading, is what has to be checked.
