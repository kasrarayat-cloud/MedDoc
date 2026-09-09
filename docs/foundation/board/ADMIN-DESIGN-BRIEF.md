# DESIGN BRIEF — the ADMIN shell, and the money view inside it

**For the owner's three Claude Design sessions. One page.**
Filed 2026-09-09 by Design/Admin, from `admin-arc-recon-9rows-20260909.md`.

---

## THE ONE CONSTRAINT THAT ORDERS EVERYTHING

> **The shell is designed first. Features go into it. No ADMIN-4 screen is built
> on the old dashboard.**

And the verb is **PORT, not BUILD** — re-derived and confirmed by the nine-row
recon. A complete, audited provisioning console already exists at
`apps/meddoc-pro/src/app/system-admin/`. It is **dark deliberately** (container
`Exited (143)`, `pro.quillmd.com` answers **410**), and it is **never revived** —
its *design* and its *audited action shapes* are what move.

---

## WHAT EXISTS TODAY (the thing being replaced)

`/admin` in the live app — **6 pages**, no shell to speak of:

    /admin  ·  /admin/users  ·  /admin/usage  ·  /admin/queues
    /admin/hipaa  ·  /admin/threats

Every one inherits, by construction and with no per-page work: a `SUPER_ADMIN`
entitlement re-read per request, `notFound()` rather than a redirect so the
route's existence is not disclosed, a ≤12-hour admin-session freshness check,
and an access audit row.

⚠️ **So the gate is not a design problem.** Anything placed under `/admin`
is already guarded. Design the surface, not the lock.

## THE SOURCE TO PORT

`apps/meddoc-pro/src/app/system-admin/` — a users table with row actions, and
**four modals**: Add User, Edit User, Reset Password, User Sessions. Plus an
**audit page** and a **metrics page** whose `StatCard` (label / value / state,
with `HEALTHY · DEGRADED · DOWN`) is the nearest shipped art to a money card.

Nine audited server actions define the action vocabulary worth keeping:
`create · update · deactivate · activate · delete · resetPassword ·
killAllSessions · getUserSessions · deleteSessionLog`.

---

## SCREENS the shell must hold

| screen | why it is in the first cut |
|---|---|
| **Practices** | ⚠️ **There is NO write path to a `Practice` row anywhere in the product** — `practice.update` = 0 call sites, against 15+ for `user.update`. Four filed rows wait on this one missing verb (specialty, archive, slug, and standing ruling #226). |
| **Money** | ADMIN-4. Detailed below. |
| **Users** | the port target for the console's table + four modals. |
| **Audit** | the console has one; `/admin` does not. |

## CARDS

- **Rate in effect** — the number, and *since when*.
- **Practice usage** — cost, charge, margin, per practice.
- **Wallet** — ⚠️ **two buckets, promo separate from paid**, never one number
  with a note. The settings page already *promises* a balance the product cannot
  show; the same two numbers serve the doctor and the platform.
- **Health** — port the `StatCard` state vocabulary rather than inventing one.

## STATES every surface needs, and one that is usually forgotten

`loading · empty · error · refused (403/404-gated) · stale (>12h session)`

⚠️ **AND THE ONE THAT MATTERS HERE: NO RATE CONFIGURED.** It is not an error and
not an empty list — it is a *refusal with a cause*, and it is the state the
platform is in **right now**.

---

## THE MONEY VIEW — its fields, exactly

**The rate editor**

| field | notes |
|---|---|
| margin | ⚠️ **an exact ratio — numerator / denominator, never a decimal input.** `1.5` is representable in binary64 but `cost * 1.5` is a Number and loses precision above 2^53 µ$. Show `1.50×`; store `3 / 2`. |
| effective from | forward-only. **A change takes effect at the next metering cycle, never retroactively.** |
| bounds | ≥ 1.0 and ≤ 5.0 — already enforced by a DB CHECK. |
| note | free text — *why*. |

**The history** — insert-never-update, so it reads as a list and never a diff:

    when · who changed it · from → to · note

**Per practice**

    cost (µ$) · charge (µ$) · the rate that applied · promo balance · paid balance

⚠️ **"The rate that applied" is a stamped row id, not a recomputation.** Every
ledger row carries the `platform_rates` id it used. A money view that
re-multiplies is a second implementation of the rate and will disagree with the
ledger the day somebody changes it.

---

## THREE THINGS THE DESIGN MUST NOT ASSUME

1. **There is no configured rate today.** The table ships empty on purpose —
   seeding it would make a migration the thing that set the price. The first
   screen a real operator sees is the *no rate configured* state.
2. **Nothing is billing.** `BILLING_ENFORCED` is absent from production and
   stays absent **until this view exists**. The money view is what makes turning
   it on a decision somebody takes rather than a flag somebody flips.
3. **A balance has never been shown to anyone** — not to a doctor, not to a
   SUPER_ADMIN. There is no existing screen to be consistent with, and no user
   habit to preserve.
