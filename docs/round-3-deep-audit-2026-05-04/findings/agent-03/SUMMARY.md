# Agent 03 — Authorization & Tenant Isolation · Summary

## Severity counts
**P0: 0 · P1: 0 · P2: 2 · P3: 2 · Total: 4**

## Top 3 findings
1. **A03-P2-001** — `POST /api/settings/delete-account` (route.ts:135-144) calls `aiCall.deleteMany({ practiceId })` + `practice.delete({ id })` with no peer-user count check. Today every TM Practice is solo (signupAction at actions/auth.ts:371-394 always mints "Solo — {name}"), but if a User is ever re-parented to a multi-seat Practice this becomes a tenant-wide PHI delete. Schema cascade on `TranscribeMdPatient.practiceId` (schema.prisma:1356) would wipe other doctors' patient catalogs.
2. **A03-P2-002** — GET /api/visits/[id] and /visits/[id]/page.tsx pull `patient` via nested include with no `practiceId` filter (route.ts:90-100, page.tsx:196-207). PATCH validates the *new* patientId, but a stale `visit.patientId` from a prior practice would still leak. Same root cause as P2-001 — visits user-scoped, patients practice-scoped, no denormalised practiceId on TranscribeVisit.
3. **A03-P3-002** — Every visit endpoint enforces `visit.userId !== userId`. The role taxonomy at packages/auth/src/index.ts:283-291 implies ADMIN sees their whole practice, but TranscribeMD never reads `session.user.role` for visit access. Documentation/scope gap, not a security one — pilot is solo doctors so it doesn't bite.

## Coverage
**63 / 63 routes audited (100%).** Visits (16), patients (4), settings (4), auth (6), admin (31), misc (2). Plus all RSC pages (/dashboard, /patients/[id], /visits/[id], /visits/[id]/record, /visits/new, /settings, /admin/layout); all server actions (auth, visits, soap, patients, profile, session, command-palette, em-score, rx-warning-audit); worker.ts. `git grep findUnique({where:{id` produced ~70 hits — every PHI-touching one traced and confirmed to enforce ownership in the immediate next statement.

## Positives
1. **404-not-403 anti-enumeration is consistent** across every per-id route, centralised in `loadVisitExportData(visitId, userId)` (lib/visit-export-server.ts:57).
2. **Admin-API gate** (lib/admin-api-gate.ts:66-129) re-reads `User.products` from DB on every request, falls through to uniform 404 for non-admins, enforces 12h admin-session freshness on top of the 7d cookie, writes `ADMIN_API_ACCESS` audit before every handler. Every /api/admin/* route uses it; none bypass.
3. **Worker re-validates from DB**, never trusts the BullMQ payload. worker.ts:236-249 reads `visit.userId` + `visit.user.practiceId` from Prisma; payload userId is advisory (used only for jobId namespace). A poisoned queue cannot escalate.
4. **Email-export self-only guard enforced twice** — POST /api/visits/[id]/export/email (route.ts:62-86) AND POST /api/visits/[id]/sign (route.ts:104-133) both reject `to !== sessionEmail` with 403 + audit row.
5. **Self-action blocks** on revoke-admin, suspend, soft-delete (admin/users/[id]/...) reject `id === ctx.session.user.id` server-side; force-logout-on-revoke clears cached SUPER_ADMIN claims within one request.

## Cross-domain hooks
- **Agent 05 (audit logging)**: ensure `ACCOUNT_DELETED` audit row persists when peer-count guard skips Practice delete.
- **Agent 09 (migrations)**: a denormalised `practiceId` on TranscribeVisit closes both P2 findings — flag for migration backlog.
- **Agent 09 (queue/worker resilience)**: the worker's "re-validate from DB" relies on visit not being deleted between enqueue and pickup; confirm BullMQ job dies cleanly when row missing rather than retrying.

**Verdict:** Authz layer genuinely solid for pilot. No P0/P1. The two P2s are class-of-bug latent defects depending on multi-seat scenarios that don't exist today — patch before first multi-doctor signup, not before pilot.
