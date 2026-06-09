# Deploy — Rx override-gate per-warning correlation (`fix/rx-override-gate-correlation`) → prod

**When:** 2026-06-09 ~21:20 UTC
**What:** Close the critical-Rx override-count-inflation bypass (F5-1 follow-up) + remove the latent
ungated `signVisitAction` sign path. The gate now clears READY→SIGNED only when every persisted
critical warning has a matching override keyed by its REAL id; `recordOverride` validates the
submitted warningId/severity against `rxDrafts` on write.
**Result:** ✅ Deployed + verified in prod (4/4 gate assertions). No rollback. Worker + co-tenants untouched.

Commit: `0efb7c3` on `fix/rx-override-gate-correlation`. Image: `f7b622c7cd7c` (`:latest`).

---

## Pre-flight gate
🟢 GO (`docs/preflight-reports/preflight-20260609T210357Z.md`). Disk 54%/131G, RAM 11.3G avail + 2.7G swap
(comfortable for the 6G-heap build), all 9 prod containers healthy, balloon blacklist intact, 0 OOM.
Builder/image prune deferred (cache all <72h → 0B; image prune suppressed on the co-tenant box to preserve
rollback tags).

## Build once → validate → deploy the same artifact
- Source committed at `0efb7c3` (branch `fix/rx-override-gate-correlation`); built from the working tree.
- **Rollback captured first:** `docker tag …:latest …:pre-rx-gate-fix` → `4464002` (the running prod image,
  today's logout fix) **before** the build moved `:latest`.
- `docker compose build transcribe-md` — Dockerfile bakes the heap raise (`--max-old-space-size=6144`) +
  bundle-assert. Build exit 0, **no OOM**, `[bundle-assert] OK -> unpdf, mammoth, unpdf/pdfjs`. New image
  `f7b622c7` (distinct from `4464002`).
- **Content-verified the artifact** (not a cache no-op): the recordOverride validation literal
  (`That warning is not on this visit`) + `criticalWarningRefs` are present in `.next/server`;
  `signVisitAction` is **absent** (deleted server action no longer compiled/registered).
- App-only deploy — the worker is unchanged by this fix; the existing worker image already carries the
  `MOCK_RX_WARNINGS` fixture (`packages/ai/src/mock.ts`), so no worker rebuild.

## qa-stack validation (isolated `meddoc-qa`, prod untouched)
The exact `:latest` image (`f7b622c7`) was run on `docker-compose.qa.yml` (separate project/network/volumes,
app on 127.0.0.1:9020, `MOCK_AI_CALLS=true`, fail-closed `@meddoc/db/guard`):
- **rx-safety project (24 + 25): 7/7 passed (58.5s)** — un-overridden critical → 422; **fabricated 'critical'
  rows → still 422/READY (inflation closed)**; genuine override → 200/SIGNED; genuine override clears even
  amid fabricated noise rows.
- **chromium full regression: 28 passed, 16 skipped, 0 failed (3.0m)** — the 16 skips are flag-gated
  note-format scenarios (18–22), unrelated to this diff; sign-PDF / SOAP-render / SOAP-edit / patients /
  visit-list all green (gate is fully transparent when `criticalRefs` is empty).
- **vitest** (the 4 files touching the diff): 53/53. New `recordOverride` correlation test 6/6 (accepts
  genuine; rejects malformed / out-of-range / severity-lie). The full 98-file vitest suite (with DB-backed
  integration tests) runs in CI's `npm run test:all` — a required merge gate.
- qa stack torn down with `-v`.

## Prod deploy
- Recreated **only** the app: `docker compose up -d --no-deps transcribe-md` (NOT `--remove-orphans`).
  Before→after container diff: solely `meddoc-pro-transcribe-md-1` recreated onto `f7b622c7`; worker
  (`91c97b…`, StartedAt unchanged) + all meddoc-pro services + co-tenants (leathererp-*, openclaw,
  voiceassist-*, lerp-throwaway) byte-identical.
- App healthy (`/api/health`: postgres/redis/minio all ok); live bundle confirmed to carry the fix +
  no `signVisitAction`. Public surfaces: app 307, pro 200, quillmd 200.
- Post-build builder-cache prune (`-af --filter until=72h`, cache-only) → 0B. Disk 56%/125G.

## Post-deploy verification (PROD, real auth flow + the deployed gate)
Scoped to the `qa-auditor@quillmd.test` test account + two synthetic test visits, exercised via the real
NextAuth credentials login (temp password set then **restored & verified == original**) against the
deployed route. A trap deleted all test data on exit. **4/4 PASS:**

| Assertion | Expectation | Result |
|-----------|-------------|--------|
| A — un-overridden critical warning | sign blocked 422 `OVERRIDE_REQUIRED` (names real `rx-warning-0`) | ✅ 422 |
| B — fabricated 'critical' override row (bogus warningId) | **still 422** (coverage, not count) | ✅ 422 |
| C — genuine override of the real warning (`rx-warning-0`) | 200 → SIGNED | ✅ 200/SIGNED |
| D — normal visit, no critical warning | 200 → SIGNED (no regression) | ✅ 200/SIGNED |

Cleanup verified: 0 leftover test visits, 0 leftover override rows, qa-auditor password hash restored
(`hash == original`), sessions cleared.

## Blast radius / safety
- Prod writes confined to the `qa-auditor` test account: temp password (one scoped UPDATE, restored +
  verified), two synthetic test visits + their override/edit-pattern rows (all deleted), session rows
  cleared. No real patient/visit data touched. 308 real users + their data unchanged.
- Worker + all co-tenants byte-identical (verified by container diff + worker StartedAt).
- `signVisitAction` removed: the unified POST `/api/visits/[id]/sign` is now the SOLE READY→SIGNED path.

## Rollback (retained, unused)
`meddoc-pro-transcribe-md:pre-rx-gate-fix` → `4464002ecda3` (the exact pre-deploy prod image, today's
logout fix). To roll back: `docker tag …:pre-rx-gate-fix …:latest && docker compose up -d --no-deps
transcribe-md`. Not needed — gate verified healthy in prod.
