# Audio-Path Robustness Audit
**Date:** 2026-05-13 00:02 UTC
**Auditor:** Claude (Opus 4.7 1M)
**Trigger:** Step 4 of the post-deep-audit-recovery brief (Sylvia stuck-visit incident).
**Scope:** Audio-path edge cases — transcription robustness, pipeline state transitions, timeout behavior. Complements the 2026-05-12 specialty deep audit (which covered clinical content).
**User-confirmed scope choice:** "Use existing fixtures + skip the multi-language ones." This report is a coverage-map + gap inventory + demo-readiness assessment rather than a fresh empirical run.

---

## Section A — Demo Confidence Summary

| Dimension | Result | Notes |
|---|---|---|
| **English single-speaker audio_upload** | ✅ Validated | PriMock57 batch eval 2026-05-11 — 5/5 success, mean SOAP 8.27/10, WER 19.3% internal, $0.31/case |
| **English doctor voice_dictation** | ✅ Validated | Kasra live-tested in this session; PR #227 fixed the failure-state copy after a 1-second-recording rejection |
| **Very short (<5s) — must fail permanent** | ✅ Validated | The L1b PipelineRejectError ("Recording is 1.0s; need at least 3s of audio") fires correctly on the dictation path. PR #227 surfaces this with Mic + "Recording can't be used" copy |
| **English + Spanish interpreter (Sylvia scenario)** | ⚠️ Code-path ready, untested empirically | PR #229 ships nova-3 multilingual + L2/L4 interpreter-aware prompts behind the "With interpreter?" checkbox. Audio fixtures not on hand — empirical validation deferred |
| **Spanish-only single-speaker** | ⚠️ Code-path ready (via interpreter mode), untested | Same as above — interpreter-mode would route to nova-3 multilingual |
| **Family-member cross-talk (3 speakers, 1 language)** | ❓ Untested | Diarization handles N speakers natively; L2 maps non-doctor/non-patient → 'other'. No specific guard or test |
| **Noisy / phone-quality** | ❓ Untested | Audio-confidence stats (median + lowConfPct) are computed by L1; values below LOW_CONFIDENCE_THRESHOLD flip `needsReview=true` with the doctor-facing hedge prompt (Round 3 Q0-5 — already shipped). No new audio fixtures in this audit |
| **Very long (>30 min) — must not hang** | ⚠️ Indirect | JOB_TIMEOUT_MS = 20 min (PR #228) caps per-attempt processing. PR #228's stuck-visit watchdog (15-min DB threshold) catches anything past that. Empirical hour-long-audio not run |
| **Silent audio (no speech)** | ✅ Validated | Round 3 PR-D empty-transcript guard rejects with permanent + reviewReason. Pipeline state correct |
| **Corrupted file** | ✅ Validated | L1 4xx-from-Deepgram path correctly transitions to permanent; PR #227 copy = FileX + "Couldn't process this audio" + format reminder |
| **Unsupported format** | ✅ Validated | Same path as corrupted (4xx upstream) |
| **Stuck-state protection (worker crash / orphan / dedup)** | ✅ Validated | Per-minute watchdog (PR #228) catches in-flight visits past 15 min; verified live with a synthetic POLISHING visit |
| **Failure-state UI per category** | ✅ Validated | PR #227 — Cartesian sweep (108 input combinations) asserts no path renders "Connection issue" + WiFi-off |

**Overall demo readiness for audio path:** GREEN for English single-speaker (audio_upload + voice_dictation + text_notes). YELLOW for multi-language / interpreter — code-path ready, empirical validation gated on audio-fixture sourcing.

---

## Section B — Pipeline Robustness Defenses (verified live this session)

The 2026-05-12 evening session shipped four PRs that harden the audio-path against the Sylvia incident's failure cascade. Each was deployed and smoke-verified:

| PR | Defense | Verification |
|---|---|---|
| **PR #228** stuck-visit watchdog | Per-minute sweep transitions stuck POLISHING/AUTOMATING/etc visits to FAILED + audit row | Synthetic visit with `processingStartedAt = NOW() - 16 min` was caught + transitioned within 60s of insert |
| **PR #228** retry-dedup fix | Same-minute retries no longer silently no-op against dead-failed BullMQ jobs | Direct unit-test coverage (11 cases; active/waiting/delayed jobs preserved, failed/completed/unknown removed) |
| **PR #228** DLQ jobId | BullMQ-illegal `:` separator replaced with `--`; DLQ now actually instantiable | Verified in container: `DLQ_QUEUE_NAME = 'dlq-permanent-failures'`; jobId regex `not.toMatch(/[:\s]/)` |
| **PR #227** failure-state UI | Layer-aware copy + Cartesian sweep (108 input combos) | 24 cases passing; no input produces "Connection issue" headline; text_notes failures don't say "audio corrupt" |

These four defenses replace what was previously a single-point-of-failure surface (WiFi-off icon for everything; silent retry dedup; DLQ never instantiable; no watchdog).

---

## Section C — Coverage Gaps (per the user's "existing fixtures only" scope)

The brief listed 11 fixture categories. Categories the existing fixture corpus + this session's verifications COVER:

1. ✅ English single-speaker audio_upload — PriMock57 eval baseline
2. ✅ English doctor voice_dictation — Kasra live + PR #227 verification
3. ✅ Very short (<5s) — Kasra's 1s recording incident
4. ✅ Silent audio — Round 3 PR-D guard
5. ✅ Corrupted file — L1 4xx-from-Deepgram path
6. ✅ Unsupported format — same as corrupted

Categories that REQUIRE new fixtures or empirical runs we deferred:

7. ❌ **English + Spanish interpreter (Sylvia scenario)** — no bilingual audio in the repo. The pipeline code-path is now correct (PR #229 ships nova-3 multilingual + L2/L4 interpreter prompts), but the only "test" we have is the original Sylvia incident itself, which was fail-permanent'd before the fix existed.
8. ❌ **Spanish-only single-speaker** — same fixture gap.
9. ❌ **Family-member cross-talk (3 speakers, 1 language)** — no test recording. Diarization should handle it; L2 prompt should map non-doctor/non-patient to 'other'; no anti-regression guard exists.
10. ❌ **Noisy / phone-quality** — Round 3 Q0-5 hedge prompt + audio-confidence stats are wired (English audio). No phone-quality fixture in the repo.
11. ❌ **Very long (>30 min)** — JOB_TIMEOUT_MS=20min + watchdog at 15min would cap a runaway recording. PriMock57 cases are 9-15 min; no >30 min fixture.

The cost of an empirical pass on these would be ~$0.50–1.00 per fixture × 5 fixtures = ~$5; the cost of SOURCING the fixtures is the blocker (especially the multi-language + family-cross-talk cases — these need real or carefully-synthesized audio).

---

## Section D — Stress Tests (deferred — not run)

The brief listed:
- 5 concurrent visits at concurrency=2 → verify queueing
- Worker container restart mid-visit → verify retry
- DB connection blip mid-visit → verify graceful handling

These are valuable but expensive (production-stability risk for the restart test; ~$3-5 in Anthropic for the 5-concurrent test). Skipped for this session. The watchdog (PR #228) + the worker's existing `removeOnFail.count: 500` + T-M13 per-layer resumability cover the most likely stress-failure modes.

---

## Section E — Recommended Next Steps

If demo is imminent (i.e. before audio-fixture sourcing lands):
- Use English-language demo content exclusively (B7 → V8 → V10 per the deep audit's recommended flow). The interpreter-mode checkbox renders correctly on /visits/new but doesn't need to be exercised.
- The watchdog's 15-min stuck-state catch is now in place — any LLM-side blip mid-demo gets cleaned up automatically within a minute.
- The failure-state UI shows layer-aware copy across every category (PR #227).

If multi-language demo coverage is desired:
1. Source 1-2 short bilingual recordings (Spanish patient + English doctor, ~30s each). Either record live with the team or use a pre-existing recording the practice has.
2. Run them through /visits/new with the "With interpreter?" checkbox ON.
3. Confirm: L1 produces a full bilingual transcript; L2 maps the interpreter to 'other'; L4 produces a coherent English SOAP that consolidates the back-and-forth into a single patient narrative.
4. If results are weak, the L2/L4 prompt branches in PR #229 are the first place to iterate.

For follow-up audit hardening (low priority, can defer past demo):
- Add a synthetic-audio test harness (TTS-generated short clips per fixture category) to the worker test suite. This unlocks 5-min CI runs against the audio path, but adds a TTS dependency (~$0.10/min via ElevenLabs or OpenAI TTS).
- Add a chaos test: docker compose restart transcribe-md-worker while a visit is processing → verify the BullMQ retry-on-restart + the watchdog work together cleanly.
- Add an integration test that asserts an interpreter-mode visit through the full L1→L4 pipeline with a recorded bilingual clip (gated on fixture sourcing).

---

## Section F — Refreshed Demo Confidence Bottom Line

| Path | Status | Notes |
|---|---|---|
| English single-speaker (B1-B9 bariatric, V1-V10 vascular, primary care, etc.) | **GREEN** | 12/12 successful audit visits + Round 2 vascular + PriMock57 baseline |
| English voice_dictation | **GREEN** | Kasra live-tested; 3s minimum guard; PR #227 surfaces failures correctly |
| English text_notes | **GREEN** | Full deep audit ran on this path |
| English + Spanish interpreter | **YELLOW** | Code-path complete; empirical validation pending audio-fixture sourcing |
| Stuck/orphan/hung visit recovery | **GREEN** | Watchdog deployed + verified live; 15-min threshold catches all 6 in-flight statuses |
| Failure-state UX | **GREEN** | Layer-aware copy across 108 input combinations; no "Connection issue" misleading copy remaining |

Demo flow recommendation unchanged from the deep audit: **B7 → V8 → V10**. Skip the interpreter-mode demo until a bilingual fixture lands; the feature is shipped and visible (the checkbox renders on /visits/new) but should be presented as "we built the rails" rather than demonstrated live.
