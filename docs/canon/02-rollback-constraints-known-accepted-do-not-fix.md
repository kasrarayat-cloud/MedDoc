> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **6 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## Rollback constraints — known, accepted, do not "fix"

A flag rollback is not always a clean inverse. Where it costs a capability, the
cost is recorded here so nobody rediscovers it mid-incident and starts building.

### `NEXT_PUBLIC_REVIEW_DOC_VIEW=false` → E/M is confirm-only, no override

**Decided 2026-07-28. Accepted.**

Rolling that flag back returns the legacy tabbed review view, where a doctor can
see the documentation level and confirm a change to it but **cannot set one**.
The override lives only in the read-only paper's gate stack (`<EmLevelCard>`);
`BillingCardC3`'s dropdown and the coding rail's were retired in the same change
because `POST /em-score/override` requires a reason and neither had anywhere to
collect one — they would 400 on every use.

**The gate does not weaken** — confirm-before-sign and the server-side refusal in
`POST /sign` are flag-independent. One capability is lost, temporarily.

**Acceptable for an emergency window. Revisit only if a rollback must live
long**, and then by giving `BillingCardC3` its own required-reason step — never by
restoring a reasonless caller, and never by fabricating a rationale to satisfy
the route. An audit row's "why" is the doctor's words or nothing.

Prefer the IMAGE rollback (`:pre-emrehome-20260728`) when the concern is the E/M
surface specifically — it has no such constraint. Full detail and the tag table:
`docs/DEPLOYMENT_RUNBOOK.md` §3.1–3.2.


### A PRE-DEPLOY SIGNED VISIT SERVES **STYLED** FOREVER — accepted 2026-08-21

**Ruled (a): ACCEPTED. Do not build a re-attestation path.**

F5-h made a signed record resolve its document **by pointer, never by lookup**
(`native-export.ts:63-67`): a SIGNED visit with no `frozenFillManifestId`
declines to styled. Every signature taken **before** that deploy has NULL
there.

**Measured on production the day it shipped, and the partition reconciles:**

| set | count |
|---|---|
| SIGNED · VERIFIED manifest · no pointer → **loses native export** | **1** |
| SIGNED · no manifest (styled anyway — unaffected) | **30** |
| UNSIGNED with a manifest (freshness path — unaffected) | **0** |
| | **31 SIGNED** |

The one is the owner's first certified-twin visit — **the very record whose
Word download he confirmed carried his letterhead.**

⚠️ **BOTH HALVES ARE TRUE, AND THE COMFORTABLE ONE ALONE IS THE DISHONEST
FRAMING.** It is **correct-by-design**: that manifest's `noteSha256` is NULL —
written before the column existed — so nothing proves it corresponds to the
signed text, and serving it would be exactly the stale-manifest class the
freeze exists to kill. It is **also a capability lost**, permanently, for that
record.

> **A null identity is DECLINED, never inferred — the rule applied to its own
> pre-history.**

**WHY NO RECOVERY PATH WAS BUILT.** A backfilled pointer asserts a match nobody
verified: the manifest rendered at `00:18:46Z`, the visit signed at
`00:25:42Z`, and no stored hash from that era exists to compare. Re-running the
fill to compare would **mutate a signed clinical record**. The only honest
option is to decline. Its only beneficiary would be a record that already reads
correctly in styled form — the clinical content is intact; what is lost is the
doctor's own form as the *presentation* of one historical document.

⚠️ **HONEST LIMIT, RECORDED WITH IT: established by READING THE SHIPPED CODE,
never by exercising it.** The only visit that would demonstrate it is a real
patient's signed record, and a real doctor's visit is never a smoke target.

**IF A DOCTOR RE-DOWNLOADS A PRE-2026-08-21 SIGNED VISIT AND GETS THE GENERIC
LAYOUT, THAT IS THIS ENTRY, NOT A BUG.** Everything signed from that deploy
onward carries a pointer and renders native in **both** formats.

