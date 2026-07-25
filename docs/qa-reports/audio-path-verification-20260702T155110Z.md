# Real voice/audio path — end-to-end verification + follow-up closure

**Run:** 2026-07-02, autonomous. Branch `fix/audio-path-and-followups` → PR #352.
**Why:** the record/dictation segment was the ONE pipeline path never exercised on the current build with real media (all prior QA used `text_notes`; the recorder was walker-tested with mocked media — the committed specs explicitly bypass MediaRecorder, a documented gap since T-M10). Doctors dictate by voice, including ultrasound studies.

## Honest caveat (up front, as required)
The dictations are **studio-clean TTS speech** (Higgsfield Seed Audio, natural US voices, quiet channel). This run proves the **PATH** — mic → MediaRecorder → upload → MinIO → Deepgram nova-3-medical → full pipeline → gates/audit — and **number/dose/negation fidelity under clean conditions**. It does NOT prove real-world ASR robustness (accents, pace, clinic noise, phone mics). The doctor test remains the true voice validation. Notably, even clean TTS produced one genuine drug-name ASR error (below) — expect more in the wild.

## Part 1 — QA real-audio E2E (real Deepgram + Opus, anchors ON): **4/4 + drill**

Method: 3 synthesized dictations (78s dense PCP, 54s venous reflux, 29s DVT) converted to 48kHz mono PCM WAV and fed to the REAL "Dictate live" UI via Chromium `--use-fake-device-for-media-stream --use-file-for-fake-audio-capture` (real audio content through the real recorder — mic permission, record timer, "Stop & process", chunked webm/opus upload; NOT the request-level bypass the committed specs use).

| Check | Result |
|---|---|
| Recorder UI → upload → MinIO → worker → Deepgram | **PASS** ×4 visits; `transcriptionProvider='deepgram-batch'` recorded; `AUDIO_UPLOADED` audit rows; magic-byte sniff passed (webm/opus) |
| Transcript fidelity, dense PCP (9 hard checks) | **9/9** — BPs (incl. Deepgram's hybrid "one fifty four over 94" form), amlodipine 10, simvastatin 40, metformin 1000, A1c 8.1, weight 92.3, "denies chest pain", "no murmurs" all survived |
| **Drug-name ASR error (found + handled correctly)** | Deepgram transcribed "lisinopril" as **"LISAAR"**. The pipeline behaved exactly per design: the note stayed transcript-faithful ("Start LISAAR 10 mg daily" — no silent correction), and **L7c flagged it**: *"Plan text reads 'LISAAR' which is ambiguous — interpreted as lisinopril based on the entities and assessment — verify"*. Class-(a) ASR propagation with a compensating Rx-layer control. This is the strongest single argument for the doctor-review workflow. |
| **Pair warning FROM VOICE** | **PASS** — `critical: [deterministic] Simvastatin 40 mg/day exceeds the 20 mg/day maximum with amlodipine…` fired on the voice visit; sign → **422**; `RX_DRUG_PAIR_DOSE_CAP` audit row written (the new audit leg, observed live); E/M 99214 |
| **Ultrasound by voice** | **PASS** — Exam→Impression all present; every measurement survived voice→ASR→report (6.1 mm, 4.2 s, 5.2 mm, 3.1 s, 3.8 mm; body+lane accounting); laterality correct; E/M null; no spurious coding nag |
| DVT by voice | **PASS** — left popliteal DVT impression + right-leg-negative preserved |
| Audit trail | VISIT_CREATED / AUDIO_UPLOADED / RX_DRUG_PAIR_DOSE_CAP / VIEWED_VISIT rows per visit |

### Fallback drill (QA only)
Recon correction first: an **invalid Deepgram key is the PERMANENT error path** — fallback deliberately never engages there (fail-fast, no cross-provider hop). The correct drill breaker is a **transient** failure: `api.deepgram.com` DNS black-holed on the QA worker + `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=true` + the OpenAI key.

Result: Deepgram failed transient → retries → **the Whisper fallback ENGAGED and sent the request to OpenAI** — which returned **401: the `OPENAI_API_KEY` in prod `.env` is invalid/rotated**. The visit then failed closed with a clean doctor-facing reason (correct behavior with a dead key). So:
- Fallback **gate + engagement mechanics: PROVEN** (the request left for OpenAI).
- Whisper transcription + `TRANSCRIPTION_PROVIDER_FALLBACK` success row + `transcriptionProvider='whisper-fallback'`: **NOT completable — blocked by the dead key**, not by product code.
- **NEW OPERATIONAL FINDING for Kasra: the OpenAI key is dead.** This also breaks the Doc Editor + its eval suite (OpenAI-only per policy). Prod impact of the fallback itself: none — the flag is OFF everywhere (BAA posture unchanged; enabling it was already gated on the OpenAI BAA).
- Worker fully restored after the drill (flag unset, DNS normal, verified).

## Part 2 — Prod audio smoke: **PASS** (1.4m)
One real voice dictation (29s DVT study) through the prod recorder on app.quillmd.com: mic → record → "Stop & process" → Deepgram (`transcriptionProvider='deepgram-batch'`) → imaging report with `## Impression`, left-popliteal DVT content, E/M null, clean review lane (no coding nag). Cleanup: dictation audio object deleted from prod MinIO, all rows deleted transactionally; **baseline verified — 1 pre-existing visit (kasra.rayat@gmail.com), 0 residue**; co-tenants 200; 9/9 containers healthy.

## Part 3 — Follow-ups closed (PR #352)
1. **RX_DRUG_PAIR_* audit rows:** migration `20260702153000` (ADD VALUE IF NOT EXISTS precedent ×3 — the two pair codes + the PR-D-deferred `RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY`); 07c writes rows with the PR-D metadata contract ({ruleId, primaryDrug, otherDrug, severity, doseMgPerDay?}; never message/evidence_quote). **Observed live from a voice visit on QA.**
2. **"Twice nightly" sig** → 2 doses/day (before the once-nightly branch; additive-only).
3. **ICD empty-nag dedup:** pass-2's icd branch now requires the `icdResumed` hint. Root analysis: fresh ok-runs ALWAYS carry 07a's own specialty-aware empty-codes flag (its UPDATE is awaited before the column write; a throw lands in pass-1 'failed'), so pass-2 there was pure duplication — the doubled "Auto-coding… Click Retry" banner. Resumed attempts (attempt-start reset wiped the flag; T-M13 skips L7a since `{codes:[]}` counts as populated) keep pass-2 as the SOLE silent-empty guard. cpt branch + ICD generation untouched. Residual wart documented: on resumed empty-ICD attempts the Retry CTA still can't clear the banner (carve-out costed, deferred).
4. **Referrals:** demographics only when explicitly stated — never inferred ("(age inferred)" class killed at the prompt). Patient-summary "goal values" class noted (07e) — not fixed here.

## Ship trail
- Unit tests: **1827/1827**. Frozen #346 surfaces byte-identical (no verifier-adjacent diff → no fabrication eval trigger).
- code-quality-auditor: **SHIP-WITH-NITS, 0 BLOCK, 5/5 hard constraints PASS** (incl. mechanical theft-testing of the sig regex and the sole-guard analysis of the ICD dedup); WARN + 2 NITs remediated (comment scoping, DB-blip paragraph, blip canary).
- CI (6): **ALL GREEN** · squash-merge: **main `ac91dfe`** (PR #352).
- prod deploy: **LIVE** — `db-migrate` rebuilt + `migrate deploy` applied `20260702153000` BEFORE the worker rollout (enum-precedent deploy order); app + worker rebuilt + deployed; enum value verified queryable on prod. Rollback tags **`pre-audio-20260702`** (app + worker; the migration is additive enum values — rollback-safe without reverting it).
- prod audio smoke + baseline restore: **PASS** (Part 2 above).

## GO/NO-GO for doctor handoff: **GO — with two disclosures**

**GO.** Every segment a doctor will touch is now proven on the current build with real media and real models: voice recording → Deepgram → note/report → safety gates → sign → export; text input; custom templates; ultrasound reports by voice with exact measurements; the drug-pair safety floor firing from voice with the fail-closed 422 gate; HIPAA audit rows on all of it.

Disclosures for the doctor test:
1. **ASR reality:** our voice validation used clean TTS speech. It proved the path and number/dose fidelity — and even then Deepgram turned "lisinopril" into "LISAAR" once. The product handled it exactly right (transcript-faithful note + an explicit Rx ambiguity warning), but the doctor should expect to review drug names, and their real-speech results are the true test.
2. **Whisper fallback is OFF (by design, BAA posture)** — a Deepgram outage fails visits cleanly rather than silently shipping audio to OpenAI. The drill proved the fallback mechanics engage correctly if ever enabled, but completing that path needs (a) the OpenAI BAA and (b) a VALID OpenAI key — **the current prod `OPENAI_API_KEY` is dead (401), which also breaks the Doc Editor evals today. Kasra: rotate/replace the key.**

Open (small): resumed-attempt empty-ICD Retry copy still dangling (carve-out costed, deferred); patient-summary "goal values" boilerplate class (07e) unfixed.
