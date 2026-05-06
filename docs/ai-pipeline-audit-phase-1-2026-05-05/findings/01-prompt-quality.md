# Finding 01 — Prompt quality across all model-calling layers

This file groups every prompt-quality issue surfaced by reading
each layer's system + user prompt verbatim. Sub-findings are
ordered by severity (Q0 → Q3 within this file).

---

## 01.1 — L7c Rx prompt has no pediatric framing

**Severity:** Q0 (quality-blocking for pediatric pilot)
**Layer affected:** L7c
**Quality dimension:** safety, specialty-fit

### What's happening today

`apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts:64-132` —
the system prompt mentions pediatric dosing exactly once, in
parentheses on line 87:

> "Dose appears out of the adult (or pediatric if applicable)
>  therapeutic range"

Nowhere does the prompt instruct the model to:
- Compute mg/kg/day for pediatric patients
- Read the patient's weight or DOB from entities/SOAP
- Distinguish neonatal / infant / child / adolescent dosing

The deterministic dose validator
(`packages/ai/src/data/dose-ranges-validator.ts`) DOES handle
peds correctly — but it's not wired in (see Finding 06.5).

### Why this is a quality issue

A pediatric scribe submitting a 15 kg child's visit will get an
Rx draft generated against adult ceilings. Common pediatric
errors the prompt is structurally unable to catch:
- Amoxicillin "500 mg TID" prescribed to an infant (toxic — peds
  is 80-90 mg/kg/day divided)
- Acetaminophen "1000 mg q4h" given to a 6-year-old
- Ibuprofen weight-based vs adult-flat-dose

### Headroom

A specialty-aware Rx draft step would:
- Read patient.dateOfBirth + patient.weightKg from the visit row
- Compute mg/kg if peds
- Surface "this is a pediatric Rx — dose-per-kg shown" in the
  warning panel by default
- Default `action: "unclear"` more aggressively when the SOAP
  doesn't specify a peds-appropriate weight-based dose

### Recommended fix

Two-part change in `07c-rx-drafting.ts`:

1. Pull `dateOfBirth + weightKg` from the visit's patient
   relation in the worker before calling L7c. Pass them as
   structured input to the prompt.
2. Add an explicit pediatric-aware section to the system prompt:

   ```
   PEDIATRIC AWARENESS:
   - If patient age < 18, the dose ceiling is the LOWER of:
     - Adult max
     - peds mg/kg/day × patient weight (kg)
   - Always emit the mg/kg/day calculation in the warning if the
     dose is at-or-near the adult ceiling for a peds patient.
   - For neonatal (<28 days), default action="unclear" and emit
     a critical warning unless the SOAP cites a neonate-specific
     protocol.
   ```

3. Wire `validateRxDose` (the deterministic peds validator
   already shipped) into the L7c output pass — see Finding 06.5.

### Estimated PR scope
**Medium** — 07c prompt expansion + worker.ts patient-context plumbing + dose-validator integration. Single PR.

---

## 01.2 — L4 SOAP-gen is zero-shot; few-shot would significantly raise quality

**Severity:** Q1
**Layer affected:** L4
**Quality dimension:** accuracy, completeness, consistency

### What's happening today

`apps/transcribe-md/src/worker/layers/04-generate-soap.ts:60-111` —
the prompt describes the SOAP structure in prose ("**HPI:**
narrative paragraph incorporating onset, duration, quality, …")
but gives **zero examples** of what a good SOAP note actually
looks like.

The model has to translate the prose description into the
precise formatting + linguistic style on every call.

### Why this is a quality issue

Zero-shot prompts on structured-output tasks have well-documented
failure modes:
- Variability in markdown structure (some calls bold the labels,
  some don't; some include a horizontal rule between sections,
  some don't)
- Inconsistent handling of "[not documented]" — sometimes inline,
  sometimes on its own line, sometimes substituted with "N/A"
- Drift in how "Per patient, …" prefix is applied
- Prose style varies between calls — same transcript on a different
  day produces a meaningfully different note

A doctor signing the same kind of visit twice expects the AI
output to be consistently formatted. Today it isn't.

### Headroom

A 1-shot or 2-shot prompt with carefully chosen exemplars (one
for a complex visit, one for a simple visit) would:
- Cut formatting variability dramatically
- Lock in the "Per patient, …" pattern
- Show the model how negation should appear ("Denies chest
  pain" rather than "No chest pain")
- Anchor on a specific tense / voice (past-tense passive) that
  matches clinical-documentation conventions

The exemplars don't need to be specialty-specific — generic
SOAP shape grounds the formatting; specialty-guidance fills the
clinical content.

### Recommended fix

Add two anchor examples to `04-generate-soap.ts` system prompt
between the structure description and the "Critical rules"
block:

```
EXAMPLE — well-documented complex visit:
[300-400-token canonical SOAP example with the doctor + patient
clearly distinguished, "Per patient, …" prefixes shown, [not
documented] used twice, differential discussed, plan numbered,
the exact markdown formatting the model should produce]

EXAMPLE — sparse visit (typical "blood pressure check"):
[150-token canonical SOAP for a brief visit showing how to
gracefully handle missing sections without padding]
```

Source the examples from anonymized real visits if possible (the
edit-pattern table already captures these — Phase 14.1) — that
grounds the AI on real clinician prose. Otherwise hand-write
them.

### Estimated PR scope
**Small** — single-file prompt expansion in `04-generate-soap.ts`. Examples can be added in a `apps/transcribe-md/src/worker/prompts/soap-exemplars.ts` module for cleanliness.

---

## 01.3 — L5 critique only enumerates 3 red-flag scenarios

**Severity:** Q1
**Layer affected:** L5
**Quality dimension:** safety, completeness

### What's happening today

`apps/transcribe-md/src/worker/layers/05-self-critique.ts:73-76`:

> "Missing red-flag screening for the presenting complaint.
>  Examples: 'chest pain' without SOB/radiation/diaphoresis
>  screen; new-onset headache in an adult without red-flag
>  questions; pediatric fever without hydration/activity check."

Three scenarios listed; the prompt expects the model to
generalize from there.

### Why this is a quality issue

The list is anchored on a small number of well-known scenarios.
The model often-correctly flags missing red-flag questions for
the listed cases, but the audit signal degrades for less-canonical
red-flag scenarios:

- Neck pain + neuro symptoms (cord compression risk)
- Abdominal pain + age >50 (AAA, mesenteric ischemia)
- Postpartum bleeding (PPH timing)
- New mole + ABCDE criteria
- Back pain with bowel/bladder change (cauda equina)
- Pediatric fever in <3 months
- Asymmetric edema (DVT)
- Pregnancy-related red flags by trimester
- Drowsiness in the elderly + new med

Each of these is a documented red-flag-screening miss in
real-world ambulatory care. The L5 prompt treating the listed
three as exhaustive (in spirit) means the model under-flags
critique issues for the long tail.

### Headroom

A red-flag screening matrix that the L5 prompt can reference —
either:
- Specialty + chief-complaint table (best)
- A chief-complaint → red-flag-questions map (good)
- An expanded enumeration of the top 30-40 high-stakes
  scenarios (acceptable starting point)

Either of these would let the L5 critique fire more accurately
on the long tail.

### Recommended fix

Two-step path:

1. **Short term**: expand the L5 prompt to enumerate ~30 chief
   complaints with their canonical red-flag questions. Keep the
   list versioned in `apps/transcribe-md/src/worker/prompts/red-flags.ts`
   so it's easy to maintain. Reference the table in the L5
   prompt rather than inlining it.

2. **Medium term (Phase 7)**: build a structured `red_flag_check`
   pass in L5 that for each chief complaint outputs:
   - A list of questions that should have been asked
   - Whether each was asked (matched in transcript)
   - Whether the answer was documented in SOAP

This gives L5 a per-question audit, not just a free-text "looks
like the screen was incomplete" call.

### Recommended model: Opus 4.7
L5 is the second-opinion layer. The stronger reviewer catches
more — see Finding 04.1.

### Estimated PR scope
**Medium** — single-PR for short-term enumeration; medium PR for the structured per-question audit.

---

## 01.4 — L3 entity prompt is specialty-blind

**Severity:** Q1
**Layer affected:** L3
**Quality dimension:** specialty-fit, completeness

### What's happening today

`apps/transcribe-md/src/worker/layers/03-extract-entities.ts:281-302`
(`buildConversationPrompt`), :304-332 (`buildDictationPrompt`),
:334-362 (`buildTextPrompt`). All three modes use the same
`COMMON_CATEGORIES` list — the entity schema is identical
regardless of specialty.

The schema's categories are:
- chief_complaint, hpi, past_medical_history, medications,
  allergies, family_history, social_history, ros, exam_findings,
  tests_mentioned, assessment_discussed, plan_discussed

There's no extraction of:
- Standardized score totals (PHQ-9, GAD-7, HAM-D, MoCA, MMSE)
- Vital trends (BP recorded over multiple visits, A1c trend)
- Pediatric growth data (weight percentile, height percentile,
  head circumference)
- Cardiac functional status (NYHA class, ejection fraction)
- Mental status exam components (when discussed in psychiatry)
- Pain scoring (0-10 score, functional impact)
- Suicide-risk assessment for psychiatry

Some of these would land naturally in `assessment_discussed` or
`exam_findings` as free text but they wouldn't be queryable as
structured fields downstream.

### Why this is a quality issue

L4 SOAP gen is given specialty guidance but the entities it
consumes are specialty-blind. Result:
- Psychiatry visit with a verbal PHQ-9 score (12) lands as
  `assessment_discussed: [{finding: "PHQ-9 score 12"}]` —
  doesn't surface as a structured score for trending
- Cardiology visit with EF 40% lands as a string in
  `exam_findings` rather than `cardiac.ejection_fraction = 40`
- Pediatric weight percentile (5th percentile) doesn't surface
  as a flag for L4 to comment on

L4 still produces a reasonable SOAP, but the structured
extract is missing dimensions that downstream features
(trending, dashboards, specialist hand-off) would benefit
from.

### Headroom

Specialty-aware entity extraction:
- Psychiatry: extract `phq9_total`, `gad7_total`, `mse` (8
  components), `safety_assessment` (SI/HI/violence)
- Cardiology: extract `ejection_fraction`, `nyha_class`,
  `cardiac_exam` (S1/S2/murmurs/JVD/edema), `vital_trend`
- Pediatrics: extract `growth_percentile` (weight/height/HC),
  `developmental_milestones`, `immunization_status`
- Pain management: extract `pain_score_now`, `functional_impact`
  (sleep/work/ADLs)

Each of these is a small additive structured field, conditional
on specialty.

### Recommended fix

Add specialty-aware optional sections to `ExtractedEntities`
schema as discriminated-union extensions:

```typescript
export const PsychiatryExtension = z.object({
  phq9_total: z.number().min(0).max(27).nullable().optional(),
  gad7_total: z.number().min(0).max(21).nullable().optional(),
  mse: z.object({
    appearance: z.string().optional(),
    behavior: z.string().optional(),
    speech: z.string().optional(),
    mood: z.string().optional(),
    affect: z.string().optional(),
    thought_process: z.string().optional(),
    thought_content: z.string().optional(),
    cognition: z.string().optional(),
    insight: z.string().optional(),
    judgment: z.string().optional(),
  }).partial().optional(),
  safety: z.object({
    suicidal_ideation: z.enum(['denies', 'passive', 'active', 'with_plan']).optional(),
    homicidal_ideation: z.enum(['denies', 'passive', 'active', 'with_plan']).optional(),
    means_or_plan_documented: z.boolean().optional(),
  }).partial().optional(),
});
```

L3 prompt switches on specialty; L4 prompt + critique can
consume the structured fields when present.

### Estimated PR scope
**Large** — schema additions + per-specialty prompt blocks + L4 / L5 / L7 consumption updates. Probably split: PR per specialty so the change set per PR stays reviewable.

---

## 01.5 — L4 doesn't tell the model how to handle entity-vs-transcript disagreement

**Severity:** Q2
**Layer affected:** L4
**Quality dimension:** consistency, accuracy

### What's happening today

`04-generate-soap.ts:113-121` — the user message is:

```
Specialty: <specialty>

Extracted entities (structured, with evidence):
<JSON of entities>

Role-labeled transcript:
<wrapped transcript>
```

Both are presented as inputs but the prompt doesn't say which
to trust if they disagree. In practice they sometimes do:
- L3 may have missed an entity that's in the transcript
- L3 may have misclassified (e.g., a med listed as past_medical_history)
- The transcript may mention something L3's schema can't capture
  (a comment about insurance, a procedure that was attempted but
  abandoned)

### Why this is a quality issue

When entities and transcript disagree, the model picks
inconsistently across calls. Sometimes it uses entities (which
have evidence quotes — easier to ground), sometimes it
re-extracts from the transcript (which may catch what L3 missed
but with no evidence quote in entities).

### Headroom

Anchoring rule: "Treat extracted entities as the structured
backbone. If the transcript reveals additional content not in
entities, INCLUDE it in the SOAP but mark it `[supplementary]`
in your reasoning so the doctor knows it wasn't grounded in the
entity layer." Then L5 can audit the marked content.

### Recommended fix

Add 4-line block to L4 system prompt:

```
ENTITY vs TRANSCRIPT precedence:
- Extracted entities are the verified structured input. Prefer
  them when they conflict with the transcript.
- When the transcript contains material content NOT in entities
  (a missed test result, an extra medication mention), include
  it in the SOAP but ALSO surface it via the L5 audit by
  prefixing the line with "[supplementary]" — the auditor will
  decide whether to retain or drop.
```

### Estimated PR scope
**Small** — prompt-only change.

---

## 01.6 — L7c Rx prompt doesn't specify route/form for IV-only or PR-only drugs

**Severity:** Q2
**Layer affected:** L7c
**Quality dimension:** safety, accuracy

### What's happening today

`07c-rx-drafting.ts:69-75` — `form` and `route` (implicit in
sig) are both nullable. The prompt doesn't tell the model what
to do when the doctor says "give Toradol 30" (likely IM, not
PO) or "patient needs Compazine PR 25" (rectal, not oral).

### Why this is a quality issue

Some drugs have an oral default that's wrong for emergency or
peri-procedural use. A doctor saying "Toradol 30" almost
always means IM 30 mg in an outpatient/urgent-care context,
but the AI's default-to-PO assumption could produce a sig like
"Take 1 tablet by mouth as needed" — clinically wrong.

### Headroom

A short list of common drugs with non-PO defaults could be
added to the prompt or to the dose-ranges table:
- Toradol/ketorolac (IM 15-30 mg q6h)
- Compazine/prochlorperazine (PR 25 mg available; IV/IM in
  emergency)
- Promethazine (multiple routes)
- Fentanyl (IV/IM/IN/transdermal)
- Lorazepam (IV/IM/PO/SL)

### Recommended fix

Two parts:

1. Extend `dose-ranges.ts` entries with a `routes` field listing
   common-use routes per drug:

   ```typescript
   {
     drug: 'ketorolac',
     aliases: ['toradol'],
     adultMaxMgPerDay: 120,
     routes: ['IM', 'IV', 'PO'],
     defaultRoute: 'IM',
     ...
   }
   ```

2. L7c prompt block:

   ```
   ROUTE DETERMINATION:
   - If the SOAP names a drug that's commonly given by a
     non-oral route in this clinical context (e.g., Toradol IM
     in urgent care, Compazine PR for nausea), include the
     route explicitly. Do NOT default to oral when the
     transcript / SOAP doesn't specify and the drug's typical
     use isn't oral.
   ```

### Estimated PR scope
**Small** — dose-ranges schema + L7c prompt update.

---

## 01.7 — L7e patient summary "When to call us" has only one example

**Severity:** Q2
**Layer affected:** L7e
**Quality dimension:** safety, completeness

### What's happening today

`07e-patient-summary.ts:72-74`:

> "'When to call us' should list concrete red-flag symptoms
>  relevant to the visit (e.g. for high blood pressure:
>  chest pain, severe headache, vision changes)."

Only the high-blood-pressure example is given. The model
generalizes from there, sometimes well, sometimes not.

### Why this is a quality issue

Patient-facing red-flag lists are clinically important and
specialty-specific. A diabetes follow-up should warn about DKA
symptoms; a pediatric fever visit should warn about lethargy/
dehydration; a chest-pain rule-out should warn about return
symptoms.

A single in-prompt example anchors the model on hypertension
even when the visit is unrelated.

### Headroom

A specialty + chief-complaint → red-flag-symptoms map (same as
in Finding 01.3 for L5 critique) lets L7e produce reliably
appropriate "When to call us" content.

### Recommended fix

Reuse the red-flag table from Finding 01.3. L7e prompt
references it conditionally on specialty + chief complaint:

```
"When to call us" tailoring rules:
- Open <RED_FLAG_TABLE> for the chief complaint discussed.
- List the 3-5 most patient-actionable red-flag symptoms.
- If the visit is preventive/well-child/chronic stable with
  no specific risk profile, list the generic emergency
  triggers (severe shortness of breath, chest pain not
  resolving, fainting, sudden severe headache, signs of
  stroke).
```

### Estimated PR scope
**Small** — depends on red-flag table from Finding 01.3.

---

## 01.8 — L2 speaker-role classification is sample-size-bound and English-anchored

**Severity:** Q2
**Layer affected:** L2
**Quality dimension:** accuracy, robustness

### What's happening today

`02-speaker-roles.ts:24` — `SAMPLE_SIZE = 5`. Only the first 5
utterances per speaker are sent to the model.

The system prompt (lines 112-134) describes English clinical
patterns ("Doctors ask diagnostic questions, use medical
terminology"). No mention of:
- Multilingual visits (English ↔ Spanish, English ↔ Mandarin)
- Patients who are themselves clinical (nurse-as-patient,
  doctor-as-patient — they use medical terminology)
- Long monologue visits where utterance turns are unbalanced
  (one speaker 50 utterances, other 3 utterances)

### Why this is a quality issue

5 utterances may not be enough signal in:
- Long visits with subtle role distinctions
- Visits where the doctor and patient have similar speaking
  styles (e.g., doctor consults with a doctor-patient)
- Visits with multiple in-room family members where the prompt
  has only 5 samples of "Speaker 3" who's actually a teenage
  daughter translating for grandma

### Headroom

Two improvements:
1. Increase SAMPLE_SIZE to ~10 OR sample utterances strategically
   (first 3 + middle 3 + last 3 — covers visit arc, not just
   intro)
2. Augment the prompt with multilingual cues + clinical-
   profession-as-patient handling

### Recommended fix

```typescript
const SAMPLE_SIZE = 10;  // bump from 5

function groupSamplesBySpeaker(
  utterances: DeepgramUtterance[]
): Map<number, string[]> {
  // Sample evenly: first 4, middle 3, last 3
  ...
}
```

Prompt additions:
```
- Patients who are themselves clinical professionals (nurses,
  doctors as patients, EMTs) may use medical terminology
  fluently. Distinguish role by who is GIVING vs RECEIVING the
  clinical assessment, not vocabulary alone.
- Multilingual code-switching (Spanish/Mandarin) is common.
  The doctor typically speaks more English in the diagnostic
  questions; the patient typically speaks more native language
  in symptom description. Confidence may be lower; use
  "unknown" when in doubt.
```

### Estimated PR scope
**Small** — prompt + SAMPLE_SIZE bump in 02-speaker-roles.ts.

---

## 01.9 — L1b dictation transcribe doesn't pass MEDICATION_KEYTERMS

**Severity:** Q2
**Layer affected:** L1b
**Quality dimension:** accuracy

### What's happening today

`01-transcribe.ts:68` — `keyterms: MEDICATION_KEYTERMS` is
passed.

`01b-transcribe-dictation.ts:57-60` — only `diarize: false,
utterances: false` is passed. `keyterms` is omitted.

Comment in the file (lines 53-56) explains diarize/utterances
are off but doesn't say why keyterms are also off.

### Why this is a quality issue

Voice dictation is the path where the doctor speaks medication
names directly ("Increase metoprolol to 50 BID, add atorvastatin
20"). This is exactly the case `MEDICATION_KEYTERMS` was built
for — a curated lexicon to bias Deepgram toward correct drug
spellings.

Conversation mode benefits less because doctors usually say
"medication" once and move on; the patient names are fewer.

### Headroom

Adding `MEDICATION_KEYTERMS` to L1b should reduce drug-name
transcription errors in dictation specifically. Net positive
since dictation is doctor-driven and medication-dense.

### Recommended fix

```typescript
// 01b-transcribe-dictation.ts
import { MEDICATION_KEYTERMS } from '@/lib/deepgram-vocabulary';

// in attempt():
return deepgramBatchTranscribe({
  ...
  options: { diarize: false, utterances: false },
  keyterms: MEDICATION_KEYTERMS,  // <-- add
});
```

### Estimated PR scope
**Trivial** — 2-line change.

---

## 01.10 — L4 + L5 use Sonnet 4.6; cross-prompt agreement on "good SOAP" is implicit

**Severity:** Q2
**Layer affected:** L4 + L5 (cross-cutting)
**Quality dimension:** consistency

### What's happening today

L4 (`04-generate-soap.ts`) and L5 (`05-self-critique.ts`)
each describe what a "good SOAP" looks like in their own
prose. They overlap but aren't aligned:
- L4 says "Differentials if the doctor discussed them."
- L5 says "Plan does not address the Assessment." as a major
  issue — but doesn't link back to L4's "Differentials" rule.
- L4 says "[not documented]" for missing fields; L5's CRITICAL
  list doesn't explicitly accept "[not documented]" as a valid
  signal of "info wasn't there".

### Why this is a quality issue

When L5 reviews L4's output, the two prompts can disagree about
what counts as acceptable output. L5 may flag a "[not documented]"
section as a major-issue omission; L4's prompt told the model
that's fine.

The result is critique noise — issues flagged that L4's prompt
explicitly endorsed.

### Headroom

A shared "SOAP quality contract" referenced by both prompts:

```typescript
// apps/transcribe-md/src/worker/prompts/soap-contract.ts
export const SOAP_QUALITY_CONTRACT = [
  '"[not documented]" is a valid value for any section where the',
  'transcript is silent. The SOAP must NEVER invent content to',
  'fill a section.',
  '"Per patient, …" is the canonical prefix for self-reported',
  'symptoms / history.',
  ...
].join('\n');
```

Both L4 and L5 import and inline this. L5's "MAJOR — info
omitted" rule is then constrained: the omission has to be
information present in the transcript that didn't make it into
the SOAP — not a section the model correctly marked
`[not documented]`.

### Recommended fix

Extract `SOAP_QUALITY_CONTRACT` to a shared module. L4 + L5 +
L6 all reference it. PR scope: 1 file added, 3 prompts updated.

### Estimated PR scope
**Small**.

---

## 01.11 — L7d referrals temperature is 0.3 — slightly warm for billing-adjacent output

**Severity:** Q3
**Layer affected:** L7d
**Quality dimension:** consistency

### What's happening today

`07d-referrals.ts:85` — `temperature: 0.3`.

### Why this is a quality issue

Referral letters are quasi-billing artifacts (some payers
require structured referrals before authorizing specialty
visits). Determinism matters: the same SOAP should produce
the same referral on consecutive runs.

0.3 is fine for prose but adds enough variation that re-runs
on the same SOAP can produce subtly different referrals.

### Headroom

Lowering to 0.1 (matching L7a/L7b/L7c) makes referrals
deterministic without losing the ability to phrase the
"reason" sentence naturally.

### Recommended fix

Single-line change: `temperature: 0.1` in `07d-referrals.ts:85`.

### Estimated PR scope
**Trivial**.
