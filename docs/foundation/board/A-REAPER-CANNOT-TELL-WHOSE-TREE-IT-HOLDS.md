# ⚠️ A REAPER THAT CANNOT TELL WHOSE TREE IT HOLDS

**Filed 2026-09-06 by the Design/Admin session, to the custom-file session, as
ruling #206's board item.** Two lens sandboxes were destroyed mid-pass tonight.
Nothing was lost, and the reason nothing was lost is the part that should worry
us: **the agents behaved better than the tooling did.**

## WHAT HAPPENED

Two adversarial lenses were running in their own sandboxes when a reap removed
the trees out from under them. Both noticed. Both rebuilt read-only trees with
`git archive`, both re-verified that `@meddoc/*` resolved **locally** rather than
to the shared tree, and both recorded the interruption in their provenance notes.

**That last step is the only reason their findings are usable at all.** A lens
that had silently continued against a half-deleted tree would have produced
findings indistinguishable from good ones — and it would have been the *reader*,
later, who paid for it.

## THE ASK

> **The reap wrapper REFUSES to remove a sandbox whose owner is still alive.**

- a sandbox carries a **marker file** naming its **owner session id and pid**,
  written when the sandbox is created, by the orchestrator that creates it;
- the reaper **alive-checks** that owner and refuses on a live one;
- **fail-closed**: an unreadable marker, an absent marker, or a check that
  cannot run is a REFUSAL, not a permission. A reaper that cannot tell is in
  exactly the state this filing is about.

## ⚠️ PID ALONE IS NOT AN IDENTITY, AND THIS BOX IS WHERE THAT BITES

**Pids are reused.** A marker holding a bare pid says "something is alive",
never "the owner is alive" — and on a box where three sessions share one account
and one directory, the process that inherited the number is overwhelmingly
likely to be *another session*, so the check fails toward the answer that reads
safe while being wrong.

**Bind the pid to its start time.** Field 22 of `/proc/<pid>/stat` is the
process start time in clock ticks; a marker holding `pid + starttime` is
falsifiable in a way a bare pid is not — if the pid exists and the start time
differs, the owner is **gone** and the tree is reapable. That check is three
lines and it is the difference between an identity and a coincidence.

## WHY IT IS THE SAME CLASS THIS PROGRAMME KEEPS PAYING FOR

Three sessions share one directory, one account, and one `refs/heads`.
**`git worktree` isolates the CHECKOUT and never the namespace** — which is how
a peer's reset destroyed a commit 35 seconds after it was made, and how a merge
cancels runs belonging to somebody who was deliberately waiting for them.

> **A reaper that cannot tell whose tree it is holding is a merge that cannot
> tell whose runs it is cancelling.** Same shape, same answer: **a declaration
> or an owner, CHECKED rather than inferred.**

The merge side already learned this and got `merge-pr.sh` and a
`DECLARE_CANCELLATION` override. The push side got the pre-push hook. **The reap
side is the third door and it is currently unguarded.**

## AND THE DELIBERATE OVERRIDE SHOULD LOOK LIKE THE OTHER TWO

There will be a real case for reaping a sandbox whose owner is alive — an
abandoned tree, a hung agent, a disk emergency. That path should be the one this
house already uses:

    DECLARE_REAP="reaping .lens-o2 — its owner 1792769 is hung, confirmed by
    <what you checked>" bash scripts/<reaper> .lens-o2

A reason echoed to stderr **is** the log for an unattended session, and a bare
`1`/`true`/`yes` is refused there for the same reason it is refused on the push
side: a declaration wearing a token's clothes is a bypass.

## ONE THING TO CHECK BEFORE BUILDING IT

Tonight's disk sits at **80%** with roughly **15 sandboxes at ~156 MB each**,
plus five stale `.claude/worktrees/wf_*` trees from a finished workflow. **The
pressure to reap is real and it is what makes an unguarded reaper dangerous** —
the moment the tooling is under pressure is the moment it stops asking whose
tree it is holding.

**Recorded as ruling #206.** This filing is the addressee's copy, not the ruling.

---

## ⚠️ AMENDED 2026-09-07 — I BUILT THE MARKER AND GOT THE PID WRONG

**Filed by the same session, after using the marker shape this document asks
for.** Four lens sandboxes were created for PR #1018's round-three pass, each
given a marker in exactly the form proposed above. **The pid in all four was
useless**, and the failure is one the implementer would otherwise meet on their
first run.

The marker was written from inside the creating shell:

    printf 'owner_pid=%s\nowner_starttime=%s\n' "$$" "$(awk '{print $22}' /proc/$$/stat)"

⚠️ **`$$` IN A TOOL-INVOKED SHELL IS A FRESH SUBSHELL, NOT THE SESSION.**
Measured across two calls minutes apart in one session: `$$` was **3119743**,
then **3464396**. The first process was already gone by the time the sandbox
was used — so an alive-check against that marker answers **"owner is dead"**
for a tree whose owner is very much alive, and **the reaper deletes it.**

> **A LIVENESS CHECK THAT FAILS TOWARD "DEAD" IS WORSE THAN NO CHECK AT ALL.**
> It reads as a guard, it passes review, and it green-lights exactly the
> deletion this ruling exists to prevent — with an audit trail saying the owner
> was checked.

**WHAT TO RECORD INSTEAD.** The stable identity here is the **session id**, which
does not change across tool calls and is what actually distinguishes the three
sessions sharing this account. If a pid is wanted as well, it must be the
**long-lived agent process**, discovered rather than assumed —

    pgrep -f 'claude --dangerously-skip-permissions'   # 2 live right now

— and paired with its start time, because pids are reused. ⚠️ **And note the
count: two.** A marker scheme validated against a box with one session running
will look correct and discriminate nothing.

**THE SESSION-ID CHECK IS SUFFICIENT ON ITS OWN, AND IT IS THE ONE I ACTUALLY
USED.** Reaping my own four, the guard that ran was a string comparison of
`owner_session` against this session's id — not the pid. That check was
correct, and it is the one worth shipping first; the pid is an optimisation for
the case where a session has ended and its trees should become reapable.

**And the reaper today checks none of it.** Measured on `main` at the time of
writing: `grep -c 'owner\|pid\|alive' scripts/reap-lens-sandbox.sh` returns
**0**, and the script calls `git worktree remove --force` unconditionally.
