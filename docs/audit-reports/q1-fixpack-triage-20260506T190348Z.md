# Q1 fix-pack triage — 20260506T190348Z

> ## ⚠️ SUPERSEDED — 2026-07-28
>
> **The current source of truth is
> [`docs/backlog/q1-fixpack-retriage-20260728.md`](../backlog/q1-fixpack-retriage-20260728.md).**
>
> This document is the ORIGINAL triage, taken on 2026-05-06 and shipped by
> PR #171. It is kept verbatim as the historical baseline — do not work from it.
>
> Between that date and the re-triage the app went through the C3 redesign, the
> document-first rewrite, the read-only-paper review screen, the chat editor,
> the E/M rehome and the ultrasound specialty. Six of the sixteen findings below
> had been closed by later work and nobody had marked them, and one more had
> shipped as a product feature under a different name. **A backlog that predates
> three rewrites is a list of guesses until it is re-validated** — every item was
> re-checked against `main` by re-running its own evidence query.
>
> Three of the remainder were built on 2026-07-28 (N1, §07.1, §02.9); the rest
> are parked with a written trigger. All of that is in the re-triage doc.

**Source audit:** `docs/ai-pipeline-audit-phase-1-2026-05-05/` (2026-05-05)
**Total Q1 findings in source:** 19
**Triage date:** 2026-05-06T19:03:48Z
**Triage method:** read source audit + cross-reference Round 3 PRs A-N, quality fix-pack PRs (#125-128, #130, #131), QA agent v3.x discovery reports, and current production code on `main`.

## Status breakdown

| Status | Count (Q1 strict) | Notes |
|---|---|---|
| CLOSED-BY-PR | 2 | 06.3 (PR #130), 07.3 (PR #128) |
| CLOSED-BY-PR (Q2 co-cited) | +1 | **02.5** is Q2 in source; included because PR #128 explicitly cites it alongside Q1 §07.3 in the same closure. Counted separately so the Q1 total stays honest. |
| CLOSED-INFERRED | 1 | 07.5 (PR #125, Phase-1 safety scope only) |
| SUPERSEDED-BY-F-XX | 0 | — |
| OBSOLETE | 0 | — |
| NAB-RESOLVED-BY-DRIFT | 0 | — |
| STILL-OPEN | 16 | the refreshed backlog |
| NAB-FALSE-POSITIVE | 0 | — |
| NEEDS-VERIFICATION | 0 | — |
| CANNOT-DETERMINE | 0 | — |
| **Total Q1** | **19** | (2 + 1 + 16) — strict per source-audit Q1 severity |
| **+ Q2 co-cited entries** | **1** | 02.5 |
| **Total entries in report** | **20** | |

**Refreshed backlog size: 16** (the STILL-OPEN + NEEDS-VERIFICATION count — Kasra picks the next-shippable subset from this).

> **Reconciliation note:** an earlier draft of this table reported `STILL-OPEN: 15` and `Total: 19`. The actual STILL-OPEN section below contains 16 entries (off-by-one in the original table), and the report carries one Q2 co-cited closure (02.5) on top of the 19 Q1 strict entries. Updated to be honest about both.

## Top 3 STILL-OPEN findings (by relative impact, audit-author's order)

1. **01.4** — L3 entity prompt is specialty-blind (no PHQ-9 / GAD-7 / NYHA / EF / growth-percentile structured fields). Pilot specialties literally cannot trend canonical outcome measures.
2. **02.8** — Conflicting allergy information (e.g. "no allergies" early, "I'm allergic to penicillin" later) has no L3 conflict-resolution rule. Drug-allergy errors are top-tier safety failures.
3. **02.9** — Negation in ROS / denials (e.g. "denies chest pain") has no `polarity` schema field; L3 may omit or miscode, and L5's red-flag-screening critique then fires inappropriately.

## Per-status detail

### CLOSED-BY-PR (3)

- **02.5** (`02-failure-modes.md` §02.5): Heavy accent / mumbling — Deepgram low-confidence transcripts treated as ground truth. *Note: brief listed this as Q2; including here because it's explicitly co-cited with the Q1 finding 07.3 in the closing PR.* Closed by **PR #128** (sha `820bc38`). PR explicitly cites "audit Findings 02.5 + 07.3"; aggregates per-utterance confidence into `audioConfidenceStats` JSONB column, flips `needsReview` when median <0.55 OR >30% utterances <0.6, expands L4/L5 prompts with hedge instructions.
- **06.3** (`06-output-validation.md` §06.3): L3 schema accepts empty strings as valid for required fields. Closed by **PR #130** (sha `1abe74f`). PR explicitly cites "audit §06.3"; adds `.min(1)` to every business-critical string field in `ExtractedEntities` (chief_complaint.statement, medications.name, allergies.substance, family_history.{relation,condition}, ros.{system,finding}, exam_findings.{system,finding}, tests_mentioned.test, plus the factWithEvidence wrapper). Verified at `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:53,80,92,106,118-119,138-139,150-151,162`.
- **07.3** (`07-context-flow.md` §07.3): Deepgram per-utterance confidence is captured but not propagated. Closed by **PR #128** (sha `820bc38`). PR explicitly cites Finding 07.3; aggregated stats now thread to L4 + L5 prompts via `Layer4Input.audioConfidenceStats` and `Layer5Input.audioConfidenceStats`. Per-utterance confidence is NOT yet annotated into the role-labeled transcript line-by-line (audit's "Phase 2 hard option") — the Phase-1 "soft" path is shipped, which is what the audit's "Recommended fix" §Phase 1 explicitly calls for.

### CLOSED-INFERRED (1)

- **07.5** (`07-context-flow.md` §07.5): Visit-level patient metadata (DOB / weight / allergies) doesn't reach the layers. Closed by **PR #125** (sha `dea0987`). PR cites "audit Finding 01.1" but the worker change it shipped — selecting `patient: { dateOfBirth, weightKg, allergies }` and threading into L7c — is exactly the safety-only Phase-1 fix the audit recommended in §07.5 ("Recommended fix (safety-only for Phase 1)"). Verified at `apps/transcribe-md/src/worker.ts:258-264, 679-683`. **Continuity scope not closed**: prior-visit history is still NOT pulled — the audit explicitly described that as "Phase 2 nice-to-have" and the safety scope is the Q1 Phase-1 ask.

### STILL-OPEN (16)

<!-- Header said 15 from 2026-05-06 until 2026-07-28; the list below has always
     had 16 bullets. Sixteen is right — corrected rather than left to be
     rediscovered by whoever counted next. -->

- **01.2** (`01-prompt-quality.md` §01.2): L4 SOAP-gen is zero-shot; few-shot would significantly raise quality. Evidence: `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:96-149` — system prompt still describes SOAP structure in prose with zero exemplars; no `prompts/soap-exemplars.ts` file exists. Suggested investigation: read the doctor-edit-pattern table from Phase 14.1 to see if anonymized real-visit exemplars are available; otherwise an inline 1-shot/2-shot anchor block is the audit's recommended path.
- **01.3** (`01-prompt-quality.md` §01.3): L5 critique only enumerates 3 red-flag scenarios. Evidence: `apps/transcribe-md/src/worker/layers/05-self-critique.ts:109-112` — same three examples (chest pain, new-onset headache, pediatric fever) verbatim from the audit; no `prompts/red-flags.ts` file exists. Suggested investigation: confirm the audit's shortlist of ~30 chief complaints with red-flag questions is the right scope for short-term enumeration vs. the Phase-7 structured `red_flag_check` pass.
- **01.4** (`01-prompt-quality.md` §01.4): L3 entity prompt is specialty-blind. Evidence: `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:251-291` — `COMMON_CATEGORIES` is the same constant for conversation/dictation/text modes regardless of specialty; no PsychiatryExtension / CardiologyExtension / PediatricsExtension types in the file or schema. Suggested investigation: this finding overlaps with 03.2 (Q0 deferred to Phase 2 per `POST_MERGE_TODO §26.5/26.6`) — verify whether the per-specialty extension PR sequence is gated on the Phase 2 eval suite or shippable independently for cardiology/pediatrics (Q1) ahead of psychiatry (Q0).
- **02.2** (`02-failure-modes.md` §02.2): Single-speaker monologue uploaded to conversation mode. Evidence: `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:81-101` — fallback fires only when `samples.size === 0`; when `samples.size === 1` the model is still called. Suggested investigation: confirm whether the proposed short-circuit ("if size===1, assign doctor + needsReview") is acceptable as-is, or whether mode-mismatch detection upstream of L2 is preferred.
- **02.3** (`02-failure-modes.md` §02.3): Three-or-more speakers — caregiver-mediated visits attribute findings to "patient" instead of family. Evidence: `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:138-139` — only "Per patient, …" prefix rule; no caregiver/family attribution rule; no entity-level `caregiver_relation` field. Suggested investigation: confirm whether Phase-1 "L4 prompt expansion only" scope is sufficient or whether the L3 schema lift (relation field) is required.
- **02.4** (`02-failure-modes.md` §02.4): Code-switching English ↔ Spanish / Mandarin. Evidence: `apps/transcribe-md/src/worker/layers/01-transcribe.ts` — Deepgram call has no explicit `language` param and no language-detection pre-pass; downstream prompts are English-only. Suggested investigation: verify whether Deepgram nova-3-medical's `language: 'multi'` is production-ready for the pilot specialties or whether the Phase-1 "detect + flag" path is the right scope ceiling.
- **02.8** (`02-failure-modes.md` §02.8): Conflicting allergy information. Evidence: `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:102-113` — `allergies` schema has no `superseded` flag; L3 prompt at lines 299-307 has no CONFLICT RESOLUTION block. Suggested investigation: confirm scope — schema-only vs. paired schema + L3/L4 prompt change in a single PR.
- **02.9** (`02-failure-modes.md` §02.9): Negation handling in ROS. Evidence: `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:134-145` — `ros[]` schema has no `polarity` field; prompt has no negation-extraction rule. Cross-references finding 06.8. Suggested investigation: verify the L5 red-flag-screening critique's current false-positive rate to scope priority — this is the structural fix that disarms a known L5 noise source.
- **03.1** (`03-specialty-fit.md` §03.1): OB-GYN exists in `SPECIALTY_GUIDANCE` but not in the catalog. Evidence: `packages/shared/src/specialties.ts:22-32` — `SPECIALTIES` array has 9 entries, no `'ob-gyn'`; lines 69-70 + 78 still map OB-GYN strings to `'unspecified'`. Suggested investigation: check whether any production rows currently hold the legacy `'OB-Gyn'` / `'Obstetrics & Gynecology'` strings (informs whether a Prisma data migration is needed).
- **03.3** (`03-specialty-fit.md` §03.3): Cardiology pilot missing structured cardiac outputs (NYHA, EF, structured cardiac exam, vital trend). Evidence: `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:76-174` — no cardiology fields; `packages/ai/src/data/cpt-allowlist.ts` does not contain 93306/93307/93015/93224/93225/93226/93227. Suggested investigation: this overlaps with 03.7 (allowlist) — verify whether the cardiology schema PR and the allowlist PR can/should be one PR or split.
- **03.4** (`03-specialty-fit.md` §03.4): Pediatrics missing growth + developmental structure. Evidence: `apps/transcribe-md/src/worker/layers/03-extract-entities.ts:76-174` — no `growth_percentile` / `developmental_milestones` / `immunization_status` fields. Note: peds Rx safety wiring (DOB+weight) is closed via 07.5/PR #125 — this finding's residual scope is the L3 schema additions plus allowlist (overlap with 03.7). Suggested investigation: confirm whether peds growth-percentile fields are pilot-blocking vs. Phase-7-deferrable.
- **03.7** (`03-specialty-fit.md` §03.7): ICD-10 + CPT allowlists have a family-medicine bias. Evidence: `packages/ai/src/data/icd10-allowlist.ts` — 119 ICD codes (verified by line count `199` total + `grep` of code-rows = `119`); audit's gaps (F40/F42/F60/F12/F19/F50/F95/R45.851/Z63 on psychiatry; cardiology I50.21-I50.43/I42.x; peds F88/F89/F80.x/R62.51/Z28.x) — none are present. CPT gaps (93306/93307/93015/93224-93227 on cardiology, 96110/99188/92551 on peds, 59025/76801/76802 on OB, 64483/27096/64493 on pain) — none are present. Suggested investigation: confirm whether to ship the audit's hand-curated ~150-code expansion now or wait for the Phase-7 swap to the full CMS canonical list.
- **05.1** (`05-prompt-delimiter-coverage.md` §05.1): L2 speaker-role classification is unwrapped. Evidence: `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:104-110, 136` — `blocks.join('\n\n')` is used as the user message with no `wrapAsData()` call (verified by grep of file: zero `wrapAsData` references). Suggested investigation: pattern-copy from L3 should be straightforward; verify the audit-action enum already has `PIPELINE_REJECTED_INJECTION_DELIMITER` (added in PR #123) so no Prisma migration is needed.
- **06.2** (`06-output-validation.md` §06.2): L4 + L6 have NO output validation (free-form markdown). Evidence: `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:161-180` — `modelClient.completeText` returns `text` and `text.trim()` is the only verification; `apps/transcribe-md/src/worker/layers/06-polish.ts:74-89` — same shape; no `soap-validator.ts` file in `apps/transcribe-md/src/worker/layers/`. Suggested investigation: confirm whether the audit's structural validator (heading checks + preamble guard + length plausibility) is the right scope vs. a tighter "first-line is `## Subjective`" check.
- **07.1** (`07-context-flow.md` §07.1): L6 polish doesn't see transcript or entities — only draft + critique. Evidence: `apps/transcribe-md/src/worker/layers/06-polish.ts:20-26` — `Layer6Input` is `{visitId, practiceId, userId, soapDraft, critique}`; no `entities` / `roleLabeledTranscript` / `specialty` fields. Suggested investigation: verify the worker plumbing change is small (the data is already loaded for L4/L5) and whether the L6 prompt expansion is single-PR scope or wants test fixtures.
- **09.1** (`09-error-handling.md` §09.1): Content-moderation refusals not categorized; waste retries (cross-reference of 06.5). Evidence: `packages/ai/src/anthropic.ts:1-120` — no `stop_reason === 'refusal'` check (only one mention of "refusal" at line 54 in a comment header); `apps/transcribe-md/src/worker/error-categorize.ts` — no `ANTHROPIC_REFUSAL` errorCode mapping. Suggested investigation: confirm Anthropic SDK's current refusal stop_reason shape (the audit predates SDK API changes that may have moved this); verify whether `ANTHROPIC_REFUSAL` enum value needs adding to `AuditAction`.

## NAB closures

None. No Q1 finding was marked NAB-FALSE-POSITIVE in this triage.

## Notes

- **Original audit count:** 19 Q1 findings (verified by `awk` over each finding file matching `^## [0-9]+\.[0-9]+` headers paired with `**Severity:** Q1` lines).
- **Triage count:** 19 (no findings dropped, no findings added).
- **Audit-doc surprise #1:** PR #130 (`fix(quality-fp2)`) labels itself a "Q2 quick-wins bundle" but the source audit explicitly classifies §06.3 as **Q1**, not Q2. PR #130 closes the surface anyway. Honest accounting still credits §06.3 as CLOSED-BY-PR — the severity-label drift between PR title and audit is just a tagging mismatch, not a closure gap.
- **Audit-doc surprise #2:** Finding §09.1 is labeled Q1 in `09-error-handling.md`, but the *same surface* is labeled Q2 at §06.5 in `06-output-validation.md` (the §09.1 entry says "Already documented in Finding 06.5 — listed here for the error-handling audit"). I treated §09.1 as the Q1 entry per the strict-reading rule (it's the Q1-tagged copy). Closing one closes the other.
- **Audit-doc surprise #3:** Finding §07.5's "Recommended fix" text explicitly carves out "safety-only for Phase 1" as the Phase-1 scope (DOB+weight+allergies → L7c) and labels prior-visit continuity as Phase 2. PR #125 shipped exactly the safety-only scope. I'm calling that CLOSED-INFERRED on the audit's own Phase-1 framing — but if a stricter reading (full text of the finding including continuity) is preferred, this becomes STILL-OPEN and the backlog size lifts to 16.
- **POST_MERGE_TODO confirms the structure:** `docs/POST_MERGE_TODO.md §26.5/26.6` lists 4 Q0 closures (#125 / #126 / #127 / #128) and explicitly declares "❌ Any Q1 finding — those land in Fix-Pack 2 (recommend shipping Phase 2 eval suite first; see audit recommendations §10)." This triage's 15 STILL-OPEN matches the project's own published intent: the Q1 batch is unshipped pending Phase 2 eval-suite gating.
- **No QA-agent-v3.x supersede applied:** I scanned `docs/qa-reports/*.md` for keyword overlap (audio confidence, refusal, content-moderation, finding numbers) — no v3.2/v3.3 discovery report has surfaced a more-specific F-XX number that subsumes any Q1 in this list. The v3.x agent's discovery reports cover UI/walker findings (F-07 through F-16, etc.); they don't overlap the AI-pipeline audit surface.
- **Out-of-scope check:** No Q1 finding referenced `apps/meddoc-pro` (memory #9). All 19 are scoped to `apps/transcribe-md` + `packages/ai` + `packages/shared`.
