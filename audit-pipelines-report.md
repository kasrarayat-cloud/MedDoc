# Authed-Pipelines Audit Report

**Auditor:** Claude Opus 4.7 (Claude Code session)
**Date:** 2026-04-24
**Branch base:** `audit/authed-pipelines` (up to `a878150`)
**Production at time of audit:** `main` @ `d2e463c`
**Target:** `app.quillmd.com` (transcribe-md), `pro.quillmd.com` (meddoc-pro)
**Method:** static review of API routes / server actions + live HTTP probes + read-only SQL against prod DB. One state-mutating probe (an already-READY visit signed without delivery destinations) — documented in F5-1 below.

---

## Tests completed

| # | Area | Status | Bugs found |
|---|---|---|---|
| 1 | audio_upload pipeline | ✅ | 2 |
| 5 | Rx safety | ✅ | 4 |
| 6 | Realtime voice | ✅ | 4 |
| 7 | PHI email-exfil (prior session, deployed pre-audit as #58) | ✅ | — already fixed and verified live |
| 8 | Patient subtabs | ✅ | 1 |
| 9 | Cross-flow architecture | ✅ | 1 |

Tests 2, 3, 3b, 3c, 4 are from earlier audit rounds (text_notes / critical / edge / flow — artifacts in prior `audit-evidence/pipelines/logs/` and `screenshots/` on `main`).

---

## Severity summary

| Severity | Count | Notes |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 2 | F5-1 (clinical audit integrity, live-confirmed), F9-1 (entitlement bypass) |
| MEDIUM | 5 | F1-1, F5-2, F5-4, F6-1, F6-2 |
| LOW | 3 | F1-2, F5-3, F8-1 |
| INFO | 2 | F6-3, F6-4 |

No further PHI-exfil class bugs found.

---

## HIGH findings

### F5-1 — Sign endpoint does not enforce Rx warning override audit
**Severity:** HIGH (clinical audit integrity, HIPAA audit trail)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts`, `apps/transcribe-md/src/lib/rx-warning-audit.ts`
**Status:** LIVE-CONFIRMED on prod.

**Claim:** A doctor can sign a visit containing `critical` Rx warnings without ever invoking `recordOverride`. The override audit table (`rx_warning_overrides`) is a UI-enforced honor system — the server-side `/sign` path neither reads nor requires a matching override row before flipping `status → SIGNED`.

**Evidence (static):** `/sign` route inspects only `soapFinal`, `status`, `deletedAt`, `archivedAt`. It never queries `RxWarningOverride`, and `rxWarningOverride` appears nowhere in the sign path. `recordOverride` is only called from `components/rx/override-confirm-modal.tsx`, which the UI drives on doctor click.

**Evidence (DB):**
```sql
SELECT
  (SELECT COUNT(*) FROM transcribe_visits WHERE status='SIGNED') AS signed_visits,
  (SELECT COUNT(*) FROM rx_warning_overrides) AS override_records,
  (SELECT COUNT(*) FROM transcribe_visits
    WHERE status='SIGNED' AND "rxDrafts"::text LIKE '%critical%'
  ) AS signed_with_critical_warnings;
--   16       0        7
```

7 of 16 prod SIGNED visits (44%) contain a critical Rx warning. Zero override rows exist. Either the override UI never fires, the doctor always dismisses, or the sign path is being hit without the modal — in all three cases the audit record is empty.

**Evidence (live):** QA-user visit `cmocm5bt6000301kwvo1arr1x` (status READY, 1 critical + 3 minor warnings) signed via:
```
POST /api/visits/cmocm5bt6000301kwvo1arr1x/sign  body: { destinations: [] }
→ 200 {"signedAt":"2026-04-24T16:35:33.410Z","clipboardTexts":{},"emailQueued":false}
```
Post-state: `rx_warning_overrides` count still = 0, visit now SIGNED. The bypass is real, not hypothetical.

**Why this matters:** The DESIGN_SPEC §4.1 makes the override flow a clinical safety & audit requirement. An empty override table in production means either (a) doctors aren't interacting with the modal, or (b) the modal is being skipped by UI/API flow. Without server enforcement, a HIPAA audit can't distinguish "doctor acknowledged the warning" from "doctor never saw it."

**Recommended fix (S):** In `/sign`, before the `status: READY → SIGNED` transition:
1. Parse `rxDrafts.warnings[]` for `severity === 'critical'` entries.
2. For each, require a matching `rx_warning_overrides` row with `visitId` + `warningId`. Emit `409 OVERRIDE_REQUIRED` with the missing warningIds otherwise.
3. Preserve the UI flow (modal still drives the override) but make server the source of truth.

Alternative (M): treat the 7 existing bypassed signs as back-fillable — add a `{visitId, signedAt}` index and a one-shot migration that marks them with a synthetic override labeled "legacy-pre-enforcement" so the audit trail is at least explicit.

---

### F9-1 — Transcribe-MD login auto-grants TRANSCRIBE_MD product entitlement
**Severity:** HIGH (entitlement / billing bypass)
**Location:** `apps/transcribe-md/src/lib/nextauth.ts:136-148`

**Claim:** Any user with a valid `users` row (across both products) who authenticates against `app.quillmd.com` is automatically granted `Product.TRANSCRIBE_MD` in their `products[]` array on first login. There is no separate entitlement check, billing gate, or admin approval.

**Evidence:**
```ts
// apps/transcribe-md/src/lib/nextauth.ts:136-148
const hasTranscribeMd = user.products.includes(Product.TRANSCRIBE_MD);
await prisma.user.update({
  where: { id: user.id },
  data: {
    lastLogin: new Date(),
    failedLoginCount: 0,
    lockedUntil: null,
    ...(hasTranscribeMd
      ? {}
      : { products: { push: Product.TRANSCRIBE_MD } }),
  },
});
return { id: user.id, email: user.email, ... };  // login succeeds regardless
```

The comment is explicit: *"grant TranscribeMD product access to pre-existing MedDoc Pro users who are signing in here for the first time."* No business logic is gating the grant.

Downstream, no API route in `apps/transcribe-md/src/app/api/**` checks `user.products`. The auth-time auto-grant is effectively the only enforcement point, and it grants rather than checks.

**Current prod user breakdown:**
```
{MEDDOC_PRO}               → 10 users (haven't logged into transcribe-md yet — they'd be upgraded on first login)
{MEDDOC_PRO,TRANSCRIBE_MD} →  2 users (already used both)
{TRANSCRIBE_MD}            →  4 users
```

**Why this matters:** If TRANSCRIBE_MD is ever priced separately from MEDDOC_PRO (or plans include only one product), this code silently grants the more expensive product on login. It's also a concern for role separation: a practice's billing admin may only want `DOCTOR` users on transcribe-md, but login alone extends access.

**Recommended fix (S):** Replace the auto-grant with a 403 redirect to a "Contact your practice admin to enable TranscribeMD" page. Entitlement grants should go through an explicit admin surface or a billing webhook.

Alternative (XS): if this is the product team's intent (unified SSO, all users of both apps), delete the conditional and document it — leaving "grant if missing" in the auth path reads as a grace-period hack that will outlive its intent.

---

## MEDIUM findings

### F1-1 — Upload endpoints rate-limit per-user only, not per-IP
**Severity:** MEDIUM (cost abuse)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts:63`, `.../dictation/upload/route.ts:56`, `.../text/route.ts:42`

Per-IP rate limiting helpers (`clientIpFromHeaders`) exist in `lib/rate-limit.ts` and are used by signup/login actions, but not by the three pipeline-kickoff endpoints. With the 500 MB upload cap × Deepgram @ $0.0145/min, a single IP running multiple auth'd accounts can still drive meaningful spend (20 uploads/hr/user × N accounts from one box). Signup is per-IP 5/hr, so account-multiplication is slow but not impossible.

**Recommended fix (XS):** add a second `rateLimitOr429` call using `clientIpFromRequest(req)` as the identifier, with a tighter per-IP limit (e.g., 30/hr across all pipelines). Belt-and-suspenders with the per-user bucket.

---

### F5-2 — `recordOverride` stores client-supplied `severity` / `headline` verbatim
**Severity:** MEDIUM (audit integrity)
**Location:** `apps/transcribe-md/src/lib/rx-warning-audit.ts:80-100`

The `recordOverride` server action persists `input.severity`, `input.headline`, and `input.warningId` exactly as the caller sent them. A user who opens the devtools network panel and intercepts the server-action payload can relabel a `critical` warning as `info` before submitting. The audit row would then show a softer record than the warning the doctor actually saw.

This is not a privilege escalation (user is tampering with their own audit), but it defeats the clinical-safety intent of the log: a regulator reading `rx_warning_overrides` can't rely on `severity` to represent the actual warning the doctor overrode.

**Recommended fix (S):** reload the visit's `rxDrafts` in the action and re-derive severity/headline from the matching `warningId` rather than trusting the client copy. If the warningId doesn't exist in `rxDrafts.warnings[].id`, reject as invalid.

---

### F5-4 — Rx-drafting layer 7c uses SOAP-extracted allergies, not the patient's stored allergy record
**Severity:** MEDIUM (clinical safety — false negative on allergy warning)
**Location:** `apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts:135`, `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:89`

The layer-7c prompt sends `entitiesJson` to Claude, containing "current medications + allergies" — but those entities are parsed from the SOAP text by layer 3, not read from any structured patient record. If the doctor doesn't restate a known allergy in the SOAP, the LLM has no signal and won't emit an allergy warning.

There's no cross-check against `transcribeMdPatient.problemList` or an allergy subfield. The CRM side has a structured `allergies` table (the meddoc-pro app reads it), but the transcribe-md worker doesn't.

**Why this matters:** "Drug matches a documented allergy / known cross-reactivity" is literally the first example under `critical` in the layer 7c prompt. The warning relies on the doctor to re-document the allergy each visit.

**Recommended fix (M):** join `transcribeMdPatient.problemList` (or a new `allergies` JSONB) into the layer 7c input, and change the entities-based check to a deterministic "is drug on allergy list?" pre-pass that augments the LLM's warnings array instead of replacing it.

---

### F6-1 — Realtime-voice daily cap is in-memory, not persisted
**Severity:** MEDIUM (cost circuit-breaker is porous)
**Location:** `apps/meddoc-pro/src/lib/realtime/usage-cap.ts`

The `usage` Map lives in process memory and resets on meddoc-pro container restart. Its own comment admits this: *"Move to Redis when scaling beyond a single Node process."* No per-practice cap — only per-user.

On a VPS with a single meddoc-pro container, any deploy, OOM kill, or compose restart hands every doctor a fresh 120-min daily budget for the rest of the UTC day. OpenAI Realtime @ ~$0.56/min means ~$67/day per doctor per reset.

**Recommended fix (S):** move the counter to Redis with daily-TTL keys; add a per-practice cap (product decision on the number, but e.g. 500 min/day practice-wide).

---

### F6-2 — `/api/realtime/session/end` trusts client-reported `durationSeconds`
**Severity:** MEDIUM (cost-cap bypass)
**Location:** `apps/meddoc-pro/src/app/api/realtime/session/end/route.ts:45`

The endpoint clamps `durationSeconds` to MAX 8 hours but has no MIN. An attacker who runs a realtime session and closes the browser without calling `/end`, or who calls `/end` with `durationSeconds: 1`, never burns the cap. The server doesn't meter the WebRTC channel (audio goes browser ↔ OpenAI directly), so the client's self-report is the only signal.

Combined with F6-1 (in-memory cap resets on restart) the effective cost ceiling per user is "up to OpenAI's own rate limiting, per restart." Not catastrophic for a solo-doctor VPS, but worth a line item.

**Recommended fix (S):** record the ephemeral-token issuance timestamp server-side when `/session` mints a token; on `/end`, compute `Math.min(client_reported, now - issued_at)`. Also accept a missed `/end` and passively close sessions older than the token TTL (the ephemeral token already expires ~1 min after issuance, so practical session length is capped by how often the client refreshes).

---

## LOW findings

### F1-2 — No per-practice upload quota
**Severity:** LOW (operational / cost)

A practice with 10 doctors has no aggregate upload cap beyond the sum of per-user buckets (200 uploads/hr practice-wide). A legitimate practice running a stress-test or a run-away automation script can cost meaningful Deepgram spend with no platform guard.

**Recommended fix (S):** add a per-practice bucket with e.g. 100 uploads/hr at the practice level, independent of the per-user.

---

### F5-3 — `DEV_PREVIEW_VISIT_ID` sentinel bypasses auth in `recordOverride`
**Severity:** LOW (code hygiene — no exploitable side effect today)
**Location:** `apps/transcribe-md/src/lib/rx-warning-audit.ts:38,69`

When `input.visitId === 'dev-preview'`, `recordOverride` returns `{ok: true, auditId: 'dev-preview-audit'}` without session check or DB write. Harmless today (no mutation), but the sentinel is reachable from any signed-in user, and if a future refactor adds side effects before the guard, this becomes a vulnerability by accident.

**Recommended fix (XS):** gate on `process.env.NODE_ENV !== 'production'` OR on a feature flag. The `/dev/rx-warnings` preview route that relies on this sentinel isn't reachable in prod anyway.

---

### F8-1 — Patient detail `visitCount` / `lastVisitAt` aggregate across all doctors in practice
**Severity:** LOW (minor info leak — works-as-designed for the multi-doctor practice model)
**Location:** `apps/transcribe-md/src/app/api/patients/[id]/route.ts:72-79`

`GET /api/patients/[id]` returns aggregate counts for ALL visits on the patient, not filtered by caller userId. In a multi-doctor practice, Doctor A can see "this patient has 10 visits" when only 2 are theirs. The `/export` endpoint, in contrast, filters by userId. Inconsistent.

Not a security bug — same-practice doctors do share patient identity — but worth flagging if the product intends doctor-scoped visit visibility.

---

## INFO

### F6-3 — No rate limit on `/api/realtime/*` endpoints
Session creation relies on the daily voice-minutes cap as its sole throttle. A burst of /session POSTs (e.g., a buggy client retrying) isn't rate-limited. Low severity because each session creation burns a trivial amount of OpenAI budget until someone actually uses the returned token.

### F6-4 — PHI flows to OpenAI Realtime in `buildSystemPrompt`
The system prompt sent to OpenAI includes patient allergies, medications, clinical notes, and trajectory. Assumed to be covered by the OpenAI BAA (the `BAA_CHECKLIST.md` in this repo lists OpenAI as a BAA vendor). No code change; just a reminder that this surface is in scope for BAA review any time the prompt template changes.

---

## Clean areas (no findings worth flagging)

- **Data integrity (Test 8):** 0 orphaned visits; 0 cross-practice visits; `ON DELETE RESTRICT` on `transcribe_visits → transcribe_md_patients` prevents hard-delete of in-use patients.
- **Session boundaries (Test 9):** NextAuth default cookie config — `HttpOnly`, `Secure`, `SameSite=lax`, no `domain=.quillmd.com` override. `app.quillmd.com` and `pro.quillmd.com` do not share session cookies.
- **Patient-model separation (Test 9):** `patients` (CRM) and `transcribe_md_patients` are separate tables with no foreign key between them. `apps/transcribe-md` imports don't touch the CRM `Patient` model anywhere.
- **Upload endpoint hardening (Test 1):** auth + rate-limit + ownership + deleted/archived check + inputMode check + status allowlist (QUEUED/FAILED) + content-length cap + MIME allowlist + structured MinIO error classification. Was hardened by T-M18.1 A4; holds up to review.
- **Fuzzy-match SQL:** `prisma.$queryRaw` with parameterized template literals — no injection.

---

## API / cost footprint of this audit

- **Live HTTP probes:** 1 Playwright login + 1 POST to `/api/visits/.../sign` (F5-1 confirmation). No audio, no AI calls. Effectively $0.
- **Prior PHI-exfil verification (same session):** 1 legit email delivery to `qa-audit@quillmd.local` (Resend — cents, or bounced since `.local` isn't routable).
- **No `/api/realtime/*` exercise:** Test 6 was static-only to honor the budget guidance. A live probe of F6-2 would take one OpenAI session, ~$0.60/min.
- **Read-only SQL:** 12 local queries against the prod container — zero external cost.

Budget spent on AI/transcription this session: ~$0.01.

---

## Evidence file pointers

- Attack script (F5-1 confirmation): `/tmp/rx-bypass-test.mjs` (session-local, not committed)
- PHI-exfil regression test (prior session, already committed on main): `tests/automated/e2e/email-destination-guard.spec.ts`
- Smoke-test run with deployed PHI fix (prior session): `tests/automated/reports/2026-04-24-16-26.json`
- Deployed PHI fix: main @ `d2e463c`, image `dc547493d30b`

---

## Recommended action order

1. **F5-1** — HIGH clinical-audit integrity. S-sized fix on `/sign`. Do first.
2. **F9-1** — HIGH entitlement surface. Product decision first (SSO-by-default vs. paid entitlement), then either S-sized code fix or a comment + doc.
3. **F5-4** — MEDIUM clinical. M-sized but clinically meaningful; schedule alongside F5-1.
4. **F1-1, F6-1, F6-2** — MEDIUM cost. All S-sized, bundle in one "cost guardrails" PR.
5. **F5-2** — MEDIUM audit integrity. S-sized; can ship with F5-1.
6. **F5-3, F1-2, F8-1, F6-3, F6-4** — LOW/INFO. Absorb opportunistically.
