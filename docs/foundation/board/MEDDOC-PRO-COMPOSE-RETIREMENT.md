# BOARD FILING — RETIRE `meddoc-pro`'s COMPOSE SERVICE (ruling #307)

**Filed 2026-09-09 by the Design/Admin session, to Custom-file (they own compose
and deploy).**

⚠️ **THIS IS A FILING, NOT AN INSTRUCTION.** Authorization travels owner →
session and never sideways through a peer. Ruling #307 is the owner's; this
sheet is the evidence and the shape, offered to the lane that owns the surface.

## THE ASK

Remove `meddoc-pro`'s **compose service definition** and its **image
reference**, so that no `docker compose up` can revive an unlocked `users`
writer.

- a **declared** change (§2.5-style), **git-reversible**
- carrying the **co-tenant baseline row**

## WHY — AND THE MEASUREMENT, NOT THE ARGUMENT

`apps/meddoc-pro` contains **four unlocked `users` writers**:

    src/app/dashboard/settings/actions.ts
    src/app/system-admin/actions.ts
    src/lib/nextauth.ts
    src/lib/session-log.ts

They write `isActive`, `deactivatedAt` and `practiceRole` — all predicate
columns of `users_last_owner_guard` — and `withPracticeLock` appears **nowhere**
in that app (`grep -rc` returns 0 across `apps/meddoc-pro/src`).

⚠️ **THE MISSING LOCK IS LOAD-BEARING AND WAS REPRODUCED.** Two individually
legal concurrent writes on a three-owner practice — one through
transcribe-md's **locked** `suspend`, one through the unlocked cross-app door —
produced:

    ERROR:  deadlock detected
    DETAIL: Process A waits for ShareLock on transaction …; blocked by process B.
            Process B waits for ExclusiveLock on advisory lock …; blocked by A.
    CONTEXT: while locking tuple in relation "users"
      SQL statement "SELECT 1 FROM "users" u WHERE u."practiceId" = OLD."practiceId"
                     AND u."id" <> OLD."id" FOR UPDATE"
      PL/pgSQL function users_last_owner_guard() line 103 at PERFORM

**The LOCKED door lost, and its write silently did not happen.** That is the
`#268` shape exactly, reinstated by a door the `#289` derivation is scoped away
from (`git ls-files src` runs with `cwd: apps/transcribe-md`).

## WHY NOW, WHEN IT HAS BEEN DOWN FOR WEEKS

Retired is not the same as unreachable. Measured today:

| fact | value |
|---|---|
| container | `Exited (143)` ~5 weeks |
| `pro.quillmd.com` | **410**, by design (`check-cotenants.sh` exit 0) |
| compose service | **still defined**, `docker-compose.yml:92` |

One `docker compose up` away. The gap between "nobody starts it" and "nobody
*can* start it" is the whole filing.

## THE BASELINE ROW THAT MUST TRAVEL WITH IT

> `pro.quillmd.com` **must still answer 410.** ⚠️ **A change AWAY from 410 is
> the finding** — not the 410 itself. `scripts/check-cotenants.sh` is the
> expectation table (ruling #265(d)); it currently reports five hosts and **four
> distinct codes**, so the probe discriminates.

## WHAT THIS DOES **NOT** DO

**It closes the door. It does not delete the writer.** The four doors stay
PINNED in `gate-289-derived-door-list.test.ts` — an arm that fails if the set
grows **or shrinks**, with a positive control that the matcher still fires on
the pinned file — until **DELETE-MEDDOC-PRO** (filed as an arc row in
`RELAY.md`) removes the code. The pin retires with that row and not before.

## ⚠️ AND A HAZARD THIS FILING ALMOST WALKED INTO

`docs/audit-reports/admin-arc-recon-20260904.md` found that
`apps/meddoc-pro/src/app/system-admin/` is **the only worked provisioning design
in the repository**, and that **ADMIN's verb is PORT, not BUILD**. It names the
danger explicitly against the old `A6` row:

> *"If A6 runs first, the only worked provisioning design is destroyed. A6's
> preconditions need amending before A6 runs."*

**`A6` is no longer in `RELAY.md`.** So that warning had nothing to attach to
until `DELETE-MEDDOC-PRO` was filed — by me, for an unrelated reason (the
deadlock), without having read it. **That is how a named hazard gets re-created:
not by ignoring the warning, but by creating a new row the warning does not
point at.** The precondition is now carried on that row.

**Nothing here is blocked by it.** Removing the compose service and image
reference deletes **no code**; it is the half that closes the door. The port —
or a capture of the design and the audited action shapes — gates only the
**code deletion**.
