# Compliance register — subprocessors, BAAs, DPAs

**Purpose:** single source of truth for the BAA/DPA status of every third-party service that touches QuillMD data. The marketing site's HIPAA + privacy pages must reconcile against this file. **If a row says "BAA pending" or "not started", marketing copy must NOT claim a signed BAA for that subprocessor.**

This register is the operationalization of Round 3 audit finding **A12-P0-001** (BAA reality vs marketing gap). It is the file the marketing legal-review process reads against, and the file an HHS auditor would ask to see.

**Last reviewed:** 2026-05-05 (Round 3 PR-G)
**Owner:** Kasra (single-engineer team, pre-pilot). Post-pilot: dedicated compliance owner (TBD).

---

## Subprocessor matrix

| Subprocessor | Role | PHI exposure | BAA status | DPA status | Last reviewed | Notes |
|---|---|---|---|---|---|---|
| **Anthropic** | LLM provider (Claude Sonnet 4.6 + judge) | Cleaned transcript text, SOAP note, Rx drafts, referral letters, patient summaries | 🟡 **Pending — request submitted via console.anthropic.com → Settings → BAA** | ✅ DPA via [Anthropic Privacy Policy](https://www.anthropic.com/legal/privacy) | 2026-05-05 | BAA must be executed before pilot launch with covered-entity customer. Anthropic offers BAA for Claude API on standard plan. Track ticket # when filed. |
| **OpenAI** | Embeddings (`text-embedding-3-small`) for edit-tracking; legacy ASR fallback (Whisper) for batch mode | For embeddings: SOAP edit-pattern vectors (no raw transcripts). For ASR fallback: uploaded audio + transcribed text | 🟡 **Pending — request via platform.openai.com → Settings → BAA** | ✅ DPA via [OpenAI Privacy Policy](https://openai.com/policies/privacy-policy) | 2026-05-05 | OpenAI offers BAA for API customers on standard plan; requires support ticket. Embeddings exposure is minimal (vector representations) but still BAA-required. |
| **Deepgram** | ASR (nova-3-medical) for production voice/audio transcription | Audio bytes (uploaded + dictation), full transcript text | 🟡 **Pending — request via Deepgram Console → Account → Compliance** | ✅ DPA via [Deepgram Privacy Policy](https://deepgram.com/privacy) | 2026-05-05 | Primary ASR provider — highest PHI exposure of any subprocessor. BAA execution is a launch blocker. |
| **Resend** | Transactional email delivery (verification, account-exists, password reset) | Email metadata (recipient address, subject); never SOAP body in email content | 🟡 **Pending — request via resend.com support; support@resend.com** | ✅ Standard ToS | 2026-05-05 | Recipient email and "you have a QuillMD account" is borderline PHI (associates patient/provider with a healthcare service). BAA execution recommended pre-pilot. |
| **Backblaze B2** | Encrypted offsite backup destination (Phase 6.2) | age-encrypted Postgres + MinIO archives. Backblaze never sees plaintext (decryption keypair private half is offline) | 🟡 **Pending — request via Backblaze support → "HIPAA BAA" ticket** | ✅ Standard ToS | 2026-05-05 | Phase 6.2 not yet activated (per `POST_MERGE_TODO §22`). BAA + activation must land together. Even with offline-key custody we want BAA in place because metadata (object names, sizes, timestamps) is itself PHI-adjacent. |
| **Sentry** | Error + performance monitoring (apps/transcribe-md, apps/marketing) | Error messages + stack traces (PHI-redacted at source via `redactPhi()`); user IDs (no email) for setUser context | 🟡 **Pending — Sentry self-serve BAA at sentry.io → Settings → Legal & Compliance** | ✅ DPA via Sentry Privacy Policy | 2026-05-05 | Phase 17 PR added `redactPhi` `beforeSend` hook — see `packages/ai/src/log.ts:67-90`. PHI-redacted before leaving the process; BAA is defense in depth. Round 3 PR-D moved Sentry instrumentation to the marketing app too (Sentry instrumentation expansion deferred to `PR-H` per `POST_MERGE_TODO §24` recommendations). |
| **Zap Hosting** | VPS provider (compute + disk for Postgres, MinIO, Redis, app containers) | Every byte of PHI rests on this host (LUKS-encrypted via Phase 6.1) | 🟡 **Pending — request via Zap Hosting support → "HIPAA BAA"** | ✅ Standard ToS | 2026-05-05 | Hosting-provider BAA required because the host has theoretical disk-image access. LUKS encryption mitigates but does not eliminate the BAA requirement. |
| **GitHub** | Source code, issue tracking, CI runners | None (PHI never enters the code). CI runs against synthetic test data only | N/A — no PHI exposure | ✅ DPA via GitHub Privacy Policy | 2026-05-05 | No BAA needed because CI never sees real PHI. If we ever introduce production-data testing in CI, this row updates. |
| **Cloudflare / Caddy** | Reverse proxy + TLS termination | TLS handshakes; HTTP request URLs + bodies pass through Caddy in-process (Caddy is self-hosted on the VPS) | N/A (self-hosted) | N/A | 2026-05-05 | Caddy runs as a container on the VPS — it's hosted by us, not Cloudflare. If we add Cloudflare in front, that adds a BAA requirement. |
| **DrChrono** (legacy MedDoc Pro EHR sync) | Patient identifier source-of-truth | Patient name, MRN, chart info — read-only sync into MedDoc Pro `patients` table | 🟡 **Verify** — was added pre-M7; status unknown post-decommission | ✅ Standard EHR partner | 2026-05-05 | DrChrono integration was scoped to MedDoc Pro (decommissioned per `POST_MERGE_TODO §21`). Verify whether any code path remains in the active build; if not, this row removes from the register. |

**Status emoji key:**
- ✅ Signed and on file
- 🟡 Pending — submitted or in active negotiation
- 🟠 Not started
- ❌ Refused / not available — must replace with another subprocessor

---

## Pre-pilot launch gate

Before the first pilot customer's PHI flows through QuillMD, the rows above marked 🟡 must move to ✅ for **at least** these subprocessors:

- [ ] Anthropic — BAA signed (highest PHI exposure)
- [ ] OpenAI — BAA signed (embeddings only; deprecate ASR-fallback if blocking)
- [ ] Deepgram — BAA signed (primary ASR)
- [ ] Resend — BAA signed (or document that recipient-email-only is below the BAA threshold for this jurisdiction; legal review)
- [ ] Zap Hosting — BAA signed (or migrate to a HIPAA-eligible host)
- [ ] Sentry — BAA signed (or disable via empty `SENTRY_DSN_*` for pilot)
- [ ] Backblaze — Phase 6.2 activation gated on BAA execution; can launch pilot without offsite backup (Phase 6.1 LUKS + daily local pg_dump are the floor)

**This list is the literal launch gate.** A "🟡 Pending" entry on a row in this list = pilot launch is blocked.

---

## When a new subprocessor is added

1. Open a row in this register before the integration ships any production traffic.
2. Add the row to `docs/BAA_CHECKLIST.md` (the operational pre-launch list).
3. Audit `redactPhi()` coverage for the new boundary (`packages/ai/src/log.ts`, `apps/*/sentry.*.config.ts`).
4. Update marketing site's `/hipaa` page to reflect the new subprocessor in the BAA list.
5. Update this register's "last reviewed" date.

---

## When a subprocessor is removed

1. Confirm no code path still calls the subprocessor (`grep -rn` for SDK imports, env vars, API URLs).
2. Mark the row 🟠 → "removed YYYY-MM-DD".
3. Remove from `BAA_CHECKLIST.md`.
4. Update `/hipaa` page.
5. Note in `POST_MERGE_TODO` decommission section.

---

## Quarterly review (Phase 7+)

Once we have a compliance owner (post-pilot), this register gets a quarterly walkthrough:

- BAA renewals (most BAAs auto-renew but verify)
- New subprocessors that snuck in without going through the gate
- DPA changes from upstream (Anthropic / OpenAI / etc. occasionally update theirs)
- Marketing copy reconciliation (every claim on the public site → row in this register)

Add to `docs/runbooks/quarterly-compliance-review.md` (Phase 7 scope; not yet authored).
