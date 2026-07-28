# Whisper-fallback kill-switch — audit item 4.2 closure

**Date:** 2026-06-10 · **Branch:** `feat/whisper-fallback-killswitch` · **Status:** code shipped + deployed to prod (worker), fail-closed (fallback DISABLED).
**Closes:** item 4.2 of `docs/qa-reports/pre-pilot-baa-status-20260610T152350Z.md` — "a Deepgram failure can silently ship raw patient audio to non-BAA'd OpenAI Whisper."

---

## TL;DR

The Deepgram→OpenAI Whisper transcription fallback is now **fail-closed behind a kill-switch** (`TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED`, default off). With the flag unset (prod default), a Deepgram failure that *would* have fallen back now fails the visit into the **retryable BullMQ DLQ** + emits a suppressed-fallback audit row — **raw patient audio never reaches OpenAI**. Forensics confirm the fallback has **never fired in prod**, so this closes a latent exposure with **zero historical incidents**. Prod deployed (worker recreated on the new image); flag unset → disabled; rollback tag in place.

---

## Phase 1 — FORENSICS (read-only): did OpenAI ever receive prod audio?

**Answer: NO — OpenAI received prod patient audio 0 times (never).** Two independent signals across ALL prod history agree:

| Signal | Result |
|---|---|
| `transcribe_visits.transcriptionProvider` (persisted per visit, PR #163) | **0** `whisper-fallback`. 17 `deepgram-batch` (2026-05-06→06-04) + 58 null/pre-field (2026-04-19→05-12). |
| `audit_logs` action `TRANSCRIPTION_PROVIDER_FALLBACK` (emitted on every fallback) | **0 rows.** (In a table with 7,821 rows across 67 action types — instrumentation is demonstrably live, not missing.) |

**Account-class of fallback events:** N/A — there were no fallback events for any account class (test or non-test). The 58 null/pre-field visits predate the fallback feature entirely (the orchestrator + the `transcriptionProvider` field + the audit action all shipped together in **PR #162, 2026-05-06**, commit `ae2cd8e`), so no OpenAI code path existed when they were created. The 2 prod `FAILED` visits were both `deepgram-batch` (failed downstream, never OpenAI).

**Feeds Kasra's 4.0 decision:** OpenAI is **cleared** as an already-incurred PHI exposure — no real (or test) patient audio has ever reached it. (The Anthropic + Deepgram + Resend "real-patient?" question from the pre-pilot report stands on its own; this only clears OpenAI.)

---

## Phase 2 — Kill-switch implementation (fail-closed)

**Gate (orchestrator, `packages/ai/src/transcribe.ts`):** `TranscribeArgs.allowCrossProviderFallback` — **fail-closed: the fallback fires only when this is exactly `=== true`.** The gate sits AFTER the existing eligibility check (`shouldFallback`: permanent-4xx / oversize still re-throw the original Deepgram error, unchanged) and BEFORE the Whisper call — the only code path to OpenAI. When eligible-but-disabled it throws the new exported `CrossProviderFallbackDisabledError`. Deepgram-internal retries unchanged.

**Worker (`01-transcribe.ts` + `01b-transcribe-dictation.ts`):** resolve the flag via `isWhisperFallbackEnabled()` (`TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED === 'true'`, app-side — `packages/ai` stays pure, takes a boolean arg), pass it into `transcribe()`, and wrap the `withRetry` call: on `CrossProviderFallbackDisabledError`, emit a `TRANSCRIPTION_PROVIDER_FALLBACK` audit row (`success:false`, `errorCode: CROSS_PROVIDER_FALLBACK_DISABLED`, `metadata.suppressed:true`, primary error/status — PHI-safe, field-names-not-values), then re-throw.

**Disabled behavior:** the re-thrown error flows to the worker's existing outer catch → `categorizeError` (no `.status` on the typed error → generous **`transient` default**) → on non-final BullMQ attempts re-runs (a fresh Deepgram attempt), on the final attempt `persistFailedState` → visit `FAILED` + `reviewReason` + the job lands in the **DLQ visible on `/admin/queues`**. Never a silent hang, never OpenAI. Retryable (BullMQ job retries + doctor re-submit). The typed error deliberately carries no `.status` so it doesn't burn an extra `withRetry` backoff and doesn't mask a real permanent-4xx (eligibility precedes the gate).

**Resilience preserved:** Deepgram's internal retries (`deepgram-batch.ts`) + the L1 `withRetry` on the Deepgram path are untouched — only the cross-provider hop is gated.

**Other clinical-path forced-tool / egress?** Out of scope here; this change is solely the transcription fallback. (The note-format parse + PHI-scan forced-`tool_choice` paths are tracked separately in the Fable gate report.)

**Pricing/telemetry:** unchanged. Whisper cost logging only matters when the flag is enabled.

**Tests:** `packages/ai/src/__tests__/transcribe-fallback.test.ts` — kill-switch suite (disabled / `false` / absent-flag fail-closed / network-no-status / permanent-4xx-still-rethrows-original, Whisper never called). `low-conf-l1.test.ts` — disabled path re-throws + emits the suppressed audit (no visit write). 23/23 pass; full transcribe-md+ai unit run otherwise green (the 7 unrelated failures are pre-existing local env/seed gaps in `llm-mdm`/`edit-tracking`/`specialty-catalog`, not in this diff). Typecheck clean for all changed files.

**code-quality-auditor: SHIP** ✅ — no BLOCKER, no SHOULD-FIX; independently traced fail-closed (no OpenAI bypass), retryable-not-extra-retry, PHI-safe audit, `packages/ai` purity. 4 cosmetic NITs (1 fixed: `.env` double-blank).

`.env.production.example` documents the flag (commented, default disabled, "do not enable until OpenAI BAA on file").

---

## Phase 3 — Verification + deploy

**Verification chain:**
1. **Unit (deterministic):** both layers × {disabled, false, absent, network-error, permanent-4xx} — the failure path (Deepgram-fail → eligible → disabled → `CrossProviderFallbackDisabledError` → suppressed audit + re-throw, Whisper never called) is asserted directly. This *is* "mock a Deepgram failure → DLQ + audit" at the unit level.
2. **Adversarial review:** code-quality-auditor traced the full runtime path through the real `worker.ts → categorizeError → persistFailedState/DLQ` machinery and confirmed correctness + retryability.
3. **QA stack (isolated `meddoc-qa`, new worker image `ffdfd6b0`):** booted clean — `ready — listening on queue transcribe-md (concurrency 2)`, flag unset → disabled, wired to DB/Redis/MinIO, no crash. Torn down `-v` (0 residue).
4. **Build:** worker image rebuilt from committed `dfb2a54` (compiles + bundles the new `packages/ai` + worker source cleanly).

**Not staged (transparency):** a live end-to-end *failure-path* fault-injection in the qa stack (network-blocking Deepgram + audio-submission across the qa-internal network) and a live prod UI transcription smoke were **not** run. Rationale: the failure path is exhaustively unit-verified + auditor-traced; the happy path is untouched **by construction** (the gate is catch-only — Deepgram-success returns before it) + unit-verified; the rebuilt worker boots clean in both qa and prod; and the fail-closed direction means the worst realistic wiring bug is a benign FAILED visit, never PHI egress. Rollback is one step.

**Deploy (prod, worker-only):**
- **Rollback tag:** `meddoc-pro-transcribe-md-worker:pre-whisper-killswitch` → `sha256:e76522161f32…` (the image the worker was actually running). One-step rollback: `docker tag …:pre-whisper-killswitch …:latest && docker compose -f docker-compose.yml up -d --no-deps transcribe-md-worker`.
- **Action:** `docker compose -f docker-compose.yml up -d --no-deps transcribe-md-worker` → recreated on new image `sha256:ffdfd6b0…`. Queue was idle (active/wait/delayed = 0) at recreate.
- **Verified post-deploy:** worker `running`, clean boot logs (`listening on queue`, ops jobs scheduled), `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED` **unset → fallback DISABLED**, `MOCK_AI_CALLS=false` + `DEEPGRAM_API_KEY` set (real Deepgram primary intact). All other prod containers + co-tenants (LeatherERP/voiceassist/openclaw) untouched; the uncommitted LeatherERP `Caddyfile` edit untouched. App NOT rebuilt (doesn't call `transcribe()`; change is additive).

---

## Phase 4 — Docs

`BAA_CHECKLIST.md` + `COMPLIANCE_REGISTER.md`: OpenAI rows updated — fallback **disabled-by-default**, OpenAI BAA **no longer pilot-blocking** (required only before enabling the flag). The pre-pilot launch gate's hard-blocking BAA list is now **4: Anthropic, Deepgram, Resend, Zap Hosting** (Sentry + Backblaze remain disabled/dormant; OpenAI now conditional).

---

## Result

- **Forensics:** OpenAI received prod audio **0 times (never)**; no fallback event for any account class.
- **Prod state:** worker on `ffdfd6b0`, fallback **DISABLED** (flag unset), Deepgram primary intact, healthy. Generation/clinical model unchanged (Opus).
- **Rollback tag:** `meddoc-pro-transcribe-md-worker:pre-whisper-killswitch` (`e76522161f32`).
- **Pilot-blocking BAA list → 4:** Anthropic, Deepgram, Resend, Zap Hosting.
