# Deploy — logout-session revoke fix (#285 / `92163f7`) → prod

**When:** 2026-06-09 14:49 UTC
**What:** Ship the merged-but-undeployed security fix that revokes the server-side
`UserSession` row on sign-out (`events.signOut` in `apps/transcribe-md/src/lib/nextauth.ts`,
commit `3208ad6`). Prod had been serving the 2026-06-04 image, so the logout re-mint
window was LIVE in production.
**Result:** ✅ Deployed + verified. No rollback. Co-tenants + worker untouched.

---

## Discovery — prior incomplete deploy (handled, not blocking)
The app image tag state contradicted the task's clean-slate assumption — evidence a prior
session got partway and stopped:

| Image | Tag(s) at start | Built | Fix literal present? |
|-------|-----------------|-------|----------------------|
| `8ef51420` | `:latest` | 06-09 08:24Z | ✅ present (a prior, never-deployed fix build) |
| `e88e5af8` | `:pre-logout-fix` | 06-09 03:21Z | ❌ absent (pre-fix; **not** the running image) |
| `9a26086…` | `:pre-batch1` (**running prod**) | 06-04 | ❌ absent (vulnerable) |

Two consequences handled:
1. The pre-existing `:pre-logout-fix` tag was a **misleading rollback target** (it pointed at a
   pre-fix image that was never in production). Rollback was instead pinned to the **actual running
   digest** `9a26` via a new tag `:prod-rollback-20260609`. The misleading tag was left untouched.
2. The unknown-provenance `:latest` (fix-present) was **not** trusted for a security deploy. Built
   fresh from verified HEAD instead; preserved `8ef51420` as `:prior-fixbuild-8ef51420` (a fallback
   had the rebuild OOM'd).

Fix presence was determined by **content** (grepping the minification-proof literal
`session revoke failed` inside each image's compiled `.next/server` bundle), not by timestamps —
the commit author-date initially looked like `:latest` predated the fix, but the bundle grep proved
otherwise.

## Pre-flight gate
🟡 FIX-AND-GO (`docs/preflight-reports/preflight-20260609T143537Z.md`). No blockers. Disk 47%/152G,
RAM 11.6G avail + 4G swap (comfortable for the 6G-heap build), all 9 containers healthy, 0 OOM in 24h.
Two auto-fixes intentionally not applied: image-prune suppressed (co-tenant-shared box), builder-prune
deferred to post-build (preserve cache for the OOM-sensitive build).

## Safe app rebuild
- Source verified clean at `HEAD == origin/main == 92163f7`; no uncommitted changes under
  `apps/transcribe-md` or `packages/`. (The only dirty file, `Caddyfile`, is inert for the app image —
  runner stage copies only `.next/standalone`+static+fonts+prisma; `.dockerignore` excludes docs/*.bak.)
- `docker compose build transcribe-md` — the Dockerfile builder stage already bakes the heap raise
  (`NODE_OPTIONS=--max-old-space-size=6144`, from the 2026-06-04 incident) and the **bundle-assert**
  guard. Build exit 0, **no OOM** through `next build`, `[bundle-assert] OK -> unpdf, mammoth, unpdf/pdfjs`.
- New image `sha256:4464002ecda3…` (`:latest`), distinct from running-prod `9a26` and prior-fixbuild
  `8ef51420` (genuine fresh build, not a cache no-op). Fix literal + `revokeSession`/`revokeAllUserSessions`
  confirmed in the compiled bundle.
- Recreated **only** the app: `docker compose up -d --no-deps transcribe-md` (NOT `--remove-orphans`).
  Compose recreated solely `meddoc-pro-transcribe-md-1`; before/after container diff showed every other
  container (worker, all meddoc-pro services, `leathererp-*`, `openclaw`, `lerp-throwaway`) byte-identical.
- Builder-cache prune (`-af --filter until=72h`, cache-only) ran post-build → 0B (cache is all <72h, fresh).
  Disk 49% / 147G — healthy; no aggressive prune warranted.

## Post-deploy verification (prod, real auth flow)
Image: running container serves `4464002`, `session revoke failed` literal present in the live bundle.

Functional logout-revoke + re-mint test against `https://app.quillmd.com` via the NextAuth endpoints
(curl chosen over a browser specifically to **replay the pre-signout JWT** — the exact re-mint race),
using one reused QA account (`qa-auditor@quillmd.test`), **5 full cycles**:

| Step | Assertion | Result |
|------|-----------|--------|
| login | 302→/, `/api/auth/session` returns the user w/ `sessionId` | ✅ 5/5 |
| DB after login | `user_sessions` row created (token == sessionId) | ✅ rows=1, 5/5 |
| signout | fires `signOut` event → `revokeSession(sessionId)` | ✅ 302→/login |
| **DB after signout** | **row deleted** | ✅ **rows=0, 5/5** |
| **re-mint replay** | replay the saved pre-signout JWT → `/api/auth/session` | ✅ **null, 5/5** (pre-fix would return the user) |
| DB after replay | no row resurrected | ✅ rows=0, 5/5 |

For a bug that was 5–30% intermittent, 5 consecutive cycles each exercising the replay (the failure
mode itself) is strong evidence the window is closed.

**No regression for a normal user:** a fresh logged-in session reaches auth-gated pages
(`/settings` 200, `/visits` 200); gating still works unauthenticated (`/visits` → 307).

## Blast radius / safety
- DB writes were confined to ONE reused QA account: temp password set (one scoped UPDATE), original
  `passwordHash` saved and **restored** (verified `hash_matches_original=true`, temp pw no longer valid),
  its sessions cleared. 308 users unchanged; all 14 remaining sessions belong to other users.
- Worker `91c97b861b36` untouched (same StartedAt, healthy). Co-tenants unchanged — `leathererp-meili`
  is `unhealthy` but was **already** unhealthy pre-deploy (out of scope, not caused here).
- Public surfaces: app 307, pro 200, quillmd 200, `/api/health` 200 through the prod ingress.

## Rollback (retained, unused)
`meddoc-pro-transcribe-md:prod-rollback-20260609` → `9a26` (the exact pre-deploy prod digest;
also still tagged `:pre-batch1`). To roll back: re-point/recreate the app onto `9a26` via
`docker compose up -d --no-deps`. Not needed — auth verified healthy.
