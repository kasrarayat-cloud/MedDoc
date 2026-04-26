QuillMD pilot-ready snapshot — 2026-04-26

Production: app.quillmd.com / pro.quillmd.com / admin.quillmd.com
Stack:      Next.js 16, Postgres 16+pgvector, Whisper + Deepgram
            Nova-3 Medical, Claude Sonnet 4.6, Docker, Caddy
Containers: 9/9 non-root, all healthy
            postgres/redis/postgres-backup uid=999
            caddy/minio uid=1000
            meddoc-pro/transcribe-md/worker/marketing uid=1001

HIPAA controls (Phase 6Z + Phase 13 review):
  §164.308 administrative safeguards:    5/5 controls verified
  §164.312 technical safeguards:         5/6 verified, 1 open (encryption-at-rest)
  §164.316 documentation:                7-year retention via soft-delete verified
  Findings:                              6 resolved / 2 open

Open findings:
  h8-h3-pilot-followup    (Hetzner managed encrypted volume —
                           runbook in docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md;
                           planned 30-45 min maintenance window)
  h13-meddoc-e2e-tenancy-residual (low — 5 Playwright tests time
                           out under next-dev Turbopack first-hit
                           compile; production login flow unaffected)

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
