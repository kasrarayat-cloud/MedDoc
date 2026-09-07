# The pointer is resolved outside the lock

**Found 2026-09-07, on PR #1018's round-four fix, by attacking the fix's own
claim rather than the code it replaced. Clinical-harm class.**

## THE CLAIM UNDER ATTACK

`set-template-control.ts:687-703` states it, and the statement is the reason
the `FOR UPDATE` was added:

> *"`POST /api/visits/[id]/sign` is the sole SIGNED-writer and it updates this
> visit row, so `FOR UPDATE` here makes the two mutually exclusive: either the
> sign commits first and the re-read below sees SIGNED, or this transaction
> holds the row and the sign waits."*

Both halves are TRUE. **And "the sign waits" is not "the sign is correct."**

## WHAT THE SIGN DECIDED BEFORE IT WAITED

The sign path resolves *which document this signature freezes* **outside its own
transaction**, and the compare-and-swap that commits the signature cannot see an
override:

| # | where | what |
|---|---|---|
| 1 | `sign/route.ts:945` | `await resolveFrozenPointer(...)` — reads the override set. **Not inside `signWrite`.** |
| 2 | `sign/route.ts:775` | `signWrite = (frozenId) => prisma.$transaction(...)` — the pointer arrives as an **argument**, already decided |
| 3 | `sign/route.ts:851-866` | the CAS: `where { id, practiceId, status: READY, soapVersion }`. An override insert moves **none** of them |
| 4 | `sign/route.ts:882` | `frozenFillManifestId: frozenId` — step 1's answer, written at step 3's time |

`resolveFrozenPointer` (`sign-freeze.ts:245`) is *correct for the state it saw*.
It binds on **both** halves of the identity — `noteSha256` AND
`overridesSha256` — exactly so that "a manifest filled before a correction"
cannot be pinned. It just reads that state before the correction commits, and
nothing re-asks.

⚠️ **The freeze's own re-read does not save it either.** `sign-freeze.ts:210`
re-reads the override set *after* the refill, precisely so "a correction that
landed during the re-fill must not pass on the strength of a list captured
before it existed". That read is also before step 1, hence also before the CAS.
**Both guarded reads sit on the same side of the window.**

## AND THE EXPORT IS FORBIDDEN FROM NOTICING

`native-export.ts:144-161` switches the override half of the freshness check
**off for a signed visit, deliberately**:

```ts
const currentOverrides = isSigned ? [] : await prisma.templateTwinFieldOverride.findMany(…)
const freshness       = isSigned ? ({ ok: true, reason: 'match' } as const)
                                 : manifestMatchesDocument(…)
```

on the stated premise:

> *"A signed record's pair was frozen AT the signature, under the CAS that
> guarantees `signedSoap` is the text the manifest was bound to."*

**The CAS guarantees the NOTE. It guarantees nothing about the override set.**
So the one gate that could catch this is the one gate told not to look.

## CONCRETE INPUT → WRONG OUTPUT

Visit `v1`, practice `p1`, `status=READY`, `soapVersion=7`, certified twin, one
VERIFIED manifest `m-OLD` whose `overridesSha256` is the identity of `[]`.

| t | doctor's tab A — the panel | the sign |
|---|---|---|
| 0 | `setTemplateControlAction(v1,'f-42','Bilateral')`; two full fills run (seconds) | |
| 1 | `BEGIN`; `SELECT … FOR UPDATE` on `v1`; sees READY | |
| 2 | | `POST /sign`. `resolveFrozenPointer` reads overrides → **0 rows** → returns **`m-OLD`** |
| 3 | | `signWrite('m-OLD')`; the CAS **blocks** on tab A's row lock |
| 4 | upsert the override; `COMMIT`; returns **`{ok:true, label:'Laterality', value:'Bilateral'}`** | |
| 5 | | CAS unblocks — `status` still READY, `soapVersion` still 7 → **matches**. Commits `SIGNED`, `frozenFillManifestId='m-OLD'` |

**Output.** The doctor was told the correction was applied. Every download of
the signed record resolves by pointer to `m-OLD` — the document **without**
`Bilateral` — and `native-export.ts` skips the override freshness check because
the visit is signed. **Permanently, with nothing on any surface saying so.**

## MEASURED

`psql`, two sessions, the two statements verbatim from the source shapes:

```
DOOR   SELECT "status","signedAt" … FOR UPDATE   →  READY | (null)
DOOR   INSERT 0 1                                    (t ≈ 4.0s)
DOOR   COMMIT

SIGN   SELECT count(*) … template_twin_field_overrides  →  0     ← outside BEGIN
SIGN   BEGIN ISOLATION LEVEL SERIALIZABLE
SIGN   UPDATE transcribe_visits SET status='SIGNED', "frozenFillManifestId"='m-OLD'
        WHERE id='v1' AND status='READY' AND "soapVersion"=7
       UPDATE 1        Time: 2972.835 ms          ← blocked on the door, then MATCHED
SIGN   COMMIT
```

The `2972.835 ms` is the finding. The sign **did** wait for the door — the lock
worked exactly as designed — and then committed a decision made before the wait,
against a row whose override had landed in the meantime. `UPDATE 1`, not
`UPDATE 0`: the CAS had nothing to catch it with.

⚠️ **PROVENANCE, STATED — AND ONE ATTRIBUTION I GOT WRONG FIRST.**

The psql interleave above is **LENS 2's** measurement, not mine. I found
`door.sql` / `sign.out` in the session scratchpad, assumed they were my own
pre-break work, and was ready to file them as such; they carry
`2972.835 ms` and so did the lens's report, which is what made me check.
`grep` over the five lens transcripts named exactly one author. **A number
that matches to the microsecond is not a corroboration, it is the same
measurement twice** — and the whole value of an independent pass is lost the
moment its evidence is re-filed as the reader's own.

What is genuinely independent is the **source read**: the three-file chain and
every line number above were re-derived from the tree before the lens's report
was opened, which is the verification the pass is owed rather than a second
sighting. The SSI arms in the next section are mine.

**Not yet done:** driven end-to-end through the app. LENS 2 got closest —
`lens2-frozen-pointer-race.test.ts` drives the REAL `resolveFrozenPointer`
with prisma mocked to honour the `overridesSha256` predicate, 3 of 3.

## ⚠️ AND THE OTHER ORDERING IS WORSE — LENS 2's, WHICH I MISSED ENTIRELY

I looked at one side of the window. There are two, and they differ by which
side of `resolveFrozenPointer`'s read the door's COMMIT lands on:

| ordering | door commits… | pointer | what the record becomes |
|---|---|---|---|
| **A** | **before** the read | `wantedOverrides` no longer matches `m-OLD`'s stored empty-set hash → the `findFirst` matches nothing → **`null`** | `route.ts:950` stamps `no_matching_manifest_at_signature`; `signWrite(null)` writes `frozenFillManifestId: NULL`; `native-export.ts:63` returns null **forever**. **Signed STYLED, permanently** — the file's own words: *"a visit signed styled is styled FOREVER … there is no re-attestation path."* The signer loses their own letterhead because somebody else clicked Insert. |
| **B** | **after** the read, before the CAS | `m-OLD` | pinned to a document that does not contain the correction, while the door returned `ok:true` and wrote a `DEFAULT_INSERTED_BY_DOCTOR` audit row. `native-export.ts:144-155` never checks. **Undetectable, permanently.** |

**Ordering A is the one `resolveFrozenPointer` exists to prevent, firing as
designed and producing the permanent loss anyway** — because "no matching
manifest" is indistinguishable, at that line, from "a correction landed one
millisecond ago". The honest answer and the harmful answer are the same value.

## ⚠️ THE FIX MADE THIS BRANCH RELIABLE

This is the part that matters, and it is why the finding belongs to #1018
rather than to the sign path alone.

**Before** the `FOR UPDATE`, that interleaving had two outcomes. The sign's CAS
did not wait, so it could commit *before* the door's insert — and then the
insert landed on a SIGNED visit. That is round four's finding: an orphan
override, no panel, no Undo, permanent. **Loud, visible, and on the record.**

**After** the `FOR UPDATE`, the door is guaranteed to win the lock whenever it
holds it — so the override reliably exists at the moment the sign freezes a
manifest that excludes it. The loud failure was closed and a silent one was
opened underneath it.

> **A guard that makes the loser wait has not made the winner right.**

It is the shape the sign route already quotes at itself, one lane over:
*"an absent field is content the doctor did not see; a WRONG field is content
that says the opposite of the record being signed — and restoring a surface can
introduce the second while fixing the first."*

## ⚠️ THE OBVIOUS FIX DOES NOT FIX IT — MEASURED

The first thing I wrote here was *"move the pointer resolution inside
`signWrite`; the transaction is already SERIALIZABLE, so Postgres refuses the
interleaving with a 40001 the route already retries."* **That is wrong, and
only a measurement said so.**

`ssi_probe` on PG 16.13, three arms, the middle one carrying a positive control
because *"no 40001"* and *"SSI is not working"* are the same output:

| arm | the door's isolation | the sign | final state |
|---|---|---|---|
| **control** | — (a genuine two-way cycle) | **40001** | SSI is live in this database; the instrument works |
| **A** | `BEGIN;` — READ COMMITTED, **what the code does today** | **committed** | `status=SIGNED  overrides=1` |
| **B** | `BEGIN ISOLATION LEVEL SERIALIZABLE;` | **40001 — refused** | `status=READY  overrides=1` |

**ARM A is the finding, restated at full strength.** The proposed fix was
applied — the override read moved inside the sign's SERIALIZABLE transaction —
and the sign still committed, and the end state is still a SIGNED visit whose
frozen manifest excludes an override that exists. Moving the read bought
nothing.

**Why**, and it generalises well past this file: SSI aborts on a *cycle*, and a
cycle needs an edge in each direction. The sign reads the override predicate
that the door writes, so `sign --rw--> door` exists. The door reads the visit
row that the sign writes — but the door is READ COMMITTED, so **that read takes
no predicate lock and the return edge is never recorded.** One edge is not a
cycle. Postgres is behaving exactly as documented; serializable guarantees hold
between serializable transactions.

> **You cannot buy serializability for a PAIR by upgrading only the side you
> happen to be editing.** The door is the side nobody was editing, and it is
> the side that decides.

## WHAT WOULD CLOSE IT

Not decided here; the shapes, with what each costs. **(1) and (2) are one fix,
not two** — that is what ARM A cost me to learn.

1. **Move the pointer resolution INSIDE `signWrite`** *(necessary, not
   sufficient)* — so the override read becomes a tracked read at all.
2. **AND raise the door's `$transaction` at `set-template-control.ts:704` to
   SERIALIZABLE** *(the half that actually does the work)* — ARM B. The sign
   then takes 40001, and the route's existing three-attempt retry
   (`sign/route.ts:964-990`) re-runs the whole transaction, which re-resolves
   the pointer against the committed override. **Machinery that is already
   there and already proven, and the door's transaction is two statements
   long.** ⚠️ Both sides must be raised together; either alone is ARM A.
3. **Or put the override set in the CAS.** Bind the `updateMany` on an
   `overridesSha256`-equivalent so a correction landing in the window makes the
   CAS return `count: 0` and the existing race-loser path answers precisely.
   Isolation-level-independent, and the widest change — but it is the only one
   that does not depend on every future writer of that table choosing the right
   isolation level.
4. **Stop exempting signed visits at `native-export.ts:155`.** Cheapest, and it
   converts silent wrong content into a visible refusal — but it breaks the
   property that comment protects (a post-signature edit to `soapFinal` must not
   decline the frozen document), so it needs the override half split from the
   note half rather than the whole check re-enabled.

**(3) is the recommendation, with (1)+(2) as the smaller alternative.** (3) is
preferred precisely because ARM A showed the failure mode of the isolation-level
route: it is correct only while every door into that table stays SERIALIZABLE,
and nothing asserts that. A predicate in the CAS cannot be defeated by somebody
else's `BEGIN`.

### ⚠️ AND NONE OF (1)–(4) CLOSES ORDERING A

Every shape above is about ordering B — *which manifest gets pinned*. Ordering A
never reaches the CAS: it produces `pointer = null` **honestly**, and the harm is
what the route then does with a null.

`route.ts:950` reads null as *"this signature froze NO native document"* and
`native-export.ts:63` makes that permanent. But there are two ways to get a
null, and they want opposite answers:

| why null | the right answer |
|---|---|
| there genuinely is no VERIFIED manifest for this note | styled, forever — correct as built |
| a VERIFIED manifest exists for this note and its **override hash moved a moment ago** | **stale, re-fill** — never "styled forever" |

`resolveFrozenPointer` cannot tell the caller which, because it returns
`string | null` and both cases are `null`. **The fix for A is a third return
value**, not a lock and not an isolation level: distinguish
`no_manifest_for_this_note` from `manifest_exists_but_overrides_moved`, and let
only the first stamp NULL. The second is the case the retry loop at
`route.ts:964-990` was built for and is currently never handed.

> **A function whose honest answer and whose harmful answer are the same value
> cannot be fixed by its callers.**
