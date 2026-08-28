# RETROSPECTIVE JUDGEMENT — F12-e, inside the deploy of `eec8685b`

⚠️ **THIS IS A RETROSPECTIVE JUDGEMENT. The gate was overtaken, not overridden.**

| | |
|---|---|
| **deploy began** | `2026-08-27T20:00:03Z` |
| **judged** | `2026-08-28T05:14:13Z` |
| **latency, deploy → judgement** | **554 minutes (~9h 14m)** |
| **declaration** | `docs/foundation/deploys/20260827-b439dcbb.md`, committed `2026-08-27T18:31:18Z` |
| **provenance** | the declaration's commit **provably precedes** the act by 1h28m45s, so no row here could have been tuned to an outcome |
| **production image** | `32a43656` — the id the original judgement records, **unchanged since** |

## WHY THIS DOCUMENT EXISTS

F12-e was **merged, cited 4 of 4, and HELD** — its deploy is a supervised act.
It reached production anyway, as an ancestor of the deployed commit: the F8
deploy shipped `main`, and `main` contained it.

**OVERTAKEN, NOT OVERRIDDEN.** Nobody bypassed the hold. The hold was attached to
a CHANGE, and a deploy ships a TREE, so a later act carried the change past its
own gate without either party doing anything wrong.

## WHAT THE DECLARATION ACTUALLY SAID ABOUT F12-e

⚠️ **ONE ROW, AND IT IS NOT A BEHAVIOUR ROW.** An earlier account of this said
*"not one of the 18 rows could have detected an F12-e regression."* That was too
strong and is corrected here: the declaration's LATENCY table carries exactly one
F12-e row.

| change | takes effect | retroactive |
|---|---|---|
| F12-e E/M freeze (`emApplies` alone) | next **sign** | **NONE — FORWARD-ONLY**, ruling #155 |

So F12-e had **a declared retro-effect and no declared behaviour**. Both halves
are judged below; the behaviour rows are reconstructed from F12-e's own claim
(ruling #152) and are marked as such.

## THE DECLARED ROW — 1 of 1

| quantity | declared | measured | |
|---|---|---|---|
| pre-deploy signed records mutated after the act | **NONE** (forward-only) | **0** | ✅ |

Measured directly: `signedAt < act AND updatedAt >= act` → **0 rows**. This is the
strongest available form of the claim — not "the counts still look right", but
"no record signed before the act has been written since".

## RECONSTRUCTED BEHAVIOUR ROWS — F12-e's own claim, and BOTH arms fired

F12-e's claim: the freeze is gated on `emApplies` **alone**; `emBlob &&` was the
defect. **2 visits were signed after the act**, and they exercise both arms —
which is why this is evidence and not a single-sided coincidence.

| visit | specialty | `emApplies` | signedCode | verdict |
|---|---|---|---|---|
| `cmtc03oot000t0…` | gastroenterology | **true** | **99214** frozen | ✅ froze when it applies |
| `cmsttnpph001a0…` | gastroenterology | **false** (by NOTE SHAPE) | **absent** | ✅ did NOT freeze when it does not apply |

⚠️ **THE SECOND ROW IS THE DISCRIMINATING ONE, AND IT LOOKED LIKE A REGRESSION.**
A gastroenterology visit signed after the fix, carrying `emScoredCode` 99215 and
no `signedCode`, is the exact silhouette of the bug F12-e removed. It is not:
`check-em-note-shape-artifacts.sh` lists that id under **verdict FALSE, axis =
note-shape**, so `emApplies` is false and refusing to freeze is correct. Its
residual E/M state is **F12-g's** class, which is separately tracked.

**Had this been judged at deploy time, that row would have had to be resolved
then — which is the argument for the structural fix, not against the deploy.**

## STANDING CHECKS — unmoved

| check | at judgement | now | |
|---|---|---|---|
| `check-em-note-shape-artifacts.sh` | 🔴 15 note-shape / 0 specialty | 🔴 **15 / 0** | ✅ unmoved |
| partition reconciliation | 52 == 52 | **52 == 52** | ✅ |

## ⚠️ ONE NUMBER THAT DOES NOT RECONCILE — RECORDED, NOT EXPLAINED AWAY

Ruling **#155** names **ten** signed records with absent E/M. Measured now: **11**
— all signed **before** the act (latest `2026-08-21`), **zero** after.

**The deploy did not move this population**, so it is not a finding about this
act. It is a **PREDICATE difference** to reconcile: this document counted
`signedAt IS NOT NULL AND cptCodes->'em' IS ABSENT`, and #155's ten may have been
counted through a narrower predicate (E/M-eligible only). *A census is only as
authoritative as its predicate's fidelity to the shipped function* — so the
number is reported with its predicate attached rather than silently matched to
the ruling. **It is carried into #155(b)'s annotation work**, which is already
queued as its own supervised act.

## VERDICT

**1 declared row, 1 matched. 2 reconstructed behaviour rows, 2 matched, both arms
exercised. No unnamed movement.**

⚠️ **WHAT THIS RECOVERS AND WHAT IT DOES NOT.** The declaration's commit precedes
the rows, so the EVIDENCE is real and could not have been tuned. What was lost is
the **GATE** — the chance to refuse the deploy, or to resolve the note-shape row
before it shipped rather than 9 hours after. **Saying which half you
have is the discipline; this document has the evidence and not the gate.**
