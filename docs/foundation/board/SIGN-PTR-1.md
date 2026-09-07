# SIGN-PTR-1 — the frozen pointer is resolved outside the transaction that guards it

**Filed by ruling #235, 2026-09-07. Clinical-path item against `main`.**
**NOT part of PR #1018** — see ATTRIBUTION.

| | |
|---|---|
| **status** | OPEN, filed, not scheduled |
| **class** | capability loss + a **false audit assertion** |
| **reachable** | in principle yes; **never exercised** |
| **lanes** | **Custom-file** owns `sign/route.ts` + `native-export.ts`; **Design/Admin** owns the option door |
| **ships** | as a **PAIRED** change, both halves in one composed deploy |

## THE HARM, NAMED PRECISELY

It is **not** the freeze. Ruling #235 is explicit:

> **The door returns `ok:true` and writes a `DEFAULT_INSERTED_BY_DOCTOR` audit
> row asserting a default reached a document it did not reach.**

**A trail that asserts a clinical act which did not occur is worse than a
missing trail, because it is evidence pointing the wrong way.** The freeze
itself is defensible in one ordering — pinning the document the signer actually
reviewed is arguably correct semantics. The audit row is not defensible in
either.

## THE MECHANISM

The sign path decides **which document it freezes** outside the transaction that
any lock contends with, and before any wait:

| # | where | what |
|---|---|---|
| 1 | `sign/route.ts:945` | `await resolveFrozenPointer(...)` — reads the override set. **Outside `signWrite`.** |
| 2 | `sign/route.ts:775` | `signWrite = (frozenId) => prisma.$transaction(...)` — the pointer arrives as an **argument**, already decided |
| 3 | `sign/route.ts:851-866` | the CAS: `where { id, practiceId, status: READY, soapVersion }`. An override insert moves **none** of them |
| 4 | `sign/route.ts:882` | `frozenFillManifestId: frozenId` — step 1's answer, written at step 3's time |
| 5 | `native-export.ts:144-161` | `isSigned ? [] : …` and `isSigned ? {ok:true,'match'} : …` — the override half of the freshness check is **off for signed visits, deliberately** |

Step 5's stated premise is *"the pair was frozen AT the signature, under the CAS
that guarantees `signedSoap` is the text the manifest was bound to."* **The CAS
guarantees the NOTE. It guarantees nothing about the override set.**

`resolveFrozenPointer` is *correct for the state it saw* — `sign-freeze.ts:245`
binds on **both** `noteSha256` and `overridesSha256`, precisely so a manifest
filled before a correction cannot be pinned. It reads that state before the
correction commits, and nothing re-asks.

**Two orderings, by which side of step 1 the door's COMMIT lands on:**

| ordering | door commits… | pointer | outcome |
|---|---|---|---|
| **A** | **before** the read | `null` (the override hash no longer matches) | `no_matching_manifest_at_signature` → `frozenFillManifestId: NULL` → `native-export.ts:63` serves **styled, permanently**. The signer loses their letterhead because somebody clicked Insert. |
| **B** | **after** it, before the CAS | the pre-override manifest | pinned to a document without the correction, while the door returned `ok:true` and wrote the audit row |

⚠️ **ORDERING A IS THE ONE `resolveFrozenPointer` EXISTS TO PREVENT, FIRING AS
DESIGNED.** *"No matching manifest"* and *"a correction landed one millisecond
ago"* are the same return value.

> **A function whose honest answer and whose harmful answer are the same value
> cannot be fixed by its callers.**

## THE FIX IS PAIRED — NEITHER HALF SHIPS ALONE

1. **Resolve the frozen pointer INSIDE `signWrite`** — so the override read
   becomes a tracked read at all. **Necessary. Not sufficient.**
2. **AND make the option door's transaction SERIALIZABLE.**

**Why both, measured** — `packages/db/prisma/proofs/pointer-outside-lock-ssi-arms.sh`,
with a positive control because *"no 40001"* and *"SSI is off"* are the same
output:

| arm | the door's isolation | the sign | final state |
|---|---|---|---|
| **control** | a genuine two-way cycle | **40001** | SSI is live; the instrument works |
| **A** | READ COMMITTED — **as the door is today** | **committed** | `status=SIGNED  overrides=1` |
| **B** | SERIALIZABLE | **40001 — refused** | `status=READY  overrides=1` |

SSI aborts on a **cycle**, and a cycle needs an edge each way. The sign reads the
override predicate the door writes, so `sign --rw--> door` exists. The door reads
the visit row the sign writes — but **READ COMMITTED takes no predicate lock, so
the return edge is never recorded.** One edge is not a cycle.

> **You cannot buy serializability for a PAIR by upgrading only the side you
> happen to be editing.**

**ARM B's outcome is the desired one and it needs no new machinery:** the sign
takes 40001, and the route's existing three-attempt retry (`sign/route.ts:964-990`)
re-runs the whole transaction — which re-resolves the pointer against the
committed override.

**The alternative, if the isolation-level route is rejected:** put the override
set in the CAS, so a correction landing in the window makes `updateMany` return
`count: 0` and the existing race-loser path answers precisely. Wider, and the
only form that **cannot be defeated by somebody else's `BEGIN`** — the
isolation-level fix is correct only while every future writer of that table
chooses the right level, and nothing asserts that.

⚠️ **AND ORDERING A NEEDS A THIRD RETURN VALUE, WHICH NEITHER FIX SUPPLIES.**
`resolveFrozenPointer` returns `string | null`, and two different situations
produce `null`:

| why null | the right answer |
|---|---|
| there genuinely is no VERIFIED manifest for this note | styled, forever — correct as built |
| a manifest exists and its **override hash moved a moment ago** | **stale, re-fill** — never "styled forever" |

Distinguish `no_manifest_for_this_note` from
`manifest_exists_but_overrides_moved`, and let only the first stamp NULL.

## REPRODUCTION

The harness interleave is kept with this item — **with its correction attached**:

    door  BEGIN; SELECT "status","signedAt" … FOR UPDATE;  [hold];  INSERT override;  COMMIT
    sign  SELECT count(*) FROM overrides -> 0      ← outside BEGIN, decides the pointer
          BEGIN SERIALIZABLE; UPDATE … SET status='SIGNED', "frozenFillManifestId"='m-OLD'
                WHERE id=… AND status='READY' AND "soapVersion"=7;   -> UPDATE 1
          COMMIT

⚠️ **THE HOLD IS THE HARNESS'S, NOT THE CODE'S.** The original filing held the
door's transaction open for **4 seconds**; the real transaction is **two
statements** — both fills are awaited before `prisma.$transaction` opens. **A
window you had to hold open yourself is not a window the code has.** The window
here is real and **narrow**; the harness widened it to make it visible. Any
future reproduction must state the same thing.

## ATTRIBUTION — WHY THIS IS NOT #1018

`git diff --name-only origin/main...feat/review-defaults-omit-door` contains
**none** of `sign/route.ts`, `sign-freeze.ts`, `native-export.ts`.

And #1018's `FOR UPDATE` is a **strict improvement** on the surrounding
behaviour, measured: against `main`'s shape — no transaction, no lock, no status
re-read — the same interleave writes `INSERT 0 1`, landing an override row on an
already-SIGNED visit. **The branch refuses what main writes.**

Folding this item into #1018 would misattribute a main-line defect to the branch
that improves it, and hold a good change hostage to an unrelated one.

## REACHABILITY — STATED SO THE PRIORITY IS HONEST

Measured read-only against production:

- exactly **one** qualifying compiled version — `18a7ae19…`, GI Consultation
  Note, CERTIFIED, template `active`, **53/53 fields scaffolded** — and it has
  **0 visits**;
- `template_twin_field_overrides`: **0 rows, ever**;
- the race additionally needs a concurrent sign on the same visit inside a
  sub-second window.

**Real, filed, and not an emergency.** The population that makes it reachable
arrived on 2026-09-07; it has not yet been used.
