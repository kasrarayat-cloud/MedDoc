QuillMD pilot-ready snapshot — 2026-04-27

Production: app.quillmd.com / pro.quillmd.com / admin.quillmd.com
Stack:      Next.js 16, Postgres 16+pgvector, Whisper + Deepgram
            Nova-3 Medical, Claude Sonnet 4.6, Docker, Caddy
Containers: 9/9 non-root, all healthy
            postgres/redis/postgres-backup uid=999
            caddy/minio uid=1000
            meddoc-pro/transcribe-md/worker/marketing uid=1001

HIPAA controls (Phase 6Z + Phase 13 + Phase 16/17 review):
  §164.308 administrative safeguards:    5/5 controls verified
  §164.312 technical safeguards:         5/6 verified, 1 open (encryption-at-rest)
  §164.316 documentation:                7-year retention via soft-delete verified
  Findings:                              9 resolved / 7 open

Open findings:
  h8-h3-pilot-followup       (high — Hetzner managed encrypted volume;
                              runbook docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md;
                              planned 30-45 min maintenance window)
  h16-offsite-backup         (high — code in place + post-script gated
                              on REMOTE_BACKUP_S3_* env vars; runbook
                              docs/H16_OFFSITE_BACKUP_PROCEDURE.md
                              awaiting Hetzner Object Storage creds)
  h16-admin-session-7day     (medium — admin surface inherits
                              transcribe-md 7d session maxAge)
  h16-audit-gap-realtime     (medium — WebRTC voice session lifecycle
                              endpoints unaudited; audio bytes never
                              touch our server)
  h16-cap-drop-defense-in-depth (medium — 8/9 containers keep default
                              Docker capabilities)
  h16-csp-report-only        (medium — CSP report-only; switch to
                              enforced after burn-in)
  h13-meddoc-e2e-tenancy-residual (low — 5 Playwright tests time out
                              under next-dev Turbopack first-hit
                              compile; production login flow unaffected)

Recent work (newest first):
  Phase 17 (2026-04-27, PR #78): closed 3 of 4 high h16 findings —
    AUDIO_UPLOADED, DOC_EDITOR_SAVED, DOC_EDITOR_AI_SUGGESTED,
    PHI_EXTRACTED_FROM_VOICE audit actions now emitted on the
    PHI-touching mutation paths; off-site backup post-script + runbook
    landed (gated on env vars; safe to merge before Hetzner-side
    provisioning).
  Phase 16 (2026-04-26, PR #77): full re-audit; 0 critical found,
    8 new h16 findings tracked, conditional GO verdict.
  Phase 14 (2026-04-26): test-flows.mjs:322 severity-filter fix so
    the E5 assertion stays drift-resistant as new low-severity
    findings get added.
  Phase 13 (2026-04-26, PR #75): postgres/redis/caddy/postgres-backup
    converted to non-root (closed h8-h4); AUTH_DEBUG instrumentation
    + per-IP/per-email rate-limit loopback exemption (closed h9 with
    partial fix; residual tracked as h13); H3 encrypted-volume
    runbook documented.

Test posture:
  Admin audit:  46/46 passed (production smoke)
  Flows:        19/19 passed (resolve→reopen, suspend, threats, audit-write)
  Consistency:  9/9 passed   (cent-match across 3 windows + audit timeline)
  Vitest:       9 passed     (adversarial suite, in CI)
  Playwright:   3/8 passing in CI; 8/8 verified live in production

Backup:     daily 00:00 UTC, 7-day rotation, restore drill verified ✓
Smoke test: real visit cmofzxpoi004y01nzrpu8n01d, SIGNED in 3:29
            (audio → Deepgram → 10 Anthropic layers → OpenAI embed →
             Resend email; 12 api_usage_events across 4 providers) ✓

Pilot scope: 5 doctors, 30-day evaluation
Apply:       [DM Kasra / pilot@quillmd.com / form link]
