# Pre-pilot subprocessor / BAA compliance sweep — QuillMD `apps/transcribe-md`

**Date:** 2026-06-10 · **Mode:** READ-ONLY audit (no code / no prod / no data mutations) · **Scope:** `apps/transcribe-md` (LIVE app); `apps/meddoc-pro` excluded.
**Method:** HIPAA Compliance Auditor agent (code data-flow + doc reconciliation, shadow mode) + lead-agent verification of every load-bearing claim against deployed code/infra + PHI-safe prod data-marker query (metadata only, no row contents).
**Companion artifacts:** auditor shadow run `docs/agent-shadow-runs/hipaa-compliance/20260610T151733Z.md`; Fable gate `docs/qa-reports/fable5-flip-baa-gate-20260610T144302Z.md`; preflight `docs/preflight-reports/preflight-20260610T143859Z.md`.

---

## Bottom line

**Every external processor that touches real PHI is PILOT-BLOCKING.** Zero BAAs are `COUNTERSIGNED`, `secrets/baa/` does not exist, and there is **no countersign artifact anywhere on disk or in git history** (only BAA *documentation* commits #196/#120). Per the docs' own rule (`BAA_CHECKLIST.md:6-7`), no real patient data may flow until those BAAs are executed.

**Two things sharpen the urgency beyond "pre-pilot":**
1. **Prod already contains production-pattern data** — 75 visits, 25 SIGNED, 73 patient records, 173 delivery emails sent over ~7 weeks (see §3). If any are real patients, the Anthropic + Deepgram + Resend exposures are **already incurred**, not merely pilot-gating. → **Explicit question for Kasra in §4.**
2. **A latent OpenAI egress:** a routine Deepgram 429/5xx silently routes raw patient **audio** to OpenAI Whisper, which has no BAA (§2, processor row).

Encryption-at-rest is genuinely live (postgres LUKS + MinIO SSE-S3 — good). Several compliance-doc records were stale or contradicted the deployed code; corrected in this PR (§5).

---

## 1. Per-processor pre-pilot status

| Processor | PHI it sees | Real-PHI? | Current BAA status | Where it gets signed | Pilot-blocking |
|---|---|---|---|---|---|
| **Anthropic** | Transcript text, SOAP, Rx, referrals, patient summaries, note-format-parse input (`api.anthropic.com`) | **YES** | 🟡 NOT YET (request submitted 2026-05-05; **no countersign on disk/git**) | console.anthropic.com / trust.anthropic.com → Request a BAA (Tier-2+; else Anthropic Sales) | **YES** |
| **Deepgram** | Raw patient audio (uploaded + dictation) + transcript; **primary** batch ASR nova-3-medical (`deepgram-batch.ts`) | **YES** | 🟡 NOT YET | Deepgram Console → Account → Compliance → Request HIPAA BAA | **YES** |
| **OpenAI (Whisper)** | Raw patient audio — **live fallback** `whisper-1` (`whisper-batch.ts`), fires on Deepgram 5xx/408/429/network/timeout | **YES** | 🟡 NOT YET | platform.openai.com → Compliance API / Settings → BAA | **YES** (or disable the fallback — see §4.2) |
| **Resend** | Visit-export email: **patient name in subject + signed SOAP PDF attachment** (`lib/email.ts:80-83,117-122`); auth emails link-only | **YES** (visit-export path) | 🟡 NOT YET | resend.com/legal → request HIPAA BAA via support | **YES** |
| **Zap Hosting (VPS)** | All PHI at rest — Postgres rows, MinIO audio, pg_dump backups | **YES (at rest)** | 🟡 VERIFY | Zap Hosting support → "HIPAA BAA" (else migrate to HIPAA-eligible host) | **YES** |
| **Backblaze B2** (offsite backup) | age-encrypted backup blobs | n/a (**dormant**) | 🟡 NOT YET | backblaze.com/baa-request | **NO** — offsite leg disabled (`REMOTE_BACKUP_*`/`BACKBLAZE_*` env unset); blocks Phase 6.2, not the pilot |
| **Sentry** (error tracking) | Error events (redactPhi'd) | n/a (**disabled**) | 🟡 NOT YET | sentry.io → Legal & Compliance | **NO** — `SENTRY_DSN*` unset in both prod containers → SDK no-ops. **Do not set a DSN before a Sentry BAA.** |
| **MinIO / Postgres / Redis** | PHI at rest / in transit (self-hosted) | YES | covered by **Zap Hosting** host BAA | — | via Zap row |
| **GitHub / Caddy** | none / TLS in-process (self-hosted) | NO | N/A | — | NO |

**Verified controls (good):** postgres at-rest = LUKS `dm-crypt` (`/dev/mapper/pg-encrypted` → `/mnt/pgdata-encrypted`, verified live); MinIO at-rest = SSE-S3 auto-encryption enabled; Resend visit-export destination hard-gated to the caller's own account email (`route.ts:61-86`); Anthropic note-format **preview** uses a fixed synthetic transcript with `visitId:null` (no PHI); no third-party analytics/session-replay/webhook egress found in the code sweep.

---

## 2. Latent PHI egress — OpenAI Whisper fallback (verified)

`packages/ai/src/transcribe.ts` `shouldFallback()` routes to OpenAI Whisper (`whisper-batch.ts:223`, `whisper-1`) whenever the Deepgram primary throws AND the error is not a permanent 4xx AND audio ≤ 25 MB. `isPermanent4xxError` (`whisper-batch.ts:129-140`) treats **408 (timeout) and 429 (rate-limit) as RECOVERABLE**, so a routine Deepgram rate-limit or 5xx blip ships **raw patient audio to OpenAI** — which has no countersigned BAA. The transcript is tagged `provider:'whisper-fallback'` *after* the audio has already left. This is a live wired path (worker L1 → `transcribe()`), not dead code. **Audit only — not modified** (per task constraint "do not touch the Whisper fallback").

## 2a. Resend email carries PHI (verified — contradicts the old register)

`sendVisitPdfEmail` (`lib/email.ts`) puts the **patient name in the subject** (`:80-83`, `— ${patientName}`) and **attaches the signed SOAP note as a PDF** (`:117-122`, `attachments:[{content: pdfBuffer}]`). The body is PHI-free boilerplate, but subject + attachment are PHI. The register's prior "never SOAP body in email content" was materially inaccurate; corrected in §5. Mitigating control: destination is hard-gated to the caller's own account email.

---

## 3. Prod data markers (PHI-safe — counts/timestamps/status/domains only, no row contents)

- `transcribe_visits`: **75 total / 74 live**, statuses **48 READY · 25 SIGNED · 2 FAILED**, span **2026-04-19 → 2026-06-04**, **8 distinct doctors**.
- `transcribe_md_patients`: **73**. `visit_deliveries`: **173** (latest 2026-06-10).
- Visit-creating accounts by email **domain** (metadata only): gmail.com **45** (19 signed), meddoc.com **10** (3 signed), yahoo.com **6** (1 signed), quillmd-test.local 5 (0), quillmd.test 4 (0), quillmd.local 3 (2), ashtechgroup.com 2 (0).

This is **not** an empty pre-pilot system. 51 of 75 visits were created from real-looking external domains (gmail/yahoo), 20 of them signed, plus deliveries sent via Resend. Whether those are real clinicians or developer dogfooding with synthetic patients lives in `patientName`/`patientSummary` — **not read** (PHI). → §4 question.

---

## 4. THE OPERATOR ACTION LIST (Kasra — before any pilot / any real PHI)

**4.0 — EXPLICIT QUESTION (load-bearing): Do any of the prod visits above (esp. the gmail.com/yahoo.com/meddoc.com accounts) represent REAL patient encounters?**
- **If YES:** the Anthropic + Deepgram + Resend BAAs (and OpenAI, if any audio visit ever hit the Whisper fallback) are **IMMEDIATE breaches of §164.308(b), not pilot-gating** — real PHI has already flowed to processors with no executed BAA. Escalate to counsel now; consider whether breach-assessment obligations are triggered.
- **If NO (all synthetic/dogfood):** the items below are pre-pilot gates as written.
- Determine the answer from your own knowledge of these accounts — I did not read patient row contents.

**4.1 — Execute + file BAAs (each blocks the pilot per `COMPLIANCE_REGISTER.md:35-47`):**
| # | Processor | Where to sign | File to |
|---|---|---|---|
| 1 | **Anthropic** | console.anthropic.com / trust.anthropic.com → Request a BAA (request was submitted 2026-05-05; **chase it — no countersign on disk/git since**) | `secrets/baa/anthropic-<date>.pdf` |
| 2 | **Deepgram** | Deepgram Console → Account → Compliance → Request HIPAA BAA | `secrets/baa/deepgram-<date>.pdf` |
| 3 | **OpenAI** | platform.openai.com → Compliance/Settings → BAA | `secrets/baa/openai-<date>.pdf` |
| 4 | **Resend** | resend.com/legal → HIPAA BAA via support | `secrets/baa/resend-<date>.pdf` |
| 5 | **Zap Hosting** | Zap Hosting support → "HIPAA BAA" (or migrate to a HIPAA-eligible host) | `secrets/baa/zap-hosting-<date>.pdf` |

`secrets/baa/` does not exist yet — create it (host-only; `secrets/` is `.gitignore`d). Flip each `BAA_CHECKLIST.md` status to `COUNTERSIGNED <date>` **only after** the executed PDF is on file (this PR did NOT flip any checkbox).

**4.2 — OpenAI Whisper fallback decision:** if the OpenAI BAA can't land pre-pilot, **disable the fallback** (accept Deepgram-only with surfaced failure) so a Deepgram 429/5xx can't silently ship PHI audio to a non-BAA'd processor. (Code change — out of scope for this audit; flagged for a follow-up.)

**4.3 — Resend scope confirmation:** confirm with counsel given the PHI **PDF attachment + patient-named subject** (not the "metadata only" the register previously claimed).

**4.4 — Keep `SENTRY_DSN*` unset** until a Sentry BAA is signed (currently safe — disabled).

**4.5 — Backblaze:** offsite backup (Phase 6.2) stays gated on a Backblaze BAA; the pilot can launch without it (LUKS + daily local pg_dump are the floor).

**4.6 — h8 reconciliation:** encryption-at-rest is verified live, but the `HIPAA_COMPLIANCE.md` §h8 detail + the `docker-compose.yml` comment still describe pre-deploy design paths (`/var/lib/meddoc-postgres-encrypted.img`, `/etc/meddoc/postgres-volume.key`) vs the deployed `/mnt/pgdata-encrypted`. Reconcile the paths + confirm key-escrow/rotation per `RUNBOOK_ENCRYPTED_VOLUME.md` (root-owned; not agent-verifiable).

---

## 5. Doc staleness corrected in this PR (no BAA checkbox flipped)

| Doc | Was | Now |
|---|---|---|
| `BAA_CHECKLIST.md:30` / `COMPLIANCE_REGISTER.md:16` | Anthropic "Sonnet 4.6 + Opus 4.7 + judge" | `claude-opus-4-8` + `claude-sonnet-4-6` split + `TRANSCRIBE_MD_CLINICAL_MODEL`; preview noted synthetic |
| `BAA_CHECKLIST.md:31` / notes / `REGISTER:17` | OpenAI `gpt-4o-transcribe`, `openai.ts`, "legacy" | `whisper-1`, `whisper-batch.ts` via `transcribe.ts`, **live** fallback + 408/429 trigger |
| `BAA_CHECKLIST.md:32` / notes | Deepgram "streaming", `deepgram.ts`, `wss://`, scribe-ws | **batch** `deepgram-batch.ts`, HTTPS `POST /v1/listen` |
| `REGISTER:19` | Resend "never SOAP body in email content" | **patient name in subject + signed SOAP PDF attachment** |
| `BAA_CHECKLIST.md` matrix/diagram/checklist | **Resend absent entirely** | added as a processor row + diagram node + pre-launch checklist item + PHI-tag |
| `BAA_CHECKLIST.md:37` | VPS host "Hetzner/DO/AWS — VERIFY" | pinned to **Zap Hosting** |
| `HIPAA_COMPLIANCE.md:24` (h8) | "Mitigated (pending operator migration)" | **Mitigated** (LUKS verified live) + path-reconciliation note |
| both docs | no Fable-5 decision on file | **recorded** (rejected for prod; rationale + ref to gate report) |

**Not flipped:** every BAA status remains 🟡/NOT YET/VERIFY — those move to signed only after Kasra files the executed PDFs (§4.1).

---

## 6. Fable 5 — decision on file

Generation stays on `claude-opus-4-8`. Fable 5 was evaluated (PR #292, clinical quality clean) but **rejected for prod**: (a) global flip breaks forced-`tool_choice` parse + PHI-scan; (b) Fable 5 is a Mythos-class Covered Model with **mandatory 30-day retention and no zero-data-retention option**, structurally incompatible with the zero-retention HIPAA posture. Recorded in `COMPLIANCE_REGISTER.md` + `BAA_CHECKLIST.md` Anthropic notes. Full rationale: `docs/qa-reports/fable5-flip-baa-gate-20260610T144302Z.md`.

---

**Verdict:** 🔴 **Pilot BLOCKED** until the §4.1 BAAs are countersigned + filed. Prod untouched; no code/schema/pipeline changed by this audit.
