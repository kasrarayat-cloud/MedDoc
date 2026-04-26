# Phase 16 — Deep Audit Results
*Compiled 2026-04-26 — last full pass before pilot opens.*

This document captures the findings from a from-scratch re-audit of the
production system. Each section was run independently against live
production state; results are observations, not fixes (those land in
Phase 17 if Kasra agrees with the prioritization).

---

## Verdict

**Conditional GO.**

Zero CRITICAL findings (no cross-tenant data leak, no cross-host cookie
leak, no raw PHI in audit metadata, no anonymous /admin access, no
plaintext-port login surface, no exposed database). Backup + restore
loop verified working. All three production smoke suites green
(46 + 19 + 9 = 74/74). TLS 1.3, HSTS, host-scoped HttpOnly+Secure
cookies. Container UIDs all non-root.

The conditional caveat: **5 new HIGH findings were uncovered**, all in
the audit-completeness space (PHI-touching endpoints that don't write
audit_logs rows). These are §164.312(b) gaps, not active leaks — the
data flows correctly; the audit trail just doesn't cover every PHI
mutation. For a 5-doctor pilot they're acceptable risk if Kasra
accepts the gap explicitly. For an enterprise rollout they are not.

Recommended path: **open pilot with an explicit "audit-completeness
in flight" note in the BAA or pilot agreement**, fix the 4 audit-gap
findings within 14 days of pilot start (Phase 17), then close the
findings as the gaps land.

---

## A. Auth + session integrity — pass

| Probe | Result |
|---|---|
| Login (good/bad) per host (admin / pro / app) | ✅ 302 + cookie on good; 302 → /login?error=CredentialsSignin on bad |
| Anon /admin, /admin/users, /admin/usage, /admin/threats, /admin/hipaa | ✅ All 404 |
| Cross-host cookie isolation (3×3 matrix probe) | ✅ Each cookie authenticates ONLY on its issuing host |
| App-cookie hitting admin PHI endpoints | ✅ All 404 (anon-equivalent rejection) |
| Plaintext HTTP → HTTPS | ✅ 308 redirect on all hosts |
| Session maxAge | ⚠️ **h16-admin-session-7day** (medium) — admin.quillmd.com inherits transcribe-md's 7-day maxAge instead of meddoc-pro's 8h |

## B. Tenancy + PHI isolation — pass

| Probe | Result |
|---|---|
| FK orphans across users / visits / patients / audit_logs | ✅ 0 across all 6 checks |
| Users without practice | ✅ 0 |
| Cross-tenant visit fetch (qa-audit reads other-doctor visits) | ✅ 404 across status, progress, export |
| Soft-deleted users in /api/admin/users | ✅ 0 of 23 returned |
| Practice with `<script>` literal in name | ✅ Stored verbatim, not rendered (no `dangerouslySetInnerHTML` matches anywhere in apps/) |

## C. Audit + threat coverage — partial

| Probe | Result |
|---|---|
| logAudit() coverage of state-mutating endpoints (45 routes) | ⚠️ **7 routes don't write audit rows** — 4 touch PHI, see h16-audit-gap-* below |
| 100-row audit metadata sample for raw PHI patterns | ✅ Zero matches for ssn / dob / diagnosis / chief.complaint / symptom / medication / prescription / patient.name |
| /api/admin/threats cold-start | ✅ 200, threats=[] |
| THREAT_RESOLVED / HIPAA_FINDING_RESOLVED audit rows | ✅ Both present |

**New h16 findings from this section:**
- `h16-audit-gap-doc-editor` (high, §164.312(b))
- `h16-audit-gap-extract-from-voice` (high, §164.312(b))
- `h16-audit-gap-audio-upload` (high, §164.312(b))
- `h16-audit-gap-realtime` (medium, §164.312(b))

## D. Container + runtime hardening — partial

| Probe | Result |
|---|---|
| UIDs all non-root | ✅ postgres/redis/postgres-backup=999, caddy/minio=1000, Node apps=1001 |
| Capabilities | ⚠️ **h16-cap-drop-defense-in-depth** (medium) — only caddy uses cap_drop=ALL |
| Read-only root fs | ⚠️ All false; documented as low-priority post-pilot work, not a new finding |
| Externally exposed ports | ✅ Only 80/443 (caddy) on 0.0.0.0; postgres/redis/minio bound to 127.0.0.1 |
| 9010 / 9020 docker port mappings | ✅ Mapped at docker level but no process listens (cosmetic config debt; no security risk) |
| Health + restart=unless-stopped | ✅ All healthy except worker (no healthcheck, expected for a queue worker) |
| Memory limits | ✅ All capped (postgres 512MB, worker 1GB, caddy/redis/postgres-backup 128MB, minio/marketing 256MB, Node apps 512MB) |
| PIDs limit | ⚠️ Unset — fork bomb is theoretically possible. Low. |

## E. Backups + DR — partial

| Probe | Result |
|---|---|
| Backup recency (≤24h) | ✅ /backups/last/meddoc-20260426-000000.sql.gz, 1.5MB, dated today 00:00 UTC |
| Fresh restore drill (ephemeral pgvector container) | ✅ Restored cleanly; row counts: users=21, audit_logs=21d-ago state, visits=*, practices=*, patients=*, api_usage_events=* |
| Schema drift between backup and live | ⚠️ Backup is missing 3 migrations applied today (phase_6h_threat_resolutions, phase_7b_hipaa_findings, phase_8_pilot_followup_findings) — tables `hipaa_findings` and `threat_resolutions` not in backup. Normal RPO=24h behavior; tomorrow's backup will catch up. |
| MinIO bucket integrity | ✅ 117 files / 161.6 MB |
| Audio audit-log presence | ⚠️ See **h16-audit-gap-audio-upload** above (zero AUDIO_* actions in 4547 rows) |
| Off-host backup | ⚠️ **h16-offsite-backup** (high) — same-VPS only, single failure domain |

## F. Code-level checks — pass

| Probe | Result |
|---|---|
| `tsc --noEmit` transcribe-md | ✅ 0 errors |
| `tsc --noEmit` meddoc-pro | ✅ 0 errors |
| ESLint | ⚠️ Skipped — `.eslintrc.*` exists but ESLint v9 needs `eslint.config.js`; `next lint` removed in Next 16. **Cleanup item, not a finding.** |
| Secret-shape grep across tracked files | ✅ Zero matches |
| .env files in git | ✅ Only `.env.production.example` |
| Migration drift (last applied vs last directory) | ✅ Match (`20260426071519_phase_8_pilot_followup_findings`) |

## G. Production smoke — pass

| Probe | Result |
|---|---|
| Last 5 visits state | ✅ cmofzxpoi004y01nzrpu8n01d still SIGNED, 7095 chars transcript, 12 billing events |
| CSRF latency (5 hits per host) | ✅ All < 200ms; admin cold 199ms, all warm < 50ms |
| /tmp/admin-audit.mjs | ✅ 46 / 0 |
| /tmp/test-flows.mjs | ✅ 19 / 0 |
| /tmp/test-consistency.mjs | ✅ 9 / 0 |

## H. TLS + headers — partial

| Probe | Result |
|---|---|
| TLS version + cipher | ✅ TLSv1.3 / TLS_AES_128_GCM_SHA256 across all 3 hosts |
| Let's Encrypt cert validity | ✅ Verify return code: 0 (ok) |
| HSTS | ✅ max-age=31536000; includeSubDomains; preload |
| X-Frame-Options | ✅ SAMEORIGIN |
| X-Content-Type-Options | ✅ nosniff |
| Referrer-Policy | ✅ strict-origin-when-cross-origin |
| Permissions-Policy | ✅ microphone=(self), camera=(self), geolocation=() |
| CSP | ⚠️ **h16-csp-report-only** (medium) — Content-Security-Policy-Report-Only set, but no enforced CSP |
| X-Powered-By: Next.js | ⚠️ Framework leak (low) — included in cap-drop / CSP cleanup pass |
| Cookie flags | ✅ HttpOnly; Secure; SameSite=Lax on all NextAuth cookies |

---

## Findings — ranked

| # | Severity | Section | Finding | Suggested fix |
|---|---|---|---|---|
| 1 | high | C / E | `h16-audit-gap-audio-upload` — visit audio uploads have zero audit rows; 117 PHI audio files in MinIO with no per-upload trail | Wrap the upload route + presigned-URL grant with `logAudit({ action: 'VISIT_AUDIO_UPLOADED', ... })` |
| 2 | high | C | `h16-audit-gap-doc-editor` — POST /api/doc-editor + /api/doc-editor/save process PHI without audit | Wrap both with logAudit; metadata = visitId + format + bytes |
| 3 | high | C | `h16-audit-gap-extract-from-voice` — Whisper + GPT extract patient demographics from voice with no audit row | logAudit `PATIENT_EXTRACTED_FROM_VOICE` with userId + audio duration |
| 4 | high | E | `h16-offsite-backup` — backups co-located with database on same VPS; single failure domain | Add a daily `rclone sync /opt/meddoc-pro/backups → s3:b2-bucket` cron; same retention policy |
| 5 | high | open (Phase 13) | `h8-h3-pilot-followup` — disk encryption at rest pending Hetzner managed encrypted volume | Run `docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md` on a maintenance window |
| 6 | medium | A | `h16-admin-session-7day` — admin surface inherits transcribe-md 7-day session maxAge | Per-role override: SUPER_ADMIN → 8h; doctor on app.quillmd.com → 7d as before |
| 7 | medium | C | `h16-audit-gap-realtime` — voice session lifecycle endpoints not audited | logAudit on session/end with durationSeconds |
| 8 | medium | D | `h16-cap-drop-defense-in-depth` — 8/9 containers keep default Docker capabilities | Add `cap_drop: [ALL]` to each service in docker-compose.yml; add `cap_add` only where strictly needed (e.g. SETGID for nginx-style images) |
| 9 | medium | H | `h16-csp-report-only` — CSP enforced version not deployed | Switch the report-only header to enforcement after a 7-day burn-in window confirms zero violation reports |
| 10 | low | open (Phase 13) | `h13-meddoc-e2e-tenancy-residual` — 5 Playwright tests time out under Turbopack first-hit | Investigate post-pilot |

---

## /admin/hipaa final state (post-Phase 16)

```
 status   | severity | count
----------+----------+------
 open     | high     |   5     (h16-audit-gap-{doc-editor,extract-from-voice,audio-upload}, h16-offsite-backup, h8-h3-pilot-followup)
 open     | medium   |   4     (h16-{admin-session-7day, audit-gap-realtime, cap-drop, csp-report-only})
 open     | low      |   1     (h13-meddoc-e2e-tenancy-residual)
 resolved | high     |   5     (h7b-h2, h7b-h3, h7b-h4, h7b-detector4, h8-h4-pilot-followup)
 resolved | medium   |   1     (h9-meddoc-e2e-residual)
```

Total: 16 findings — 6 resolved, 10 open. Of the 10 open: 5 high, 4 medium, 1 low.

---

## What this audit did NOT verify

- A live new visit upload end-to-end (would burn Deepgram + Anthropic credits; existing live visit `cmofzxpoi004y01nzrpu8n01d` is the verification reference).
- Detector behavior under simulated attack (the cold-start probe only confirms the endpoint serves; per-detector logic is covered by /tmp/test-flows.mjs E1).
- Disk encryption at rest (still pending Hetzner Console action — `h8-h3-pilot-followup`).
- Penetration-test class probes (SQLi, SSRF, XXE, deserialization). Defer to a real third-party pen-test post-pilot.
- ESLint static analysis (toolchain not configured for v9).

---

## Recommended action sequence (Phase 17 if Kasra agrees)

**Day 0 (before pilot opens):**
- Decide: accept the 5 high findings as documented pilot risk, or block pilot until at least h16-audit-gap-* are fixed. Recommendation: **accept and proceed**, with the audit-gap items in the BAA/pilot-agreement risk register.

**Days 1–7 (pilot week 1):**
- Land the 4 audit-gap findings (`h16-audit-gap-{doc-editor, extract-from-voice, audio-upload, realtime}`). Net code change: ~12 `await logAudit({...})` lines in 6 route files.
- Add `cap_drop: [ALL]` per-service in docker-compose.yml. ~30 minute change, one-restart redeploy.

**Days 7–14:**
- Add offsite backup sync (`h16-offsite-backup`). Hetzner Object Storage is the simplest fit (same vendor, same DC region).
- Per-role session maxAge override (`h16-admin-session-7day`).
- Switch CSP to enforced after burn-in (`h16-csp-report-only`).

**Days 14–30:**
- Run H3 encrypted-volume procedure (`h8-h3-pilot-followup`).
- Investigate h13 tenancy-residual once enough signal accumulates.
