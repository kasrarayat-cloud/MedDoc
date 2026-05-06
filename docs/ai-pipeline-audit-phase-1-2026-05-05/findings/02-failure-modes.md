# Finding 02 — Degraded-input failure modes

For each scenario below, the table is: what the pipeline does
today, whether the output is wrong/dangerous, and whether it
fails-closed (rejects with audit row) or fails-open (produces
garbage silently).

---

## 02.1 — Silent / near-silent audio

**Severity:** Q3 (covered well by PR-D guard)
**Layer affected:** L1 → guards.ts
**Quality dimension:** robustness

### What happens today

Two-tier defense:
1. `assertSufficientTranscript` (guards.ts) — rejects if
   `audioDurationSec < 3` OR transcript word count < 10.
2. Audit row `PIPELINE_REJECTED_TOO_SHORT` /
   `PIPELINE_REJECTED_INSUFFICIENT_TRANSCRIPT` emitted.

Doctor sees a clear `humanReason` banner.

### Verdict
**Fails-closed cleanly.** Well-handled. Round 3 PR-D earned this.

### Residual gap (Q3)
Long audio with mostly silence + brief speech (e.g., 5-min
recording with 30s of clinical content + 4.5min ambient noise)
passes the duration guard and may have ≥10 words. Model
generates a thin SOAP. **Recommended next step**: a
"clinical-content density" heuristic — fraction of utterances
with medical terminology — could fire as a soft-warning to flag
"transcript appears to have low clinical density".

---

## 02.2 — Single-speaker monologue (audio uploaded by mistake to conversation mode)

**Severity:** Q1
**Layer affected:** L1 → L2 (orchestration)
**Quality dimension:** robustness

### What happens today

L1 transcribes with `diarize: true`. Deepgram returns 1 speaker
ID. L2's `groupSamplesBySpeaker` returns a Map of size 1.
`02-speaker-roles.ts:82-102` — when `samples.size === 0` the
fallback is "single-speaker doctor". When size is 1 the fallback
isn't taken; the model is asked to classify a single speaker.

The model usually gets it right (assigns "doctor" with
confidence ~0.7-0.9), but the prompt's "patient/family/other"
options invite a misclassification.

### Why it matters

L3 conversation mode then builds a role-labeled transcript with
every line tagged `[Patient #0, ...]` if L2 misclassified — and
L4 produces a SOAP that treats everything as patient
self-report (with "Per patient, …" prefixed inappropriately).

### Verdict
**Fails-open.** Misclassification produces a wrong-shape SOAP.

### Recommended fix

In `02-speaker-roles.ts`, before the model call: if
`samples.size === 1`, **skip the model call** and assign the
single speaker as `doctor` (highest base rate when audio is
single-speaker — usually a doctor accidentally uploaded to
conversation mode). Set `needsReview: true` with reason "Audio
appears single-speaker; treated as doctor dictation. Re-upload
as voice dictation if intended."

This forces the orchestration to either skip diarization or to
use the dictation pipeline. Better: detect mode mismatch
upstream and offer the doctor a one-click path to re-process as
dictation.

### Estimated PR scope
**Small** — short-circuit in L2 + handle the redirected mode in worker.ts.

---

## 02.3 — Three-or-more speakers (family member + patient + doctor)

**Severity:** Q1
**Layer affected:** L2 → L3
**Quality dimension:** specialty-fit (pediatrics / geriatrics)

### What happens today

L2 handles 3+ speakers with the same prompt — the model assigns
roles. Common in pediatric (parent + child) and geriatric
(spouse + patient) visits.

`SAMPLE_SIZE = 5` per speaker — for a 3-speaker visit that's
15 utterances total to classify three roles. Often enough.

L3 builds a role-labeled transcript with all 3 roles.

L4 SOAP generation has to attribute findings: "Per patient, …"
vs "Per mother (caregiver), …". The L4 prompt at line 100
mentions:

> "When information came exclusively from the patient, prefix
>  with 'Per patient, …'"

It does NOT specify the family/caregiver case explicitly.

### Why it matters

Pediatric visits are caregiver-mediated. Most clinical info
comes through the parent. The SOAP often reads like the patient
self-reported when actually the mother said it. This conflates
who provided the history — important for clinical and legal
documentation.

### Verdict
**Fails-open.** Output is plausible but mislabels source-of-info.

### Recommended fix

L4 prompt expansion:

```
SOURCE-OF-INFO ATTRIBUTION:
- "Per patient, …" — info reported by patient directly
- "Per [relation], …" — info reported by family/caregiver
  (e.g., "Per mother, …", "Per spouse, …", "Per daughter, …")
- "Per clinician observation, …" — info from the doctor's
  exam
- For pediatric visits, default to "Per [parent], …" when
  the entity's `speaker` is "Family" — the relation should
  come from the entity's evidence quote when available.
```

L3 should also expand `family_history` / chief_complaint
schemas to capture the relation explicitly when the speaker is
non-patient.

### Estimated PR scope
**Small** for the prompt; **Medium** if combined with L3 schema.

---

## 02.4 — Code-switching (English ↔ Spanish, English ↔ Mandarin)

**Severity:** Q1
**Layer affected:** L1 → L2 → L3 → L4
**Quality dimension:** accuracy, robustness

### What happens today

L1 calls Deepgram with `nova-3-medical` model. **Language is
not explicitly set** in the call — Deepgram auto-detects from
the first ~10 seconds of audio. For a Spanish-English bilingual
visit, auto-detect typically picks one language and transcribes
the other half as garbled.

L2 + L3 + L4 prompts are English-only. Spanish content gets
processed but with degraded accuracy.

### Why it matters

The pilot population includes Iranian/Middle Eastern (per
`deepgram-vocabulary.ts` comment about "Iranian / ME brand
spellings"), and a non-trivial fraction of US ambulatory care is
bilingual. A Spanish-fluent patient describing chest pain in
Spanish will have the symptom characterization mangled.

### Verdict
**Fails-open silently.** Output is plausibly-shaped English SOAP
that misrepresents what the patient said.

### Recommended fix

Three-step:
1. **Detect**: Add a language-detection pre-pass on L1's
   transcript. Deepgram returns `language` per utterance — sum
   it. If >10% of utterances are non-English, flag.
2. **Transcribe per-language**: For mixed-language visits,
   call Deepgram with `language: 'multi'` (which is
   supported on nova-3) for proper multi-lang handling, OR
   fall back to splitting the audio by detected-language and
   running once per language.
3. **Translate-and-flag**: For L3+L4, append a system-prompt
   note: "Some utterances are in [language X]. Treat them
   identically to English for SOAP generation; if a non-English
   medical term lacks a clear English equivalent, preserve the
   original term in the SOAP and add the English gloss in
   parentheses."

For pilot: at minimum, language-detect + flag. Full multi-lang
SOAP generation is Phase 7+.

### Estimated PR scope
**Medium** — Deepgram param tuning + language detection +
prompt updates.

---

## 02.5 — Heavy accent / mumbling (Whisper or Deepgram garbled output)

**Severity:** Q2
**Layer affected:** L1 (transcription quality)
**Quality dimension:** accuracy, robustness

### What happens today

Deepgram returns transcripts even when confidence is low. L1
persists the transcript without filtering on confidence.
Layers 2-6 process the garbled text as ground truth.

### Why it matters

The downstream L4 SOAP is built on the garbled transcription —
the model invents plausible-sounding clinical content from
garbled utterances. This is one of the fabrication-risk paths
the PR-D guards (Finding 02.1) DON'T catch — there are >10
words and >3s audio, just with low fidelity.

### Verdict
**Fails-open.** SOAP based on a garbled transcript reads
confident but is clinically unreliable.

### Recommended fix

Transcript-quality scoring at L1:
- Sum per-utterance `confidence` from Deepgram (the API
  returns this)
- If mean utterance confidence < 0.7, flag visit with
  `needsReview: true, reviewReason: "Audio confidence is
  below our threshold; SOAP may misrepresent the visit."`
- Don't HALT the pipeline — produce the SOAP, but make sure
  the doctor sees the warning before signing.

### Estimated PR scope
**Small** — L1 confidence aggregation + reviewReason update.

---

## 02.6 — Off-topic content (patient chats about kids' soccer for 3 minutes)

**Severity:** Q2
**Layer affected:** L3 → L4
**Quality dimension:** completeness, signal-to-noise

### What happens today

L3 sees the entire transcript and is told "If the transcript is
silent on a category, return [] (or null)". The kids-soccer
content has no clinical entities to extract — L3 returns
nothing for that segment.

L4 prompt says "Use ONLY the entities provided and the
transcript as evidence." If L4 reads the transcript, it sees
the soccer content too. The L4 prompt doesn't explicitly tell
the model to ignore non-clinical content.

### Why it matters

Most of the time the model correctly ignores the soccer
content. Sometimes it weaves it into the social_history
("Patient discussed family activities including children's
soccer participation"), which dilutes the clinical relevance
of the SOAP.

### Verdict
**Fails-open at low rate.** Output isn't dangerous but is noisy.

### Recommended fix

L4 prompt addition:

```
NON-CLINICAL CONTENT FILTER:
- The transcript may contain non-clinical conversation
  (small talk, weather, family activities). Do NOT include
  this in the SOAP unless it has clinical bearing
  (e.g., a job change with stress impact = social history;
  a planned trip with travel-related health concern =
  preventive plan).
- Treat the transcript like a clinician dictating: keep
  only what's clinically actionable.
```

### Estimated PR scope
**Trivial** — prompt-only.

---

## 02.7 — Inaudible critical info (doctor whispers "diabetes type 2" → transcribed as "diabetes")

**Severity:** Q2
**Layer affected:** L1 → L3 → L4 (cross-cutting)
**Quality dimension:** specificity, accuracy

### What happens today

Deepgram returns "diabetes" (loss of specificity).
L3 extracts `past_medical_history: [{condition: "diabetes"}]`.
L4 SOAP says "PMH: Diabetes". L7a ICD coding picks E11.9
("Type 2 DM without complications") as a default — which may
be right, or may be wrong (E10.x for type 1).

### Why it matters

The model can default to a coding choice that's clinically
plausible but unverified. ICD-10 E11.9 vs E10.9 is a real
difference (different management, different med list).

### Verdict
**Fails-open.** The L7a allowlist filter catches the structural
side (code is real) but not the specificity question.

### Recommended fix

L7a prompt addition:

```
SPECIFICITY GUARDRAIL:
- If the SOAP says "diabetes" without specifying type 1 vs 2,
  use E11.9 (most common in adult ambulatory) AND emit a
  confidence ≤ 0.7 with note "diabetes type unspecified —
  verify before billing" in the description.
- Same pattern for "asthma" (J45.909 unspec vs J45.20
  intermittent vs J45.40 moderate persistent), "hypertension"
  (I10 essential vs I15.x secondary), etc.
- Never invent a more-specific code than the SOAP supports.
```

This ties confidence scoring directly to specificity — the UI
already maps confidence to color (red/amber/green).

### Estimated PR scope
**Small** — L7a prompt expansion.

---

## 02.8 — Conflicting information (patient says "no allergies" early, "I'm allergic to penicillin" later)

**Severity:** Q1
**Layer affected:** L3
**Quality dimension:** safety, accuracy

### What happens today

L3 processes the transcript linearly. If both statements appear
in the entities, both get extracted. The schema's `allergies`
array could contain `[]` (denied early) AND
`[{substance: "penicillin"}]` (asserted late) — but in practice
the model usually picks one.

The L3 prompt doesn't say which to prefer when there's
conflict. Often the LATER statement wins (correctly), but not
always.

### Why it matters

Drug-allergy errors are top-tier safety failures. If the
allergic-to-penicillin claim is dropped because the
"no allergies" came first, and the doctor prescribes amoxicillin,
the dose validator won't catch it (penicillin allergy isn't in
the structured allergies field).

### Verdict
**Fails-open.** Dangerous if conflict goes the wrong way.

### Recommended fix

L3 prompt addition (CRITICAL section):

```
CONFLICT RESOLUTION:
- If the same category contains contradictory statements
  (e.g., "no known allergies" early AND "allergic to penicillin"
  later), include BOTH but mark the more-permissive one as
  superseded:
    "allergies": [
      {"substance": "no known drug allergies", "evidence_quote": "...", "superseded": true},
      {"substance": "penicillin", "evidence_quote": "actually I had a reaction to amoxicillin once"}
    ]
- Generally, the LATER, more-specific statement is the source
  of truth — but emit both so the doctor can review and audit.
```

L4 then reads `superseded: true` and excludes from the SOAP's
allergy list, but the auditor can see the trail.

### Estimated PR scope
**Small** — schema + L3 prompt update + minor L4 prompt update.

---

## 02.9 — Negation / patient denies a condition the doctor diagnoses

**Severity:** Q1
**Layer affected:** L3 → L4
**Quality dimension:** accuracy

### What happens today

L3 extraction has no specific negation handling. If the
transcript says "Patient denies chest pain", L3 may create:
- `ros: [{system: 'cardiovascular', finding: 'chest pain', evidence_quote: 'denies chest pain'}]` — wrong shape (should be NEGATIVE finding)
- OR `ros: [{system: 'cardiovascular', finding: 'no chest pain', ...}]` — right shape
- OR omits entirely — wrong (negative-finding documentation matters)

The L4 prompt says ROS should be "by system when documented"
but doesn't specify how to render negative findings.

### Why it matters

Negative findings are clinically meaningful — "ROS negative
for chest pain, SOB, palpitations" is documentation that
red-flags were screened. If L3 omits or miscodes negations,
L5's red-flag-screening critique fires inappropriately.

### Verdict
**Fails-open at moderate rate.** L5's red-flag check sees missing
ROS-negative documentation that's actually present.

### Recommended fix

L3 schema extension:

```typescript
ros: z.array(
  z.object({
    system: z.string(),
    finding: z.string(),
    polarity: z.enum(['positive', 'negative']),  // NEW
    evidence_quote: z.string().min(1),
    speaker: z.string().optional(),
    timestamp: z.number().nonnegative().optional(),
  })
).default([]);
```

L3 prompt addition:
```
NEGATION:
- "Denies chest pain" → polarity: "negative", finding: "chest pain"
- "Reports no shortness of breath" → polarity: "negative"
- "Has chest tightness on exertion" → polarity: "positive"
- Always extract the finding even when negative — negative-
  finding documentation is clinically meaningful.
```

L4 then renders ROS as:
```
ROS — Cardiovascular: denies chest pain, denies palpitations.
       Respiratory: reports occasional cough.
```

L5 red-flag check uses the polarity to verify a screen WAS
documented (positive or negative both count) rather than
misreading "no entry" as "not screened".

### Estimated PR scope
**Medium** — schema + L3/L4 prompts + L5 critique consumption.

---

## 02.10 — Hypothetical / rule-out language ("could be", "rule out", "differential includes")

**Severity:** Q2
**Layer affected:** L3 → L4 → L7a
**Quality dimension:** accuracy, billing-safety

### What happens today

L3 prompt warning at line 51-54 of `07a-icd-coding.ts`:

> "Code ONLY active problems the clinician addressed at THIS
>  visit.
>  Do NOT code 'rule out' diagnoses or historical conditions
>  that did not affect today's plan."

L7a is told NOT to code rule-outs. ✓ Good.

But L3 has no specific rule-out handling. A "differential
includes IBS" comment by the doctor may end up in
`assessment_discussed` as a flat string. L4 then writes
"Assessment: …; differential includes IBS" and L7a may try to
code IBS (K58.0).

The L7a "do NOT code rule-out" rule helps catch this BUT
relies on the model recognizing "differential includes" as
rule-out language.

### Why it matters

Coding a rule-out as a confirmed diagnosis is a billing fraud
exposure (False Claims Act). The L7a prompt addresses it but
relies on natural-language pattern recognition.

### Verdict
**Fails-open at low rate** if L4 prose lacks the rule-out
markers.

### Recommended fix

Extract rule-out structure earlier — at L3:

```typescript
assessment_discussed: z.array(
  z.object({
    finding: z.string(),
    status: z.enum(['confirmed', 'differential', 'rule_out', 'historical']).default('confirmed'),  // NEW
    evidence_quote: z.string().min(1),
    ...
  })
).default([]);
```

L3 prompt:
```
ASSESSMENT STATUS:
- "confirmed" — doctor stated as the working diagnosis
- "differential" — listed as one of multiple possibilities
- "rule_out" — actively being excluded ("rule out PE", "r/o
  acute MI")
- "historical" — past condition mentioned for context, not
  active today
```

L4 prompt then renders differential / rule_out distinctly
in the Assessment section. L7a strictly codes only `confirmed`
items, deterministically — no natural-language pattern
matching needed.

### Estimated PR scope
**Medium** — schema + L3/L4 prompt + L7a logic update.

---

## 02.11 — Doctor dictating after patient leaves (mid-visit dictation pivot)

**Severity:** Q2
**Layer affected:** L1 → L2
**Quality dimension:** robustness

### What happens today

A common workflow: doctor records the conversation, then after
the patient leaves continues recording while dictating their
own assessment + plan. The audio has both modes.

L1's `01-transcribe.ts` runs with `diarize: true`. Deepgram
will still split the post-patient-leaves portion into the
"doctor" speaker. L2 classifies appropriately.

But the L4 prompt sees a transcript where the doctor "talks
to themselves" extensively in the post-patient portion. The
"Per patient, …" attribution rule doesn't apply there, so the
SOAP looks fine.

### Verdict
**Mostly handled** — accidental robustness from the role
attribution rules.

### Residual gap (Q3)
If diarization fails to mark the post-patient portion as a
separate phase, the model could attribute doctor's reflective
comments to the patient. Rare; low impact.

---

## 02.12 — Visit aborted mid-conversation

**Severity:** Q3
**Layer affected:** orchestration / L1
**Quality dimension:** completeness

### What happens today

Audio is shorter than expected. PR-D guards catch this if it
falls below 3s OR <10 words. Otherwise pipeline runs, produces
a SOAP that's missing later sections (e.g., no plan).

L4 will produce sections marked `[not documented]` for missing
content. ✓ Acceptable.

### Verdict
**Handled.** No new finding.

---

## 02.13 — Transcript with 90% small talk, 10% clinical content

**Severity:** Q2
**Layer affected:** L3 → L4 → L5
**Quality dimension:** signal-to-noise

### What happens today

L3 extracts the clinical 10% correctly (ignores small talk per
the "OMIT IT" rule). L4 produces a thin but accurate SOAP.

The risk: L5 critique may flag the SOAP as "underdeveloped"
because most ROS/exam sections are `[not documented]`. The
needsReview banner fires on a visit where the brevity is
honest.

### Verdict
**Fails-open at low rate** — false-positive review flags.

### Residual mitigation
Surface the visit duration alongside the L5 review reason.
"15-min recorded visit; SOAP brevity reflects visit content."

### Recommended fix

L5 prompt addition:
```
LOW-CONTENT VISITS:
- A short visit (under 5 minutes of clinical conversation)
  legitimately produces a thin SOAP. Do NOT flag missing
  sections as MAJOR issues if the transcript itself is brief.
- Calibrate "missing" against what was discussed, not against
  a generic SOAP completeness expectation.
```

### Estimated PR scope
**Trivial** — L5 prompt-only.
