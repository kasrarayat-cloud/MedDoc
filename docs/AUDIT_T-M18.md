# T-M18 Pre-Launch Audit (Round 2)

**Auditor:** Claude Opus 4.7 (via Claude Code session)
**Date:** 2026-04-21
**Scope:** apps/transcribe-md + shared packages (db, ai, auth). CRM app (meddoc-pro/) excluded.
**Methodology:** static analysis of 35 API routes / 7 actions / 14 worker files / 28 lib modules / full schema.prisma read; 10 targeted read-only SQL queries against the live VPS DB; grep-based pattern audits (TODO/FIXME/console.error without redactPhi/Scribe residue).

---

## Executive summary

**Verdict: READY FOR PILOT** conditional on the 4 HIGH findings being addressed first (A1–A4). No CRITICAL launch blockers. No IDOR vulnerabilities. No missing auth guards on mutation paths. Patient/visit lifecycle, retry resilience, and cleanup cron all operate as designed.

**Findings by severity:**

| Severity | Count | Typical fix effort |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 4 | XS–M |
| MEDIUM | 9 | XS–S |
| LOW | 14 | XS |
| INFO | 7 | — |

**Regression check** vs T-M15 audit: every resolved T-M15 finding stays resolved. The new findings are entirely additions from T-M16 → T-M17.3 code, not regressions.

---

## CRITICAL (launch blockers)

None.

---

## HIGH (fix before pilot)

### A1 — `withApiHandler` top-level catch logs raw `err` (potential PHI in stdout)
**Severity:** HIGH
**Location:** `apps/transcribe-md/src/lib/api-error.ts:89`

```ts
} catch (err) {
  console.error(`[${prefix}] unexpected error:`, err);   // ← no redactPhi
  return apiError('internal server error', 500);
}
```

**Impact:** `withApiHandler` wraps every API route. Any unhandled exception (Prisma error with query params echoing back, `TypeError` carrying user text in its message, Zod error containing submitted content) lands in the container's stdout unscrubbed. Docker logs persist indefinitely and are the primary post-mortem source — every one of the T-M16.3 PHI redactions on route-specific catches is defeated by this catchall.

Prisma is particularly exposed: a Prisma client error on `update({ data: { soapFinal: "…full SOAP text…" } })` produces an `Error` whose `.message` includes the failing field value. The T-M17.1 `errorDetails` observability for Claude responses was added explicitly to keep PHI out of stdout; this route-level catch undoes that posture.

**Recommended fix (S):** wrap `err` with `redactPhi` from `@meddoc/ai`:
```ts
console.error(`[${prefix}] unexpected error:`, redactPhi(err instanceof Error ? err.message : err));
```
Same one-liner already lives in every individual route's try/catch. Touching one file fixes the whole surface.

---

### A2 — Worker error path writes `err.message` to `reviewReason` (PHI into DB + UI banner)
**Severity:** HIGH
**Location:** `apps/transcribe-md/src/worker.ts:722-725`

```ts
reviewReason:
  err instanceof Error
    ? err.message.slice(0, 500)
    : 'Unknown error during processing. Try again or contact support.',
```

**Impact:** When a visit fails, the worker writes the raw error message (truncated to 500 chars) to `TranscribeVisit.reviewReason`, which is then rendered as the FAILED-state banner on `/visits/[id]`. A Deepgram/Anthropic/Prisma error whose message quotes the visit's content bleeds that content into the DB and into the user-facing banner. Separate code paths in the same file DO apply `redactPhi` to the console.error side (line 709) — but not to the DB write.

**Recommended fix (S):** apply `redactPhi` before the DB write. Use a two-tier message: a user-friendly generic (e.g. "Processing failed — please retry or contact support. Code: <timestamp>") for `reviewReason`, and the scrubbed detail for the log + Sentry side. This also improves UX — doctors shouldn't see raw SDK error messages.

---

### A3 — Retention config exists in schema but isn't enforced anywhere
**Severity:** HIGH (HIPAA)
**Location:** `packages/db/prisma/schema.prisma:208,211` + T-M15 finding [3.1]

```prisma
audioRetentionDays      Int @default(90)
transcriptRetentionDays Int @default(2555)  // 7y
```

**Impact:** The schema promises per-practice audio retention (90 days default) and transcript retention (7 years default). Neither value is read by any code: grep confirms both fields are only referenced in `schema.prisma` itself, the migration, and the T-M15 audit report. Audio and transcript data persist indefinitely regardless of what the fields say. For a HIPAA-facing pilot this is a compliance gap — the retention policy is a representation to the practice, and we're not honouring it.

The T-M12 MinIO orphan cleanup sweeps only unreferenced audio; it explicitly is NOT a retention-based purge. The T-M17.3 stale-visit cleanup handles abandoned/trashed, not signed visits past retention.

**Recommended fix (M):** extend the worker cleanup module (`worker/cleanup/`) with a `retention-purge.ts` sweep that runs daily:
- For each practice, fetch `audioRetentionDays` + `transcriptRetentionDays`.
- Find visits older than audio retention → delete `audioKey` / `dictationAudioKey` objects from MinIO + null the DB columns (preserve transcriptText + soap content, which is under transcript retention).
- Find visits older than transcript retention → hard-delete the row (cascade handles deliveries + edit patterns).
- Add opt-in env flag `RETENTION_ENFORCEMENT_ENABLED=true` so the first deploy of this is dry-run-verified before it starts deleting real data.

Alternative, lower-effort (S): hardcode retention to `audio = 90d`, `transcript = 7y` in `worker/cleanup/retention.ts` and ignore the Practice fields for now. Good-enough stopgap; the schema fields become future-state.

---

### A4 — `/api/visits/[id]/upload` accepts re-upload during AUTOMATING status
**Severity:** HIGH
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:84-94`

The status reject list includes `SIGNED, READY, TRANSCRIBING, EXTRACTING, DRAFTING, CRITIQUING, POLISHING` — but **NOT `AUTOMATING`**. A visit mid-automation (L7 ICD/CPT/Rx/referrals/summary running) could receive a new upload, flip back to QUEUED, and trigger a duplicate pipeline run.

**Impact:** Medium-size cost bleed (redundant Deepgram + Anthropic calls). The BullMQ per-minute jobId idempotency (T-M16.4) catches double-clicks within 60s but NOT an AUTOMATING→new-upload race that takes more than a minute. Could also cause a confused final state (two SOAP draft versions interleaving).

**Recommended fix (XS):** change the reject list to an allowlist — only QUEUED + FAILED accept uploads:

```ts
if (
  visit.status !== TranscribeVisitStatus.QUEUED &&
  visit.status !== TranscribeVisitStatus.FAILED
) {
  return apiError('visit is already processing or finalized', 409);
}
```
Also remove `SIGNED → cannot be deleted` route's reliance on the inverse pattern for consistency.

---

## MEDIUM (fix before pilot becomes busy)

### A5 — `AccountDeletion` 90-day retention is promised but never purged
**Severity:** MEDIUM (HIPAA/GDPR)
**Location:** `apps/transcribe-md/src/app/api/settings/delete-account/route.ts:56-58`

The code computes `purgeAt = now + 90d` and persists it. No cron or sweep reads this field. `AccountDeletion` rows accumulate indefinitely. At pilot scale negligible; at any volume, a GDPR-deleted-user's email + visit count live forever in the DB after we told them they'd be purged.

**Fix (S):** add to the T-M17.3 cleanup cron: `DELETE FROM account_deletions WHERE "purgeAt" < now()`.

### A6 — Denormalization drift on 3 legacy visits (`patientName` ≠ `patient.name`)
**Severity:** MEDIUM (UX)
**Location:** live DB; rows `cmo56mweh…`, `cmo55fzd8…`, `cmo50q114…`

VisitCard renders `visit.patientName`, patient detail page renders `patient.name`. For the 3 legacy rows where the T-M17.2 backfill picked a different canonical casing ("kAsra" vs older "Kasra" in `patientName`), the same visit shows two different spellings across the UI.

**Fix (XS):** one-shot SQL: `UPDATE transcribe_visits v SET "patientName" = p.name FROM transcribe_md_patients p WHERE p.id = v."patientId" AND v."patientName" IS NOT NULL;` Or deprecate the legacy column entirely — the per-visit name is always derivable from the FK now (this would be a Prisma-schema cleanup one release later).

### A7 — Worker `downloadAudio` loads entire blob into memory
**Severity:** MEDIUM (OOM risk)
**Location:** `apps/transcribe-md/src/lib/minio.ts:86-95`

500MB audio × 2 worker concurrency = 1GB RAM for the audio buffers alone. Worker container has 1024MB mem_limit. A real 500MB upload + a second concurrent job = OOM kill. Current pilot probably uploads sub-50MB clips; not a lurking time bomb but a known low-margin path.

**Fix (M):** stream the audio directly to the Deepgram SDK's file-upload variant. Deepgram's `prerecorded.transcribeUrl` + MinIO presigned URL would skip the worker memory hop entirely. Bigger refactor than the other fixes.

### A8 — `reviewReason` rendered as the FAILED banner can leak stack-shape details
**Severity:** MEDIUM (UX + minor PHI)
**Location:** same as A2; flagged separately because the fix is UX

Even after A2's PHI-scrub, a user sees SDK-flavor error text ("SchemaValidationError: expected string, received undefined" etc.). Doctors have no actionable response to that copy.

**Fix (S):** UI-side — when `reviewReason` matches known taxonomy codes or keywords, map to human copy ("Processing failed due to an unusually short transcript. Please re-upload or contact support."). Keep the raw reason in a developer-visible aside.

### A9 — Upload route re-uploads orphan prior `audioKey` in MinIO
**Severity:** MEDIUM (storage waste + minor PHI)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:168-182`

Re-uploading to a FAILED visit writes the new object key, updates the DB, but never removes the old `audioKey` object. T-M12 orphan sweep catches it eventually but that sweep is opt-in + disabled.

**Fix (S):** before the DB update, if `visit.audioKey` was set, fire-and-forget `deleteAudioObject(visit.audioKey)`. Same pattern for dictation/upload.

### A10 — `/api/visits/[id]/route.ts` PATCH uses `VISIT_DELETED` code for archived state
**Severity:** MEDIUM (error-code taxonomy)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/route.ts:121`

The `archivedAt` branch returns `code: 'VISIT_DELETED'` with the message "Archived visits cannot be edited." Clients that branch on `code` will route to the wrong recovery path. Defensive code path (currently unreachable in production), but ambiguous when it does fire.

**Fix (XS):** change to `code: 'VISIT_ARCHIVED'` and update the header doc comment to list both codes.

### A11 — Tab badge count jumps when archived toggle is switched
**Severity:** MEDIUM (UX)
**Location:** `apps/transcribe-md/src/app/dashboard/page.tsx` + documented in Commit 9 comments

The design decision was explicit (`visitCount` stays archive-exclusive to avoid jumpy UI). Current behaviour can still feel weird: toggle on → tab says "7 visits" but the grid shows 12 cards. Doctor may do a mental double-take.

**Fix (S):** either rephrase the badge copy ("7 active") or have the badge flicker to "7 + 5 archived" when the toggle is on.

### A12 — No in-app discovery of trashed-visits-only URL for archived patients
**Severity:** MEDIUM (UX discoverability)
**Location:** `/patients/[id]?tab=trash` pattern from T-M17.3 Commit 8

The Trash tab on patient detail only surfaces for patients with ≥1 trashed visit. If a doctor wants to see trashed visits across ALL patients, no UI exists. Scenario: doctor trashes a patient entirely (soft-deletes the patient row), all of that patient's visits live on with `patientName` set but the patient is hidden from the dashboard. The trashed-state of those visits becomes invisible.

**Fix (M):** add a global trash view at `/dashboard?tab=trash` or similar. Lower priority for a solo-doctor pilot where the patient population is small.

### A13 — Cleanup cron has not yet fired for the first time
**Severity:** MEDIUM (verification gap, not a bug)
**Location:** live system

At audit time, 3 abandoned-QUEUED visits (all 24+ hours old) are sitting in the DB. BullMQ repeatable key shows the next fire at `2026-04-21 03:00 UTC` (~19 min from audit write). End-to-end cleanup behaviour has therefore NOT been observed in production yet. If the cron fails silently (BullMQ worker dies, SQL timeout, …), nobody will notice until operational muscle memory detects the stuck rows.

**Fix (XS-S):** after the first fire completes, re-query the stuck visits to confirm deletion + check `cleanup:abandoned-queued` log lines. Optionally add a health-check side-signal: write a `last_ran_at` timestamp somewhere readable by `/api/health` so a silently-failing cron is visible.

---

## LOW (tech debt + polish)

### A14 — Rate limiter is process-local (documented limitation)
**Location:** `lib/rate-limit.ts:19-23`. Buckets don't cross containers, reset on worker restart. Known + acceptable at single-VPS scale. Note for when we horizontally scale.

### A15 — `/api/health` version string stale (`T-M16.3`)
**Location:** `app/api/health/route.ts:37`. We've shipped T-M17.1, T-M17.2, T-M17.3 since. **Fix (XS):** bump to `T-M17.3`.

### A16 — Stale comment in reset-password says "no rate limiting"
**Location:** `app/api/auth/reset-password/route.ts:7-11`. Comment contradicts the code, which DOES apply `AUTH_EMAIL` at line 55. **Fix (XS):** delete the outdated comment.

### A17 — `console.error` calls with raw `err` in lib files
**Location:** `lib/edit-tracking.ts:133`, `lib/nextauth.ts:64/102/125`, `lib/deliveries.ts:39`, `lib/queue.ts:25`. Most are low-PHI-risk (auth errors, redis errors, delivery metadata) but `edit-tracking.ts:133` runs inside the sign-capture path and has access to `originalSoap` in scope. **Fix (XS each):** add `redactPhi(err...)` wrapping. Same pattern as route-level fixes.

### A18 — NextAuth unverified-user timing side-channel
**Location:** `lib/nextauth.ts:78-80`. Unverified accounts early-return null without bcrypt; verified accounts run bcrypt (~100ms). Attacker measuring response time can detect "email exists + unverified". Very low value — attacker still can't log in — but trivial to fix. **Fix (XS):** run a no-op bcrypt.compare against a dummy hash before the early-return to equalize timing.

### A19 — `change-email` leaks email-taken via logged-in attacker
**Location:** `app/api/settings/change-email/route.ts:103-120`. A logged-in user can fish for "is X@Y a registered email" by attempting to change their own email to X@Y. Response distinguishes the taken case from the success case. Minor — requires a valid session to exploit. **Fix (XS):** return the same 202/pending response in both cases and surface nothing to the current user until they actually click the (never-sent) confirm link. Slightly more complex UX-wise; worth revisiting if/when the vector matters.

### A20 — loginAction bcrypt pre-check is a minor timing side-channel for unverified accounts
**Location:** `actions/auth.ts:135-170`. Similar to A18. **Fix (XS):** same pattern — dummy bcrypt.compare for non-unverified paths.

### A21 — Status route doesn't return `deletedAt`/`archivedAt`
**Location:** `app/api/visits/[id]/status/route.ts:60-70`. A stale polling UI on a visit that was trashed in another tab will keep showing the old state. **Fix (XS):** include the two fields in the response; UI redirects to /dashboard on observing a non-null value.

### A22 — Profile settings accepts a specialty field that is never persisted
**Location:** `actions/profile.ts:42-46` + `app/settings/page.tsx`. The doctor's typed specialty is silently discarded (no `User.specialty` column). **Fix (XS or S):** either hide the input in the UI, or add the column + migration to actually persist it.

### A23 — Missing index on `(userId, deletedAt, archivedAt)` for dashboard
**Location:** schema.prisma + `transcribe_visits_userId_createdAt_idx`. Current index handles the sort key; filter on deletedAt/archivedAt becomes a post-filter. At ≥1000 visits/user, this matters. **Fix (XS):** add the composite index next time you touch the schema.

### A24 — No index on `deletedAt` alone for stale-trash sweep
**Location:** same file. The 15-day sweep does a table scan on `deletedAt < cutoff`. At current scale <5ms. Becomes problematic at ~100k visits. **Fix (XS):** partial index `WHERE deletedAt IS NOT NULL` or a plain `deletedAt` btree.

### A25 — 110 stale `eval` + `judge` ai_calls rows from T-M15 testing
**Location:** DB — purposes `eval` (97) + `judge` (13) from 2026-04-17. Not written by prod code. Inert but noise in queries like "failure rate by purpose". **Fix (XS):** one-shot SQL delete.

### A26 — Retry route rate limit uses UPLOAD bucket (20/hr), peers use VISIT_OPS (30/hr)
**Location:** `app/api/visits/[id]/retry/route.ts:68`. Minor inconsistency — retry is closer to a delete/archive in frequency than an upload. **Fix (XS):** change to `VISIT_OPS`. Not urgent.

### A27 — Visit detail page's delete/archive buttons don't disable during pending POST
**Location:** `app/visits/[id]/visit-lifecycle-actions.tsx`. Individual buttons handle their own `pending` state internally — consistent UX. But the Delete dialog's confirm button during submission does NOT block the parent banner's Restore button if one is rendered. Narrow race; probably fine. **Fix (XS):** none urgent.

---

## INFO (observations, no action needed)

### A28 — Scribe legacy references in 7 files
Comments + Dockerfile text. Nothing working; documentation rot only. Clean up during a future doc-sprint milestone.

### A29 — Meddoc-pro CRM `Patient` vs TranscribeMD `TranscribeMdPatient` — correctly separated
No cross-referencing. Verified.

### A30 — T-M17.1 `errorDetails` observability is working
Live DB: 5 failed rows post-T-M17.1 all have `errorDetails` populated. 12 pre-T-M17.1 failed rows correctly have NULL (predate the column).

### A31 — T-M17.3 stale-visit cron scheduled + waiting for first fire
Redis key `bull:transcribe-md-cleanup:repeat:stale-visit-cleanup` exists. Next fire: `2026-04-21T03:00:00Z`. 3 abandoned visits waiting for sweep. NOT a bug (cron just hasn't fired yet); listed for post-fire verification.

### A32 — No orphan visits, no missing patient FKs, no missing practice FKs
Live DB confirms clean referential integrity.

### A33 — 8 patients, 0 with DOB populated (all from backfill)
As expected post-backfill — DOB was a new-visit-flow addition. The UI correctly surfaces "No DOB on file" for these legacy records.

### A34 — Automation layer failure rates are within retry-coverage tolerance
- `tm_entities` 57% fail / 43% ok (8 fail, 6 ok) — all recoverable by T-M17.1 retries
- `tm_cpt_coding` 45% fail — same
- `tm_icd_coding` 57% fail — same
- All terminal visits reached READY or SIGNED, confirming end-to-end retry efficacy

---

## Regression check vs T-M15 audit

Every T-M15 finding marked resolved in `docs/T-M15-AUDIT-REPORT.md` still holds:

| T-M15 finding | Status now | Note |
|---|---|---|
| C1–C8 (CRITICAL: docs/HIPAA/email) | ✅ Resolved | Shipped in T-M16.1/16.2 |
| H1–H7 (HIGH: security hardening) | ✅ Resolved | Shipped in T-M16.3 |
| H8–H13 (HIGH: infra + UX) | ✅ Resolved | Shipped in T-M16.4 |
| KI-1 (Cardiology SCHEMA_FAIL) | ✅ Resolved | T-M17.1 retries caught real incidents |
| KI-3 (Abandoned QUEUED) | ⏳ Resolved-pending | Cron scheduled, first fire 19 min from audit. Confirm post-fire. |
| KI-2 (Patient case-variant duplicates) | ⏳ Open | Explicitly deferred to T-M18+ merge-patients milestone |
| [3.1] Practice retention fields unused | ❌ Still open | Reclassified as **A3 HIGH** in this audit — HIPAA posture matters for pilot |

---

## Suggested fix batching

**T-M18.1 — Pre-pilot compliance (before any real doctor)** — 4 HIGH items, ~1 day total
- A1: `redactPhi` wrap in `withApiHandler` catch (XS)
- A2: scrub `reviewReason` + dual-message pattern (S)
- A3: retention enforcement sweep OR hardcoded 90d audio purge (M; stopgap S)
- A4: upload status allowlist (XS)

**T-M18.2 — Post-pilot polish** — 9 MEDIUM items, ~2–3 days
- A5 (AccountDeletion purge cron)
- A6 (denorm drift one-shot SQL)
- A8 (UI-side error-message mapping)
- A9 (re-upload orphan cleanup)
- A10 (error code label fix)
- A11 (tab badge copy)
- A13 (cron observability)
- (Defer A7 + A12 to when they matter at scale)

**T-M18.3 — Tech debt sweep** — 14 LOW items, ~1 day if batched
All XS fixes, mostly documentation/labels/indexes. Good cleanup milestone for a quiet week.

---

## Areas NOT fully covered in this audit

Honest disclosure of audit gaps:

1. **Worker layers L1, L2, L5, L6, L7a–e**: read only L4 in detail. L3 behaviour was covered via the T-M16.4 / T-M17.1 live-incident evidence already in `KNOWN_ISSUES.md`.
2. **React client components** (`components/*.tsx`, page-level UI): no detailed audit of accessibility (aria, keyboard focus traps, color contrast). Quick grep shows `aria-hidden`, `aria-pressed`, `aria-label`, `focus-visible:ring` usage throughout, so baseline hygiene exists — but I did not verify every Dialog has proper focus management or every dynamic region has `aria-live`.
3. **Mobile/responsive behaviour**: Tailwind `sm:` / `lg:` prefixes are used but I did not trace every layout on a narrow viewport.
4. **Email content**: I read the sender functions; I did not render the HTML in a browser or test it against email client rendering.
5. **Playwright E2E test suite state**: known to have a pre-existing `2-voice-dictation.spec.ts` typecheck error. Not exercised.
6. **Sentry + worker-sentry wiring**: I relied on T-M16.3 audit evidence; did not re-verify redactPhi flow through `beforeSend`.
7. **Meddoc-pro CRM app**: out of scope per user direction.

If any of these become load-bearing, a follow-up targeted audit is cheap.

---

## Ready for pilot?

**Yes, conditional on A1–A4 being patched first.** The T-M16 through T-M17.3 work is mature, cohesive, well-tested at the observability layer, and ergonomically sound. The four HIGH findings are localised and quick to fix — none requires architectural change. Once patched, I'd rate this system at 8.5/10 for real-doctor pilot readiness, with the remaining 1.5 points split between MEDIUM items that surface only under scale + a couple of UX rough edges.

Good work on T-M17.2 and T-M17.3 especially — the patient-first dashboard, trash flow, and lifecycle state machine held up to every edge case I could construct.
