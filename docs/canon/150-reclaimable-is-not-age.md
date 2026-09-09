# 150 — RECLAIMABLE IS NOT AGE, AND THE TRIGGER FIRED EXACTLY WHEN ITS FIX COULD NOT WORK

**Measured 2026-09-09, on the VPS, with the disk at 95% and a task blocked behind it.**

The pre-flight skill's Check 2 carried this auto-fix:

> **Build Cache reclaimable > 30 GB** → `docker builder prune -af --filter "until=72h"`

It ran. It returned **`Total: 0B`**. Re-run at `--filter "until=24h"`: **`Total: 0B`** again.

Meanwhile the instruments it was reacting to said:

| instrument | reading |
|---|---|
| `docker system df` | Build Cache **46.5 GB**, **29.19 GB reclaimable** |
| `docker buildx du` | `Shared: 17.31GB` · `Private: 29.19GB` · **`Reclaimable: 46.5GB`** |

**Both numbers were correct. The prune was correct. They are about different things.**

`Reclaimable` is a statement about **usage** — cache not pinned by a running
build. `until=` is a filter on **LAST USED**. `docker system df -v` settles it:
every record in the 46.5 GB cache read `LAST USED 7 hours ago`, because the most
recent image build had touched all of it.

> **A SINGLE BUILD INSIDE THE WINDOW REFRESHES `LAST USED` ACROSS THE WHOLE
> CACHE.** So an age filter can never match a cache whose reclaimable figure is
> large — and "reclaimable is large" is the trigger's own firing condition.
> **The fix was unreachable precisely when it was called for.**

The unfiltered `docker builder prune -af` reclaimed all 46.5 GB and took the
disk from 89% to 81%.

## WHY IT SURVIVED — it is the WATCHED-SET failure, one layer up

This house already names two shapes: the broken instrument, and the right
question asked of the wrong universe. **This is the second**, and it wore the
costume of a third: *the correct command, correctly parameterised, against a set
that cannot contain what you are looking for.*

Nothing errors. `Total: 0B` is a truthful answer. A session that runs the
sanctioned fix, reads `0B`, and concludes *"nothing to reclaim"* has been told
the truth and drawn the false conclusion — and the report it writes will say the
auto-fix ran, which is also true.

⚠️ **AND THE CONSERVATISM WAS THE HAZARD, NOT THE SAFETY.** The `until=72h`
window reads as prudence — *don't eat cache a recent build might still want*.
On a box that builds daily it is not prudence, it is a guarantee of no-op.
**A guard calibrated so tightly that it never fires is indistinguishable from an
absent one, and it costs more, because its presence answers the question.**

## AND THE SECOND HALF: THE OTHER LEVER WAS ALSO AT ZERO, FOR A GOOD REASON

`prune-rollback-tags.sh` (ruling #137's sanctioned path) reported
**`57 dated tags = 57 kept/held + 0 deletable`** — 31 of 45 deploys past the
keep-list, every one `⏸ HELD, a container references this image`. That refusal
was **correct** and must not be loosened.

So both documented reclaims read zero, and the honest conclusion — *the docker
levers are exhausted, look elsewhere* — was **wrong about one of them**.

> **BUILD CACHE IS NOT A ROLLBACK ARTIFACT.** Ruling #137 protects
> `*:pre-<sha>-<date>` **images** — the only thing that makes a bad deploy
> reversible. It says nothing about build cache, which is regenerable and whose
> only loss is the next build's speed. **Conflating the two is what left this
> box at 95% with both sanctioned levers reporting zero.**

## THE GENERAL SHAPE

**When a trigger and its remedy are phrased in different vocabularies, check
that they range over the same set before trusting a zero.** *Reclaimable* /
*unused* / *dangling* / *orphaned* / *stale* / *older than* are five different
predicates that all read like "not needed any more", and a cleanup tool will
happily accept a filter that its own trigger condition excludes.

**The test is one line:** name an input the fix would act on *while the trigger
is firing*. Here there is none, and the whole defect is visible in that sentence.

**Fixed** by dropping the filter from the trigger, with the measurement recorded
beside it so the conservatism is not reinstated by someone reasoning from first
principles about recent builds.
