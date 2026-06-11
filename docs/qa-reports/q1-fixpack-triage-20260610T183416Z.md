# Q1 fix-pack — re-triage against current `main` (2026-06-10)

**Read-only triage. No code changed.** Re-verifies the 16 STILL-OPEN items from the 2026-05-06 Q1 fix-pack triage (PR #171, `docs/audit-reports/q1-fixpack-triage-20260506T190348Z.md`) against current production code — months of Round-3 / v3.x / note-format / Rx-safety / interpreter-mode / FIND-P1 churn may have incidentally fixed or obsoleted items. **Verified, not trusted.**

> **UPDATE 2026-06-10 — FIX-NOW batch SHIPPED (PR #296).** 09.1, 02.2, 02.8 are implemented, reviewed (code-quality-auditor SHIP), unit + real-model validated, and deployed to prod. Remaining open backlog → **9** (the FIX-LATER items below, unchanged).
>
> **UPDATE 2026-06-10 (later) — 02.8 N-2 matcher-boundary follow-up CLOSED (PR #297, prod `bfdd8509`/worker `0bec71a4`).** The deterministic Rx contraindication backstop now fires on bare-substance allergies (the gap the #296 02.8 documenting test pinned). See "Follow-ups" under the 02.8 entry. Backlog unchanged at **9** (this was a sub-item of an already-shipped fix, not a new backlog line).

Source audit: `docs/ai-pipeline-audit-phase-1-2026-05-05/`. All items scoped to `apps/transcribe-md` + `packages/ai` + `packages/shared` (no `apps/meddoc-pro`).

## Re-triage outcome

| Bucket | Count | IDs |
|---|---|---|
| **CLOSE** (incidentally fixed since 2026-05-06; evidence below) | **3** | 05.1, 03.1, 06.2 |
| **FIX-LATER — partially addressed** | 1 | 02.4 |
| **STILL-OPEN** | 12 | 01.2, 01.3, 01.4, 02.2, 02.3, 02.8, 02.9, 03.3, 03.4, 03.7, 07.1, 09.1 |
| Total (prior backlog) | 16 | |

Net: the open backlog drops **16 → 12** (3 closed, 02.4 downgraded to partial/FIX-LATER). Of the 12, **3 are FIX-NOW** (small, self-contained, pilot-relevant, not eval-suite-gated); the other 9 are FIX-LATER (eval-suite / clinical-curation / schema-design / UX / specialty-gated).

---

## CLOSE — verified fixed since the 2026-05-06 triage

| ID | What | Ground-truth evidence (current `main`) |
|---|---|---|
| **05.1** | L2 speaker-classification prompt was unwrapped (injection risk) | **CLOSED.** `02-speaker-roles.ts:18-19,184-197` — now `wrapAsData(userContent,'transcript')` + `delimiterSystemSuffix` + `PIPELINE_REJECTED_INJECTION_DELIMITER` audit-on-detection. (Shipped as fix-pack-2 Q1 #18.) |
| **03.1** | OB-GYN in `SPECIALTY_GUIDANCE` but not the catalog | **CLOSED.** `packages/shared/src/specialties.ts:28` — `{ id:'ob-gyn', label:'OB-GYN', templateId:'ob-gyn' }` + legacy string remaps (`:73-87`) + comment "canonical id post Q1 #9". |
| **06.2** | L4 + L6 had NO output validation (free-form markdown) | **CLOSED.** `apps/transcribe-md/src/worker/layers/soap-structure-validator.ts` (FIND-P1-015/016, 2026-05-14) is imported + wired into **both** L4 (`04-generate-soap.ts:21,191`) and L6 (`06-polish.ts:18,123`) via `validateSoapStructure(text, requiredSections)`. Lenient structural check before persistence — exactly the audit's recommended scope. |

---

## STILL-OPEN + FIX-LATER-partial — full triage table

| ID | What (one line) | Ground-truth (current code) | Severity / pilot impact | Effort | Deps | Rec |
|---|---|---|---|---|---|---|
| **09.1** | Anthropic content-moderation refusals not categorized → burn the full retry budget then fail slowly | OPEN — `packages/ai/src/anthropic.ts` has only a comment mention of "refusal"; no `stop_reason==='refusal'` check; `error-categorize.ts` has no `ANTHROPIC_REFUSAL` mapping (→ generous `transient` default → 3 wasted retries) | Reliability/cost. A pilot doctor on edge-case dictation hits a slow opaque failure | **S** | none (self-contained) | **FIX-NOW** |
| **02.2** | Single-speaker monologue uploaded to conversation mode → L2 still calls the model on 1 speaker | OPEN — `02-speaker-roles.ts:96` fallback fires only on `samples.size===0`; no `size===1` short-circuit | Robustness. Mode-mismatch is a real pilot footgun (dictation dropped into conversation upload) | **S** | none (self-contained) | **FIX-NOW** |
| **02.8** | Conflicting allergy info ("no allergies" then "allergic to penicillin") has no L3 conflict-resolution → the wrong one may win and drop a real allergy | OPEN — `03-extract-entities.ts` allergies schema has no `superseded` flag + no CONFLICT-RESOLUTION prompt block | **Safety** (drug-allergy = top-tier). Allergy mentions are common in pilot visits | **S–M** | additive schema field + L3 prompt | **FIX-NOW** (safety) |
| **02.9** | ROS/denial negation ("denies chest pain") has no `polarity` field → L5 red-flag-screen fires false positives the doctor sees every visit | OPEN — `ros[]` schema has no `polarity`; no negation rule | Quality + safety-screen trust; high-frequency review friction | **M** | polarity field ripples to L4/L5/L6 readers (do with schema-design pass alongside 01.4/02.8) | FIX-LATER (top priority) |
| **01.4** | L3 entity prompt is specialty-blind (no PHQ-9/GAD-7/NYHA/EF/growth-percentile structured fields) | OPEN — `03-extract-entities.ts` `COMMON_CATEGORIES` is specialty-agnostic; no per-specialty extension types | Specialties can't trend canonical measures. Pilot-relevant **only if** pilot includes psych/cardio/peds | **L** | schema design + eval suite; clusters with 02.9/03.3/03.4 | FIX-LATER |
| **03.3** | Cardiology missing structured cardiac outputs (NYHA, EF, structured exam) + cardiac CPT (93306/93015/93224-7) | OPEN — no cardiac L3 fields; cardiac CPT absent from `cpt-allowlist.ts` (verified 93306/93015/93224 = 0). (ICD HF I50.21/I50.4x WERE added — partial.) | Specialty-gated (cardiology pilot) | **L** | overlaps 01.4 + 03.7 | FIX-LATER |
| **03.4** | Pediatrics missing growth-percentile / developmental-milestone / immunization structure + peds codes | OPEN — no peds L3 fields; peds CPT (96110/99188/92551 = 0) + ICD (F88/F80/R62.51 = 0) absent. (Peds Rx safety DOB+weight already closed via 07.5/#125.) | Specialty-gated (peds pilot) | **L** | overlaps 01.4 + 03.7 | FIX-LATER |
| **03.7** | ICD-10 + CPT allowlists family-medicine-biased → valid specialty codes get dropped | OPEN (**partially mitigated**) — ICD allowlist grew **119 → 562** rows (HF I50.x, F41 anxiety added) but audit-cited psych (F40/F42/F60/F12/F19/F95), cardiomyopathy (I42), peds (F88/F80) still absent; **no** specialty CPT added (all audit-cited 0) | Specialty-gated; missing codes silently dropped from the doctor's coding rail | **M** | curate ~codes; overlaps 03.3/03.4 | FIX-LATER |
| **01.2** | L4 SOAP-gen is zero-shot; few-shot would raise quality | OPEN — `04-generate-soap.ts` prompt has no exemplars; no `soap-exemplars.ts` | Quality lift (all specialties) | **M** | needs clinical exemplars + eval suite to measure | FIX-LATER |
| **01.3** | L5 critique enumerates only 3 red-flag scenarios | OPEN — `05-self-critique.ts:150-153` still chest-pain / headache / peds-fever verbatim | Safety-critique coverage | **M** | clinical curation of ~30 chief-complaint→red-flag table | FIX-LATER |
| **02.3** | 3+ speakers / caregiver-mediated visits attribute findings to "patient" not family | OPEN — `04-generate-soap.ts` has only "Per patient,…" rule; no caregiver attribution; no `caregiver_relation` entity field | Quality for peds/geriatric pilots | **M** | L4 prompt (+ maybe L3 relation field) | FIX-LATER |
| **07.1** | L6 polish sees only draft + critique, not entities/transcript → can drift from source | OPEN — `Layer6Input` gained `noteTemplate` (note-format work) but still no `entities`/`roleLabeledTranscript`/`specialty` | Quality (polish fidelity) | **S–M** | data already loaded for L4/L5; but adds tokens → cache-key/architecture decision | FIX-LATER |
| **02.4** | Code-switching (EN↔ES/Mandarin) not handled | **PARTIAL** — interpreter-mode (`01-transcribe.ts`, 2026-05-12) added opt-in `detect_language:true` + `language:'multi'` (nova-3) for flagged interpreted visits. Residual: no auto-detect-and-flag on a *non-flagged* visit | Mitigated for known bilingual visits (operator flags them); residual not pilot-blocking | **M** | — | FIX-LATER |

Severity key: S ≤ ~half-day, M ≈ 1-3 days, L = multi-day / cross-layer.

---

## Recommended FIX-NOW batch — ✅ SHIPPED 2026-06-10 (PR #296, branch `fix/q1-pre-pilot-batch`)

A tight, low-risk, pre-pilot branch — all three small/self-contained, pilot-relevant, **not** gated on the Phase-2 eval suite. All three are implemented, code-quality-auditor SHIP, unit + real-model validated, and deployed to prod.

1. **09.1 — Anthropic refusal handling.** ✅ SHIPPED. `anthropic.ts` detects `stop_reason==='refusal'` at all 3 call sites → typed `AnthropicRefusalError` + `AI_REFUSAL` ai_calls row; `error-categorize.ts` maps it `permanent` (fail-fast into DLQ); worker emits an `AI_REFUSAL` audit + accurate reviewReason. AuditAction enum + migration. (S)
2. **02.2 — Single-speaker short-circuit.** ✅ SHIPPED. `02-speaker-roles.ts` `size===1` → dictation/doctor + needsReview, no model call. Real-model: the dictation fixture diarized to 1 speaker → the short-circuit fires. (S)
3. **02.8 — Allergy conflict resolution.** ✅ SHIPPED. Additive `superseded`/`conflict_note` + L3 CONFLICT-RESOLUTION prompt (keep BOTH, flag the contradicted one, never drop either). **Caution-first safety invariant:** `mergeAllergiesForSafety` feeds chart ∪ in-visit allergies (incl. superseded) into the Rx contraindication check — a retracted allergy still warns until the doctor resolves it. Real-model: both statements kept, superseded flagged, 0 fabrication. (S–M)

   **Follow-up — N-2 matcher boundary: ✅ CLOSED 2026-06-10 (PR #297, branch `fix/rx-allergy-match-normalization`).** #296's 02.8 documenting test pinned a pre-existing quirk: `validateRxDose`'s `allergyMatchesContraindication` matched the FULL curated needle verbatim, so needle `"penicillin allergy"` only fired when the patient string literally contained `"penicillin allergy"` — bare `"penicillin"` (exactly what L3 extracts and how charts are written) did NOT fire. The deterministic backstop missed the case the model is meant to be backstopped on. **Fix:** the matcher now also derives the bare substance from each `"<substance> allergy"` needle and matches it as a whole word (`\b<substance>(?:s|es)?\b`, regex-escaped). **Purely additive** (rule 1 = verbatim old matcher; proven 0 regressions across 231 needles × 345 strings), **word-boundary anchored** (substance `iron` matches `iron`/`irons`/`iron-dextran` but NOT `environmental`), errs toward WARNING (false positive = doctor-reviewable via override gate; false negative = the danger). **Needle audit:** 82 substance-allergy needles across 64 drugs normalize cleanly (68 distinct substances, shortest `gip`/`ppi`); 149 clinical-state needles keep substring semantics; cross-reactivity classes (penicillin↔cephalosporin, sulfa↔sulfonamide) stay OUT of scope (curated in needle lists). **Tests:** new `dose-ranges-validator-allergy-match.test.ts` (required behaviors + word-boundary guards + live-data audit + zero-FP matrix, 64 drugs × 20 benign = 1,280 combos clean) + the #296 N-2 documenting test inverted to pin the fix. code-quality-auditor SHIP-WITH-NITS (2 NITs = the deliberate over-warn tradeoff). 5/5 CI green; deployed to prod (rollback tags `:pre-rx-allergy-match` on app `3ba8922e` + worker `8a0bbaa1`). The deterministic-match proof lives at the unit layer; a live-prod pipeline smoke was attempted but blocked at prod's email-verification gate (`EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD` correctly off) — deployment health proven via `/api/health` + worker queue + CI e2e (full pipeline under MOCK, green on this commit) + bundle-assert; test residue purged to zero. (S)

**Explicitly NOT in the FIX-NOW batch:** 02.9 (polarity — do with the schema-design pass: it ripples to L4/L5/L6); 01.4/03.3/03.4/03.7 (specialty/schema/eval-gated — sequence behind the eval suite, and only if the pilot includes those specialties); 01.2/01.3 (clinical-curation + eval-gated); 02.3 (caregiver — prompt/UX); 07.1 (cache-key architecture decision); 02.4 (already mitigated by interpreter-mode).

**Sequencing note (matches the fix-pack-2 plan):** the FIX-LATER cluster is unblocked mainly by the **Phase-2 eval suite** (makes the L3-schema + prompt refactors safe to measure) + targeted clinical input. The single highest-value FIX-LATER once the eval suite lands is **02.9** (disarms a high-frequency L5 false-positive the pilot doctor would otherwise see on most visits), bundled with 01.4 in one L3-schema-design PR.
