# The pointer is resolved outside the lock

**Round five, PR #1018. ⚠️ FILED AS CLINICAL-HARM AGAINST THIS DIFF, AND
REFUTED ON THAT FRAMING BY THE VERIFY STAGE. What survives is narrower, one
severity band lower, and belongs to `main` rather than to this branch.**

**This file is kept, not deleted, because the refutation is the useful part.**

---

## WHAT WAS CLAIMED, AND WHY IT WAS WRONG

The claim was: *"`FOR UPDATE` blocks the sign's CAS and prevents nothing"* —
that round four's fix made the door reliably win the lock and therefore
reliably freeze a manifest excluding the doctor's correction, trading a loud
failure for a silent one.

**Four independent refutations, each sufficient, all measured by the verifier
against its own throwaway database rather than by re-running mine:**

**1 · "Prevents nothing" is FALSE — arm 1 works exactly as the comment says.**

    sign  t=0  BEGIN SERIALIZABLE; UPDATE … status='SIGNED' …  -> UPDATE 1 (held 3s)
    door  t=1  BEGIN; SELECT "status","signedAt" … FOR UPDATE
               -> BLOCKED 1968.339 ms, returned status=SIGNED
               -> guarded write:  INSERT 0 0            ← REFUSED
    final:     v1 | SIGNED | override_rows = 0

**2 · The lock is a STRICT IMPROVEMENT, measured against `main`.** The shipped
option door and main's insert door have no transaction, no `FOR UPDATE` and no
status re-read — only a top-of-action status read. Same interleave:

    door  t=0  SELECT status -> READY
    sign  t=1  UPDATE … -> UPDATE 1; COMMIT
    door  t=2  INSERT … ON CONFLICT …  ->  INSERT 0 1   ← lands on a SIGNED visit
    final:     SIGNED | override_rows_on_SIGNED_visit = 1

**The branch refuses what main writes.** The finding argued the fix made things
worse; it makes them better, and the arm it dismissed is the arm the diff's own
gate asserts (`gate-review-defaults-door-executable.test.ts:341,349`).

**3 · ⚠️ THE DEMONSTRATION WAS UNFAITHFUL IN THE LOAD-BEARING PLACE.** The
harness held the door's transaction open for **4 seconds** between the
`FOR UPDATE` and the `INSERT`. **The real transaction is two statements.** Both
fills happen in `scaffoldDefaultAdmissible`, awaited at `:683` — *before*
`prisma.$transaction` at `:704`. So the "seconds wide" window the comment names
is the **pre-transaction** window the lock CLOSES; it is not the lock's hold
time. **The measured `2972.835 ms` block is a property of the harness, not of
the code.**

⚠️ **I had this fact and discarded it.** Reading the door I wrote *"the door's
`$transaction` only contains the `FOR UPDATE` + upsert — the two fills happen
BEFORE the transaction"*, and then: *"But that's the point: the door's tx being
short doesn't matter."* It mattered. It was the whole thing. **Noticing a fact
and then arguing past it is worse than missing it**, because the note in the
transcript reads afterwards as though it was accounted for.

**4 · Attribution.** `sign/route.ts`, `sign-freeze.ts` and `native-export.ts`
are **not in this PR's diff.** The race is pre-existing on `main`, and the live
option door opens it today with no lock at all.

**5 · Severity.** No ordering fabricates or removes clinical text. Ordering A
costs letterhead; ordering B pins the document the signer actually reviewed —
arguably the correct freeze semantics. **Not clinical harm.**

---

## WHAT ACTUALLY SURVIVES

**A documentation overclaim on this branch, plus a pre-existing latent race on
the sign path. LOW / capability-loss. Reachable in principle, never exercised.**

The comment at `set-template-control.ts:695-700` presents **both** arms as safe.
Arm 1 is verified safe. **Arm 2 is safe only for the property the comment is
about** — an insert landing on a SIGNED visit. It is not safe for the signed
record's *document*, because the sign's document decision is taken outside the
transaction the lock contends with, and before the wait:

| | |
|---|---|
| `sign/route.ts:945` | `resolveFrozenPointer` runs **outside** `signWrite`'s transaction and binds on `overridesSha256` |
| door commits **just before** that read | pointer `null` → `no_matching_manifest_at_signature` → `frozenFillManifestId: NULL` → `native-export.ts:63` serves **styled, permanently** |
| door commits **after** it | the signature pins the pre-override manifest while the override row exists — and the door returns `ok:true` and writes a `DEFAULT_INSERTED_BY_DOCTOR` audit row asserting the default reached the document |
| either way | `native-export.ts:144-155` short-circuits freshness with `isSigned ? {ok:true,'match'}`, and a signed visit has no panel and no Undo |

**The real defect in arm 2 is the door's `ok:true` and its audit row**, not the
freeze. A trail that asserts a default reached the document, when it did not, is
the part worth fixing.

**Reachability, measured in production:** one CERTIFIED active compiled version
qualifies (`18a7ae19…`, GI Consultation Note, **53/53 scaffolded**) — and it has
**0 visits**, and `template_twin_field_overrides` has **0 rows, ever**. The race
additionally needs a concurrent sign on the same visit inside a sub-second
window. Never exercised.

## ⚠️ AND ONE MEASUREMENT SURVIVES INTACT, AS A CAVEAT ON THE OBVIOUS FIX

The verifier's own recommended fix is *"resolve the pointer inside
`signWrite`"*. **That alone does not work, and this is independent of the
window's width** — it is a property of Postgres SSI, not of the harness.

`packages/db/prisma/proofs/pointer-outside-lock-ssi-arms.sh`, three arms, with a
positive control because *"no 40001"* and *"SSI is off"* are the same output:

| arm | the door's isolation | the sign | final state |
|---|---|---|---|
| **control** | a genuine two-way cycle | **40001** | SSI is live; the instrument works |
| **A** | `BEGIN;` — READ COMMITTED, **as the door is today** | **committed** | `status=SIGNED  overrides=1` |
| **B** | `BEGIN ISOLATION LEVEL SERIALIZABLE;` | **40001 — refused** | `status=READY  overrides=1` |

SSI aborts on a **cycle**, and a cycle needs an edge each way. The sign reads the
override predicate the door writes, so `sign --rw--> door` exists. The door reads
the visit row the sign writes — but READ COMMITTED takes no predicate lock, so
**the return edge is never recorded.** One edge is not a cycle.

> **You cannot buy serializability for a PAIR by upgrading only the side you
> happen to be editing.**

So if the sign-path item is ever taken up, moving the read inside `signWrite` is
**necessary and not sufficient**: every door into `template_twin_field_overrides`
must be SERIALIZABLE too, or the predicate must go into the CAS instead — the
latter being the only form that cannot be defeated by somebody else's `BEGIN`.

## THE RESIDUE, AS ACTIONS

1. **On this branch:** amend the comment at `set-template-control.ts:695-700` so
   it does not present arm 2 as unconditionally safe. The lock protects the
   visit's SIGNED **status**, not the frozen **pointer**.
2. **Against `main`, separately:** file the pointer-outside-the-transaction race
   on the sign path, with the SSI caveat above attached so the obvious fix is not
   attempted alone.

## WHAT THIS COST, AND THE LESSON WORTH KEEPING

Three corrections on one finding: the evidence was **another agent's**, taken
from a shared scratchpad because both copies read `2972.835 ms`; the **framing**
was wrong because a 4-second hold was invented by the harness and not present in
the code; and the **severity and attribution** were both a band too high.

> **A window you had to hold open yourself is not a window the code has.**

The `FOR UPDATE` was attacked for what it does not do, when what it does do —
refusing an insert onto a signed visit, which `main` still permits — was
measurable in the same harness by running the other arm.
