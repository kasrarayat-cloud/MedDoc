# F20 (swap) — MEASURED, and its premise no longer holds for this lane

**2026-09-05. Owner-assigned at a quiet window. NOT EXECUTED — the measurement
is why, and it is filed rather than acted on.**

`RELAY.md` F20 reads: *"Swap pinned at 4.0Gi with ~20 GB RAM free; historical
pages never faulted back."* Remedy: `swapoff -a && swapon -a` in a quiet window.
Owner-approved.

**The first half is still exactly true.** Swap is **4091 of 4095 MB used, 4 MB
free**, with **22.2 GB RAM available** and no OOM kills in 24h.

## But whose pages are they?

| holder | swap |
|---|---|
| `next-server` — HOST processes (v16.2.6 / v16.2.7 / v15.5.18) | **1475 MB** |
| unattributed `python` sessions | **1358 MB** |
| `openclaw` — explicitly out of scope per the preflight skill | 260 MB |
| unattributed `node` | 216 MB |
| `docker-proxy` / `npm` / `meilisearch` / `claude` | ~278 MB |
| **every QuillMD container combined** | **~19 MB** |

Per container, summed over **all** processes in each cgroup:
`transcribe-md` **0 MB** · `transcribe-md-worker` **0 MB** · `postgres` 11 MB ·
`marketing` 8 MB.

⚠️ **THE FIRST MEASUREMENT I TOOK WAS WRONG IN THE REASSURING DIRECTION, AND
ONLY THE SECOND IS QUOTED ABOVE.** I read `VmSwap` from each container's
`.State.Pid` — the container's init — and got near-zero. That is true and
almost meaningless: the work happens in CHILD processes. The number only became
evidence when it was summed across the whole cgroup. It happens to agree; it
was not entitled to.

## Why it is not being executed

1. **The beneficiary is not this lane.** QuillMD production holds **0.5%** of
   the swap in use. The app and worker hold **zero** — they were recreated an
   hour ago by the `dcc8cabf` deploy, which is itself the cleanest possible
   demonstration that a restart is what clears a process's swap.
2. **`swapoff -a` is HOST-WIDE.** It forces ~4 GB of pages belonging to
   `voiceassistmain`, `openclaw` and other sessions back into RAM. Those are
   co-tenants. This programme's standing rule is *never touch co-tenant vhosts*;
   the reasoning does not stop at vhosts, and a host-wide memory operation is a
   larger reach than a vhost edit.
3. **It is not a quiet window.** `Runner.Listener` processes are live ON THIS
   BOX, five of my own PRs are gating, and `voiceassistmain` is running
   Playwright chrome at ~46% CPU. F20's own condition is not met.

## What the swap pressure DID explain, which stands

It is the measured cause of background pollers being reaped during this
session — three watchers killed mid-watch, each of which read at the time like
an unexplained harness quirk.

> **A FULL SWAP IS NOT A CAPACITY PROBLEM, IT IS AN EVIDENCE PROBLEM.** It does
> not stop the work; it silently selects which of your processes survive. A
> killed poller is indistinguishable from a finished one to whoever is reading
> the notification — which is how a watcher quietly stops being a control.

## What I recommend instead

- **Leave F20 open.** Its remedy is still correct for the BOX; it is simply not
  this lane's 19 MB to reclaim, and executing it spends a co-tenant's risk.
- **The durable fix for the symptom is not swapoff.** A watcher that matters
  should not be a process that can be reaped silently — it should exit on a
  condition and be re-armed, which is what this session moved to after the
  third kill.
- **If the box's swap is to be cleared, it wants the owner of the box**, at a
  window when neither tenant is mid-run — not a QuillMD session mid-batch.
