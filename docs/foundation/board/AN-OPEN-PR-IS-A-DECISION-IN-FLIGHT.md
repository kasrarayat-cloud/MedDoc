# ⚠️ "HAS THIS BEEN DECIDED?" IS NOT ANSWERED BY THE LEDGER ALONE

**Filed 2026-09-06, from building a fully-proved fix that was WRONG.**

## WHAT HAPPENED

Preparing the 53-control transfer, I measured a real defect: `encounter-facts`
emits `ros.<system>`, the mapping proposer offers the model `'ros.<system>'` one
line above `'exam.<system>'`, and only `exam.*` was registered — so every ROS
proposal was silently nulled, for every doctor, and the six per-clause ROS
controls could never certify.

I followed the prescribed check — `grep` the ledger head **and** the archives
for a prior decision — and found none. So I built the fix: a one-line registry
pattern, a gate driving the real emitter, **three mutation proofs each asserting
its own application, 6066 tests passing, `tsc` clean.** Opened as PR #1014 with
its §2.5 row.

**PR #985 — ruling #179, open, ten commits ahead of `main` — had already found
it, with the same reasoning including the same asymmetry, and fixed it
correctly.**

## ⚠️ AND MINE WAS NOT A DUPLICATE. IT WAS THE OPPOSITE ANSWER.

| | #1014 (mine) | **#985 / #179 (ruled)** |
|---|---|---|
| pattern | `/^ros\.[a-z0-9_]+$/` two-part | `/^ros\.[a-z0-9_]+\.[a-z0-9_]+$/` three-part |
| emitter | untouched | `ros.<system>.<symptom>` |
| `ros.gastrointestinal` | registered | **asserted FALSE** |

#985's gate asserts `isRegisteredConcept('ros.gastrointestinal') === false`.
**Mine makes it true, so merging mine would have redded a gate on an open PR.**

And the two-part form is *the very bug #179 exists to fix*: I had already
measured that the owner's six ROS controls are **symptom clusters, not
systems**, so five collapse onto one concept and become indistinguishable.
#985's comment states the consequence: *"the checkbox arm ticked all of them
from one fact, and a second affirmed symptom conflicted the export."*

> **I found the right problem and built the wrong answer, with every proof green.**

## THE TWO LESSONS

**1 · AN OPEN PR IS A DECISION IN FLIGHT, AND A LEDGER GREP CANNOT SEE IT.**
#179 has **no row in `RULINGS.md`** — its record lives in an unmerged PR. The
rediscovery rule points at the ledger; the ledger is necessarily behind. So the
check gains one line:

    gh pr list --state open --search '<the thing>'    # decisions in flight

**2 · GREEN ARMS DO NOT AUDIT THE PREMISE THEY WERE WRITTEN UNDER.** Every proof
I ran was sound and every one measured *my* emitter. #985 **changes the
emitter**, so my gate would have stayed green while being about a world that was
being replaced. Mutation proofs test whether a fix is load-bearing; they cannot
tell you the fix is the wrong fix.

## WHAT SURVIVES

`gate-emitted-concepts-are-registered.test.ts` is **general** where #985's is
ROS-specific — it drives `projectEncounterFacts` over a maximal snapshot and
asserts every family the emitter can produce is registered, reconciling produced
families against the ones the source can emit. **Filed as a follow-up to #985**,
to be rebased onto the three-part emitter. Kept on
`feat/ros-concept-registration`, which is NOT deleted for that reason. Nothing
else from that branch reaches `main`.
