# app.quillmd.com — Deep-Hunt Audit Report

**Auditor:** Claude Opus 4.7 (Claude Code session)
**Date:** 2026-04-24
**Branch:** `audit/app-deep-hunt`
**Target:** `app.quillmd.com` only (TranscribeMD)
**Method:** authed Playwright crawl + targeted API probes against prod.
**Scope envelope:** every authed page, every visit detail tab, every CRUD path on /patients, settings flows, edge cases (special chars, race conditions, mobile viewport), status-transition + lifecycle probes.

---

## Up-front: did I find the bug you know about?

**Honest answer: I don't know.** I cannot tell from the outside which specific bug you're holding back, and the user-facing flows I tested behaved as the code suggests they should. The findings below are all real, but several are LOW or INFO. I haven't burned the full budget — the gaps I haven't reached are listed under "Not exhausted" so you can redirect me.

---

## Bugs found

### B1 — `/api/visits/[id]/retry` accepts READY visits and re-runs the pipeline
**Severity:** MEDIUM (cost / accidental data churn)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/retry/route.ts:97-109`

Live-confirmed: POSTed to `/api/visits/cmodivx6o000201mqi5whp7d5/retry` while the visit was `status=READY`. Response: `200 {"ok":true}`. The route flipped status back to QUEUED, cleared `processingFinishedAt`, and enqueued a fresh BullMQ job. The worker re-ran (DB `updatedAt` advanced), then transitioned back to READY. T-M13's resume logic skipped layers whose output columns were populated, so my doctor-edit marker on `soapFinal` survived — BUT this only holds because the resume logic happened to align. Any layer whose input changed would re-run and overwrite.

Cost angle: on a real audio_upload visit a /retry would re-run Deepgram + every AI layer that didn't write a sentinel column, racking up cents-to-dollars per click. Combined with the per-user UPLOAD bucket being limit-30/hr (`VISIT_OPS`), a stuck-button user could fire ~30 retries/hour on the same visit.

Risk angle: a doctor who clicked retry by mistake (UI error-card shows the option after a stale visit) on a READY visit they had been editing risks losing edits if a future T-M13 invariant breaks.

**Recommended fix (S):** add `READY` to the rejected statuses with code `ALREADY_READY`. Surface a "regenerate from raw input" feature behind an explicit destructive-confirm if regeneration is a real user need.

---

### B2 — UNSIGNED visits export to PDF/DOCX with content visually identical to a signed export
**Severity:** LOW–MEDIUM (clinical workflow / chain-of-custody)
**Location:** `apps/transcribe-md/src/app/api/visits/[id]/export/pdf/route.ts`, `apps/transcribe-md/src/lib/pdf-generator.ts:204,664`

Live-confirmed: `GET /api/visits/cmodivx6o…/export/pdf` while the visit was `status=READY` (not SIGNED) returned `200` with a `41636-byte application/pdf` body. The DOCX endpoint similarly returned `200` with a 13873-byte file.

The PDF generator does signal the unsigned state — the footer reads `"Not yet signed."` instead of the signed-by line, and the header status cell is omitted. But the body of the SOAP and every Rx/Codes section renders the same. A doctor who downloaded an unsigned PDF for a quick preview, attached it to a referral by mistake, and didn't notice the small grey footer line could end up sharing a not-locked clinical note.

This isn't a security bug — the caller still owns the visit and the gate is auth-correct — but it's a chain-of-custody concern for HIPAA review. The DOCX render likely doesn't watermark either.

**Recommended fix (S):** when `data.signedAt === null`, draw a diagonal "DRAFT — NOT SIGNED" watermark across each PDF page; for DOCX, prepend a "DRAFT" header paragraph. Cheap, hard to miss.

---

### B3 — `signVisitAction` server action is exported but no longer wired up
**Severity:** LOW (code hygiene; not currently exploitable)
**Location:** `apps/transcribe-md/src/actions/soap.ts:71-122`

The action is the pre-T-M7 sign path. The new POST `/api/visits/[id]/sign` route's header comment explicitly says "Replaces the old T-M4 signVisitAction". The action is still `'use server'` exported. **It is NOT in the compiled server-action manifest** (verified by grepping `/app/.next/server/server-reference-manifest.js`) — Next.js compiled it out because no client component imports it, so an attacker cannot invoke it today.

The risk is **forward**, not present: a future PR that imports it (even by accident, e.g. autocompleted `import { saveSoapDraftAction, signVisitAction }`) would expose a sign path that **does NOT enforce F5-1 (Rx override audit)**. The action checks status / ownership / soapFinal-non-empty and flips to SIGNED, but never reads `rx_warning_overrides`.

**Recommended fix (XS):** delete `signVisitAction` from `actions/soap.ts`. It's documented dead code.

---

### B4 — React error #418 (hydration mismatch) on `/patients` for unusual unicode
**Severity:** LOW (reliability; potentially masks real bugs)
**Location:** `apps/transcribe-md/src/app/patients/page.tsx` + `patients-list-client.tsx`

While probing for XSS I created patients with Arabic, emoji, and `<script>` payloads in the name. The XSS itself is properly escaped (verified — alert never fires, `window.__IMG_XSS` never sets, no literal `<script>` tags in HTML). But every navigation to `/patients` while those rows existed produced a console pageerror:

```
Minified React error #418; visit https://react.dev/errors/418?args[]=text&args[]=
```

That's the hydration-text-mismatch error. It seems triggered by the SSR-encoded characters not matching whatever the client recomputes — most likely the `PatientCard` component or the search-filter path doing case-folding / locale-aware operations differently between server (Linux Node) and client (Chromium V8).

It's not a security bug, but every error page reload incurs a partial client-side re-render and lights up Sentry. If a real user has a patient named with a Vietnamese name + diacritics, expect to see #418 fire on their dashboard.

**Recommended fix (M):** narrow down the mismatch — likely a `.toLowerCase()` / `.normalize()` boundary issue. Run `next build` with `experimental.reactProductionProfiling=true` and reproduce locally with the unminified error to see which subtree mismatches.

---

### B5 — `reassignSpeakerAction` writes session email into stored audit string
**Severity:** LOW (light info-disclosure if exported)
**Location:** `apps/transcribe-md/src/actions/soap.ts:142`

```ts
reasoning: `Manually reassigned by ${session.user.email}.`,
```

This `reasoning` value goes into `transcribe_visits.speakerMap` JSONB. Today the visit detail UI displays it only to the visit owner, but if `speakerMap` ever gets included in the patient export ZIP (the `/api/patients/[id]/export` route already pulls full visit blobs) the doctor's email leaks into a downloadable artefact. The export is currently filtered to caller's userId, so it leaks the caller's own email back to themselves — not exploitable. But it makes the speakerMap less PHI-safe than its callers might assume.

**Recommended fix (XS):** store `overriddenBy: session.user.id` instead of email-in-reasoning, mirroring the `rx_warning_overrides.overriddenBy` foreign key pattern.

---

### B6 — `/visits/new` POST without a valid Server-Action header floods the server log with 500s
**Severity:** LOW (log spam; benign)
**Location:** Next.js server-action handler default

POST to `/visits/new` without the right `Next-Action: <id>` header returns `HTTP/2 500` (eight identical attempts in one second produced eight `500`s in the Playwright run). The container log fills with:

```
⨯ Error: Failed to find Server Action. This request might be from an older or newer deployment.
```

Cause is documented Next.js behaviour: any POST to a page route is interpreted as an attempted action invocation, and unknown action IDs throw a 500. After a deployment, browsers with stale bundles will fire these naturally.

**Recommended fix:** none on the app — this is upstream Next.js. Worth keeping a Sentry filter so the noise doesn't drown real errors.

---

### B7 — Patient list `visitCount` aggregate still includes other doctors' visits at the same practice
**Severity:** LOW (re-affirmed from prior audit F8-1)
**Location:** `apps/transcribe-md/src/app/api/patients/[id]/route.ts:72-79`

The detail GET aggregates `transcribeVisit` filtered only by `patientId / deletedAt / archivedAt` — no `userId`. Doctor A sees aggregate counts that include Doctor B's visits, while the `/export` endpoint does filter by `userId`. Inconsistent. Documented in the prior `audit-pipelines-report.md` as F8-1; flagging again because no fix shipped.

---

## Probes that were CLEAN

These are explicit "tested, no bug" notes — not dead air.

| Probe | Result |
|---|---|
| GET another user's signed visit (IDOR) | `404` on `/api/visits/<otherUser>` and `/status` and `/progress` — anti-enumeration ✓ |
| GET another user's visit `/export/pdf` / `/export/docx` / `/dictation/audio` | `404` ✓ |
| PATCH another user's patient cross-practice | `404` ✓ |
| POST `/text` after first text submitted | `409` ✓ |
| POST `/upload` on a `text_notes` visit | `400 "this visit does not accept audio uploads"` ✓ |
| POST `/text` on SIGNED | `409` ✓ |
| POST `/upload` on SIGNED | `400` ✓ |
| POST `/dictation/upload` on SIGNED | `400` ✓ |
| PATCH visit on SIGNED | `400 VISIT_NOT_DRAFT` ✓ |
| POST `/export/email` to attacker addr (regression for #58) | `403 INVALID_DESTINATION` ✓ |
| Concurrent triple POST `/text` | all three `409` (no double-submission) ✓ |
| Patient name = `<script>alert(1)</script>` | escaped at render — no alert fired, no `<script>` in DOM ✓ |
| Patient name = `<img src=x onerror=…>` | escaped — `window.__IMG_XSS` never set ✓ |
| Patient name = SQL injection (`Bobby"; DROP TABLE …`) | stored verbatim in safe ORM, no escape errors, no rows dropped ✓ |
| URL probe `/visits/' OR 1=1 --` | `404` ✓ |
| `/dev/rx-warnings` | `404` in production ✓ |
| Forgot-password while logged-in | `200` generic anti-enum response ✓ |
| Re-sign already-signed visit | `200` idempotent ✓ |
| Restore non-trashed visit | `200 alreadyActive` ✓ |
| Archive a non-SIGNED visit | `400 VISIT_NOT_SIGNED` ✓ |

## Smoke-on-prod after this audit

Smoke + product-separation matrix re-run after the deep hunt: still 13/13 + 12/12. Prior PRs not regressed by the Playwright traffic.

---

## Not exhausted (where to point me next)

Areas I deliberately under-tested because of cost / time:

1. **`voice_dictation` end-to-end flow** — needs a real mic permission grant and the MediaRecorder bytes; chromium-headless doesn't reliably surface a permission UI we can scriptedly accept. I exercised the `/dictation/upload` rejections from the API surface but never *submitted* a real dictation. If the bug lives in the voice-record-and-resubmit corner, this is where I'd dig next.
2. **`audio_upload` end-to-end with a real audio file** — Deepgram cost would be ~$0.45 per real-length file plus Anthropic per layer. Skipped per budget. The `/upload` route's 500 MB ceiling, MIME allowlist, and ownership gate I covered statically + via empty-body 4xx probes.
3. **The `Pipeline` tab** — the env flag `NEXT_PUBLIC_SHOW_PIPELINE_TAB` is `false` in prod, so the tab never renders. If it were turned on for a debug session it'd be worth a separate sweep.
4. **Real signing flow via the modal UI** — my browser script kept hitting the modal trigger as just `Sign & Send`, but the SpecularButton wrapper tripped my `getByRole('button', { name: /^sign/i })` selectors because the trigger isn't a `<button>` directly. Verified the underlying `/sign` POST is gated correctly (F5-1, F9-1, PHI-exfil blocks all in place); the UI modal itself wasn't end-to-end driven.
5. **Browser back-button / cache-stale views after sign** — would need a multi-tab playwright fixture; partially covered by reload-after-edit (B3 verified persistence).
6. **Two-tab concurrent SOAP edit** — the SoapEditor uses `revalidatePath` after save but no optimistic-locking version; "last writer wins" silently. Probable bug worth confirming with two playwright contexts; I didn't end up driving that scenario.

---

## Evidence artefacts (committed alongside this report)

```
audit-evidence/app-deep-hunt/
├── scripts/        # 8 playwright scripts, one per phase
├── screenshots/    # 59 screenshots covering each interaction
└── logs/           # JSON findings + transition timelines + raw HTML snapshots
```

QA test patient cleanup: 5 special-char patients I created during XSS probing were deleted from the QA practice on completion. The remaining `Deep Hunt Patient modiv5tv` and the visit `cmodivx6o000201mqi5whp7d5` (now `SIGNED`, with my `[DEEP_HUNT_…]` SOAP marker preserved) are intentional fixtures left behind for any subsequent regression.
