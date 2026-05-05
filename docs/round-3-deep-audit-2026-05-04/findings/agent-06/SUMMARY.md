# Agent 06 — AI Safety & Clinical Correctness · Summary

## Severity counts
**P0: 4 · P1: 6 · P2: 3 · P3: 2 · Total: 15**

## Top 3 findings
1. **A06-P0-001 — No empty-transcript guard.** "Empty audio → empty SOAP" is enforced by Claude prompt obedience only; no code-side check at L1/L1b/L3/L4. Silent recording → fabricated SOAP is one model-drift away. (`worker.ts:256-269,314-447`; `01-transcribe.ts:90-103`; `04-generate-soap.ts:27-112`.)
2. **A06-P0-002 — No ICD-10/CPT allowlist.** Both schemas validate regex shape only (`/^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$/i`, `/^[0-9]{5}$/`). `Z99.999` and `99999` pass. Modifiers + E&M code identical issue. False Claims Act exposure for the practice.
3. **A06-P0-004 — No clinical-pharmacology backstop.** Every Rx warning shown in the rail is pure Claude output. No RxNav/RxNorm, no allergy class-match, no static dose-range table, no peds mg/kg validator. Patient weight isn't even captured in the visit model.

## Coverage
Read end-to-end: every layer (L1, L1b, L2, L3, L4, L5, L6, L7a-e, readability), `worker.ts` (1087 lines), all `packages/ai/src/*`, all `worker/prompts/*`, all `em-coding/*` + tests, all 16 vitest files, all 4 e2e specs, all 7 smoke phases, specialty catalog, deepgram-vocabulary, rx-warning-audit, audio-uploader, upload route. No sampling.

## Positives
1. Per-entity `evidence_quote` enforced at Zod level (L3) — non-fabrication primitive done right.
2. `Promise.allSettled` fan-out for L7a-e + roll-up into `confidenceScores` per-task (`worker.ts:642-704`) — partial-success model is principled.
3. T-M13 layer-skip resumability with column-as-checkpoint design — avoids re-running successful layers on retry.
4. em-coding LLM-judge + deterministic fallback + Redis cache + 20%-drift re-judge (`llm-mdm.ts`). The one place in the codebase that pairs LLM with deterministic floor — should be the blueprint for fixing P0-002/003/004.
5. PHI-redaction discipline: `redactPhi(err.message)` on every console.error and Sentry capture; `reviewReason` derived ONLY from `currentLayer`, never from error body.
6. `MEDICATION_KEYTERMS` token-budget unit test (`deepgram-vocabulary.test.ts`) — guardrail-on-prompt-budget pattern.

## Cross-domain hooks
- **Agent 04 (prompt-injection):** P0-003 keyword screen overlaps content-filtering scope.
- **Agent 05 (HIPAA):** P2-013 (referral-letter PHI leak) is a `45 CFR §164.502(b)` minimum-necessary issue.
- **Agent 07 (cost):** P1-008 token-budget needs cost ceiling.
- **Agent 11 (resilience):** P1-007 absent Whisper fallback hits outage runbook.
- **Agent 12 (claims):** Five marketing claims fail accuracy ("auditor reviews every note", "supports peds dosing", "Whisper fallback", "8th-grade summaries", "10 specialty templates").

## Things the model is trusted to do without verification (27 explicit)
1. Empty/silent audio → empty SOAP (prompt only)
2. Emitted ICD-10 code is real (regex shape only)
3. Emitted 5-digit CPT is real (regex shape only)
4. E&M code is one of 8 valid 99202-99205/99211-99215 (regex only)
5. CPT modifier on AMA list (any 2-digit accepted)
6. Suicidal-ideation screening occurs in psych visits (prompt only)
7. Drug-drug interactions flagged (prompt only)
8. Allergy ↔ Rx class match detected (prompt only)
9. Pediatric mg/kg dosing correct (prompt only; weight not captured)
10. Patient utterance ≠ doctor order in Plan (prompt only)
11. Speaker attribution correct (Claude classifies; 0.7 floor)
12. Source-of-claim preserved through L4-L7 (none — markdown loses tags)
13. Chest-pain → MI-workup red-flag (auditor model judges)
14. Peds-fever → hydration screen (auditor model judges)
15. Headache red-flag screening (auditor model judges)
16. "Per patient, …" prefix applied (prompt suggestion)
17. SOAP faithfulness to transcript (model self-checks)
18. No internal contradictions between SOAP sections (model judges)
19. Patient summary at 8th grade (FK measured, NOT enforced)
20. Referral letter minimum-necessary PHI (prompt only; no exclusion list)
21. Long transcripts usefully summarized vs silently truncated (no strategy)
22. Multi-language audio recognized (Deepgram locked `language=en`)
23. Provider outage → fallback (single retry, no provider fallback)
24. L4 markdown heading format stable across model versions (prompt only)
25. L7c "current medications" list accurate (L3 model only; no EHR sync)
26. ICD-code confidence scores reflect real uncertainty (model self-rates)
27. Patient age/DOB extracted correctly for peds threshold (L3 model only)

The pattern across all 27: every patient-harm-exposing line in the pipeline has a model-prompt instruction as its primary control. The em-coding fallback is the only reusable blueprint for adding deterministic floors. P0-001 through P0-004 + P1-005 through P1-009 together represent the minimum set of backstops to defensibly enter pilot.
