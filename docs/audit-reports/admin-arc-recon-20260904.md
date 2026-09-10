# ADMIN arc — read-only recon of the four owner-ordered rows

> ⚠️ **SUPERSEDED 2026-09-09 by `admin-arc-recon-9rows-20260909.md`.**
>
> This recon covers **five** of the arc's **nine** rows. It predates the split of
> ADMIN-2 into ADMIN-2 (subdomain) + ADMIN-2b (apex domains), and predates
> ADMIN-6 and DELETE-MEDDOC-PRO entirely. The nine-row pass re-checked its claims
> rather than copying them and found **57 that had drifted**, listed per row
> there.
>
> **Two conclusions survive and are carried forward, not discarded:** the ADMIN-0
> baseline, and *"the verb for ADMIN is PORT, not BUILD"* — the system-admin
> console remains the design source. Do not work from the table below; work from
> the nine-row table, which cites this one where it still holds.


**2026-09-04 · Design/Admin session · owner ruling #176.**
Eleven agents, each verdict re-derived by a second agent told to assume the
first called something EXISTS that is only PARTIAL. Every load-bearing figure
below was then re-measured by hand before it was written down; the ones that
changed a conclusion are marked ✅ **re-verified**.

Read-only throughout. No file outside this session's worktree was written, the
shared tree `/opt/meddoc-pro` was never touched, and every production query was
a `SELECT` over counts, enum values and column names — never clinical text.

---

## The table

| Row | Verdict | What EXISTS (reachable today) | What it takes | Blocked on |
|---|---|---|---|---|
| **ADMIN-0** — the admin surface *(baseline, not one of the four)* | **PARTIAL** | 6 gated pages, 29 `/api/admin/*` routes (17 GET / 12 POST), all behind `adminApi()`. It is **observe-and-moderate only** — no create-account, create-practice, invite, template or certification surface anywhere. `/admin/queues` is gated and functional but **unlinked** (`AdminNav.client.tsx` lists 5 hrefs; queues is not one). | Port provisioning in behind the wrapper that already exists; link `/admin/queues`; add a delivery reader. | ⚠️ **`visitDelivery` has exactly ONE ORM reference in the tree and it is a `.create`** — 140 rows written by 5 callers, **read by nobody**. Delivery status is written and unreadable. |
| **ADMIN-1** — practice multi-user | **PARTIAL** | The tenancy half is **shipped and live**: `practice-scope.ts:123-158`, 45+ importers, CI ratchet at 0/0. `PracticeRole` + `User.practiceRole` **already applied in production**. Invite redemption carries `(practiceId, practiceRole)` end to end, E2E-proven. | Seat-minting with a role; member/role UI with a self-demotion guard; enforcement past signing. **No migration needed.** | ✅ **re-verified:** `note_templates` is RULED doctor-scoped and deliberately not migrated — colleagues **cannot share a note format**. Narrower than practice scope, so not a tenancy hole; a ruling to re-open, not a bug. **OWNER class (a):** who may invite and promote. |
| **ADMIN-2** — custom domain per practice | **MISSING** | Nothing. **0** host/domain columns across **592** public columns (positive control: the same ILIKE returns 2 `%url%` rows). 16 identifier spellings → **0 files**, against a **427-file** `practiceId` control. No `practice.update` anywhere in src. | A `practice_domains` carrier; host→practice resolution reconciled against the session; unpin the hardcoded app URLs. | ⚠️ **`Practice.slug` is a FALSE POSITIVE** — its doc-comment promises subdomain routing, it has **zero** routing readers, and **195 of 199** values are machine-generated. **DEPLOY OWNER** owns every ingress leg, and an **ACME blocker exists today**. |
| **ADMIN-3** — specialty partitions | **PARTIAL** | **Two** live axes, neither a workspace: a **one-member imaging partition** (`isImagingReportSpecialty(id) => id === 'ultrasound'`) driving report shape, E/M suppression at three layers and the sign gate; and a **fifteen-member prompt partition** (`SPECIALTY_GUIDANCE`). | Make the partition DATA (`reportKind`) before any UI; then a workspace model. | ⚠️ The "flag" is a **hard-coded one-member set with six unlisted consumers**, and there is **no index on `specialty`**. **OWNER class (a):** filter or model — a board filter would reverse R3.8. |
| **B8/B9** — promo + pricing | **PARTIAL** | Enum at all three layers; `grantPromoCredit()` writes one append-only row of $10; three doors. **Production: 177 rows, all `grant`, summing $1,770.00.** | Owned by the billing session. | ✅ **re-verified, and it contradicts the order:** **$10 per PRACTICE, not per user.** 177 grants across **177 distinct practices**; the 11-seat practice got **$10, not $110**. |

---

## The one thing that most changes how ADMIN should be sequenced

**A complete, audited provisioning console already exists — and it is scheduled
for deletion.**

`apps/meddoc-pro/src/app/system-admin/` holds `createUserAction`
(`actions.ts:249`) → `prisma.user.create` (`:277`) → a `USER_CREATED` audit row
(`:290`), alongside edit / reset-password / sessions modals, an audit page and a
metrics page. The recon lens reported "no admin surface can create an account"
and concluded MISSING; the verifier corrected it, and the correction survives
only on **reachability** — the container is `Exited (143)` and
`pro.quillmd.com/system-admin` returns **410**.

So the verb for ADMIN is **PORT, not BUILD** — and explicitly **not REVIVE**:
that app is dark *deliberately*, as a shipped security block, recorded at
`DISCOVERY.md:53`, in the relay archive and in five deploy reports, with a
written reversal procedure.

⚠️ **The ordering constraint is hard.** RELAY item **A6 deletes
`apps/meddoc-pro/` outright**, and its stated preconditions say nothing about
salvaging that console. If A6 runs first, the only worked provisioning design is
destroyed. **A6's preconditions need amending before A6 runs**, and that belongs
to whoever owns A5/A6 — not to this row.

Its code is also **unverified**: CI typechecks and builds exactly one target,
`transcribe-md`. **0 of 8** build/typecheck lines across all five workflows name
`meddoc-pro`. What is salvageable is the *design* and the *audited action
shapes*, ported into `transcribe-md`'s `/admin`, which already has the
`SUPER_ADMIN` gate, the 404 posture, 12-hour session freshness and the audited
wrapper.

---

## ⚠️ A security finding, verified independently before it was written down

**The admin PAGE gate enforces MFA. The admin API gate does not.**

| leg | measurement |
|---|---|
| `grep -ci mfa apps/transcribe-md/src/lib/admin-api-gate.ts` | **0** |
| positive control — the same grep on `app/admin/layout.tsx` | **hits at :69-86**, whose own comment says it *"closes shadow-audit HIPAA_FINDING_001"* |
| what the API gate *does* check | auth → fresh DB re-read of `products` + `isActive` → `SUPER_ADMIN` → 12-hour session freshness |
| POST routes behind it | **12**, including `grant-admin`, `revoke-admin`, `soft-delete`, `suspend`, `reset-password`, `force-logout` |
| production `SUPER_ADMIN` accounts | **3** |
| …of those, with MFA enrolled | **0** *(positive control: 198 users total, so the query shape works)* |

Two consequences, and the second is the one that bites the ADMIN arc:

1. **A defence-in-depth gap.** The MFA control was added specifically to close a
   HIPAA finding on the pages; every one of the 29 API routes bypasses it. It
   still requires an authenticated `SUPER_ADMIN` session — this is not an
   unauthenticated hole — but the control does not hold where it was claimed.
2. **The admin console is currently unusable by every super-admin.** All three
   are redirected to MFA enrolment before any `/admin/*` page renders. **Item 4
   would be building a console nobody can open.** Enrolling MFA is an owner
   action, self-recoverable at `/settings/security/mfa`, and it is a
   precondition for the ADMIN arc rather than part of it.

Surfaced rather than fixed: it is a change to an authentication gate on a
surface the owner is about to commission, and the right moment to close it is
with him looking at it.

---

## Work that is explicitly NOT this session's

- **DEPLOY OWNER** — every ingress leg of ADMIN-2 (a vhost, an acme-challenge
  location, certbot, the `Caddyfile` bind mount, confirming the renewal hook).
  Also: the tracked `infra/nginx/quillmd.conf` is **stale in a security-relevant
  direction** — it still sets `X-Forwarded-For $proxy_add_x_forwarded_for` where
  live sets `$remote_addr`, which the `Caddyfile` itself describes as a
  client-IP spoofing vector.
- **DEPLOY OWNER** — any `NEXT_PUBLIC_*` change is build-time inlined: a rebuild
  and a §2.5-declared deploy, never a restart.
- **OWNER, class (d)** — a DNS API token (absent; without it there is no DNS-01
  and therefore no wildcard cert), Stripe keys, and flipping `BILLING_ENFORCED`,
  which converts a wired no-op into a gate that can refuse service.
- **OWNER, class (a)** — the four product questions in ruling #176.
- **THE BILLING SESSION** — B8/B9 in full. It must not resurrect or delete
  `apps/meddoc-pro` unilaterally.
- **WHOEVER OWNS A5/A6** — amending A6's preconditions before it deletes the
  console described above.

---

## Provenance, and honest limits

Recon ran against a worktree at `cb2d3fcc` (branch
`fix/t3-signed-note-black-frame`), whose diff against `origin/main` is empty
over `apps/meddoc-pro`, `apps/marketing` and everything outside the two T3
files — so these citations are about `main`'s code, not about T3's change.

**Not established, and named rather than glossed:**

- The recon's own first pass was **wrong twice** — it claimed `/system-admin`
  does not exist, and that `user.create` had a single non-test site. Both were
  corrected under verification. Its verifier was also wrong once, claiming the
  `pro.quillmd.com` retirement had no repo record; it has five.
- Seat distribution figures differ between the recon (over all 199 practices)
  and this report (over the 177 *granted* ones). The figures here are mine, and
  they answer the question the row asks.
- Nothing here was exercised against a running admin console, because no
  super-admin can currently open one. Every ADMIN-0 claim is from source,
  route enumeration and read-only SQL.
