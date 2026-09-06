# §2.5 PASSENGER DECLARATION — T4, the post-signature checkbox → action shift

**Written BEFORE the act**, at PR-open time on `2026-09-05`, while
`feat/t4-post-state` was still an open PR and **before the merge commit
existed**. Nothing below could be tuned to an outcome, because no outcome
exists yet.

Branch `feat/t4-post-state` · ruling **#188(4)** · RELAY **T4**.

> ⚠️ **THIS IS A PASSENGER DECLARATION, NOT A DEPLOYING ONE.** This session
> does not deploy. The change rides the next declared deploy as a **named
> passenger**, and the deploying session's own §2.5 governs the comparison.
> What this file supplies is the half a deploying session cannot reconstruct
> after the fact: what this particular change was expected to do, written down
> while the answer was still unknown.
>
> **A deploy that ships this without naming it has shipped an unjudged change**
> — the *overtaken, not overridden* hazard. Name it, or defer it by name.
>
> **The handoff is one copy.** On the deploy that carries it, this file goes
> verbatim to `docs/foundation/deploys/<YYYYMMDD>-<short-sha>.md` — the path
> `deploy-prod.sh` resolves — with only a header line naming the SHA the
> original could not know. It is filed under `docs/deploy-reports/`-adjacent
> **tracked** paths on purpose: `docs/deploy-logs/` is gitignored, and a
> verification written there looks committed and is invisible.

---

## WHAT SHIPS

The sign-and-deliver modal's **post-signature** state. Ruling #188(4) landed the
`DOCUMENT SIGNED` badge as skin and said the checkbox → action shift is its own
change. This is that change.

1. **Each destination row becomes a one-click action after signing.** Before:
   tick boxes, then press a submit. After: press the row. `mode` is
   `signOnSubmit ? 'checkbox' : 'action'` — the pre-sign state is untouched.
2. **No Cancel and no primary button in the post state** — there is nothing
   left to confirm.
3. **The delivery summary is gated to pre-sign only.** It named a *set* that
   the post state no longer submits.
4. **A blocked clipboard no longer reports "Delivered."**
   `applyBrowserSideDeliveries` reports browser-side failures by toast and does
   not throw; the row's success toast fired after it, so the doctor saw
   *"Copy blocked"* and then *"Delivered — Copy for Epic"*, affirmative last,
   with the clipboard still holding whatever it held before.
5. **A download says "Download started", not "Delivered."** `pdf`/`docx` fire an
   `<a download>` with no error channel. Saying *delivered* asserts something
   the code cannot see. The honest fix — fetch, check `res.ok`, download the
   blob — is filed as **F-T4-2**, not smuggled in here.
6. **Two clicks in one React batch deliver once.** The guard is a ref; the
   state read was a stale closure.

---

## WHICH PRODUCTION ROWS THIS TOUCHES: **ZERO**

Not "few". None — and by construction rather than by hope:

| | |
|---|---|
| migrations added | **0** |
| `schema.prisma` changed | **no** |
| API routes added or changed | **0** |
| server files changed | **0** |
| files changed | **3** — one component, one stylesheet, one test |

Every destination the post state can reach was already reachable from this
same modal on `main`: the `emailEnabled` group is **not** gated on
`signOnSubmit`, and `prepareDeliverOnly` — which hits
`/api/visits/[id]/export/{email,clipboard,pdf,docx}` — is pre-existing and
unchanged. **The change is how many clicks reach those routes, not which
routes exist.** Email goes from check-then-submit to one click; it was
never unavailable.

---

## ⚠️ THE ONE THING THIS CHANGES ON THE SIGNING PATH, AND IT IS A TYPE

`applyBrowserSideDeliveries` was widened from `Promise<void>` to
`Promise<Destination[]>` so the per-row action could see a failure it
previously only toasted. **The sign path also calls that function.**

**Claimed unchanged**, and here is why it is true rather than hoped: the sign
path calls it as a `void`-ed fire-and-forget with its own `.catch`, **after**
the outcome toast has already fired. A browser-side failure is structurally
unable to reach the signature.

⚠️ **AND THE FIRST GATE ARM WRITTEN FOR THIS CLAIM WAS AIMED AT THE WRONG
SHAPE.** It mutated the function to *rethrow* and redded nothing — correctly,
because a rethrow lands in that `.catch` by design. The refactor the widening
actually invites is *fold the reported failures into the outcome*, and that one
tells a doctor **"Signed — some destinations failed"** about a signature that
committed cleanly server-side. Re-aimed, the mutation reds exactly one arm with
exactly that string. **The arm is pinned to the property, not to my first guess
at it.**

---

## EXPECTED DELTA

**Nothing but the image ids.**

Rows the deploying session should carry, and what each must read:

| row | before | after |
|---|---|---|
| `transcribe_visits` total | *(baseline)* | **identical** |
| visits with `signedAt IS NOT NULL` | *(baseline)* | **identical** |
| patients | *(baseline)* | **identical** |
| applied migrations | *(baseline)* | **identical** |
| image ids (`transcribe-md`, `-worker`) | *(baseline)* | **CHANGED — the only permitted movement** |

**A movement in any row but the last is THE FINDING**, whatever explanation is
available for it afterwards. This change has no mechanism by which a clinical
count could move, which is exactly what makes a movement worth stopping for.

---

## ⚠️ WHAT THIS DECLARATION DOES NOT CONTAIN, AND WHY

**No production baseline numbers.** This session has no production database
access — the read was attempted and denied, which is the correct posture for a
session that never deploys. The rows above are therefore stated as an
**invariant to compare against**, not as measured values.

The deploying session captures the baseline. **An unmeasured row named
honestly is worth more than a number I could not read.**

---

## VERIFICATION AVAILABLE TO A DEPLOY, WITHOUT TOUCHING A RECORD

Structural only, per standing law — no real doctor's visit is a smoke target:

- the post-signature rows are present in the shipped bundle:
  `grep -c 't4-action-' <built chunk>` — expect **≥ 1**
- container health and image digests moved for the two app images
- co-tenant HTTP status unchanged
- **no clinical flow needs exercising to verify this change.** The full walk
  belongs on QA against a byte-identical build.
