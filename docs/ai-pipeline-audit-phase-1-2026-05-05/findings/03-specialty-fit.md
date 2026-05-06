# Finding 03 — Specialty fit

How specialty-specific the pipeline is by layer:

| Layer | Specialty awareness | Notes |
|---|---|---|
| L1 / L1b | None | Deepgram nova-3-medical handles most specialties; no per-specialty keyterm tuning |
| L2 | None | Generic role classification |
| L3 | None | Generic entity schema regardless of specialty |
| L4 | Yes | `specialtyGuidance(slug)` appended to system prompt |
| L5 | Specialty in user message only | No specialty-specific critique rules |
| L6 | None | Polish doesn't see specialty |
| L7a | Specialty in user message only | Same allowlist for all specialties |
| L7b | Specialty in user message only | Same E&M / CPT allowlist for all specialties |
| L7c | None | Specialty-blind Rx |
| L7d | None | Specialty-blind referral letters |
| L7e | Specialty in user message only | Generic patient-summary structure |

The pattern: only L4 gets dedicated specialty-specific
guidance text. Other layers may receive `specialty: <slug>` in
the user message but their system prompts don't branch.

---

## 03.1 — OB-GYN exists in `SPECIALTY_GUIDANCE` but not in the catalog

**Severity:** Q1 (silent feature regression)
**Layer affected:** L4 + specialty plumbing
**Quality dimension:** specialty-fit

### What's happening today

`apps/transcribe-md/src/worker/prompts/specialty-guidance.ts:64-74`
defines guidance for both `'ob-gyn'` and `'obstetrics-gynecology'`.

`packages/shared/src/specialties.ts:22-32` does NOT list OB-GYN
in the catalog.

`packages/shared/src/specialties.ts:69` has the LEGACY map
sending OB-GYN values to `'unspecified'`:

```typescript
'OB-Gyn': 'unspecified',
'Obstetrics & Gynecology': 'unspecified',
```

A doctor cannot pick OB-GYN at the visit-create form. Existing
DB rows that were OB-GYN got mapped to `unspecified`, which
fails to lookup in `SPECIALTY_GUIDANCE` (no `'unspecified'`
key). The carefully-written OB-GYN guidance (LMP / G_P /
prenatal vitals) **never fires.**

### Why this is a quality issue

1. OB-GYN scribes can't pick their specialty at signup. They're
   forced to `unspecified` and lose all guidance.
2. The dead OB-GYN guidance suggests a partial deletion or
   mid-flight feature change that wasn't completed.

### Headroom

Restoring OB-GYN to the catalog brings back specialty-aligned
SOAP for an entire pilot specialty. Gains are large for that
cohort.

### Recommended fix

Add OB-GYN to `SPECIALTIES` in `packages/shared/src/specialties.ts`:

```typescript
{ id: 'ob-gyn', label: 'Obstetrics & Gynecology', templateId: 'ob-gyn' },
```

Update the legacy map to leave OB-GYN as itself rather than
mapping to `unspecified`. Drop the duplicate
`'obstetrics-gynecology'` key in `SPECIALTY_GUIDANCE`.

Add a Prisma migration if any production rows have already
been mapped through the legacy fallback.

### Estimated PR scope
**Small** — single shared catalog change + guidance dedup. Possibly a small data migration.

---

## 03.2 — Psychiatry pilot is missing key structured outputs

**Severity:** Q0 (critical for psychiatry pilot)
**Layer affected:** L3 → L4 → specialty-guidance
**Quality dimension:** specialty-fit

### What's happening today

Psychiatry guidance in `specialty-guidance.ts:22-29`:

> "Include a Mental Status Exam section (appearance, behavior,
>  speech, mood, affect, thought process, thought content,
>  cognition, insight, judgment). Document risk assessment
>  (suicidal/homicidal ideation) explicitly even if negative —
>  absence of risk is a documented clinical finding. Use
>  neutral, non-stigmatizing language. Do NOT infer psychiatric
>  diagnoses that weren't explicitly discussed."

Good as far as it goes. But the L3 entity schema doesn't have
slots for:
- **PHQ-9 score** (verbal "she scored 12" doesn't structure)
- **GAD-7 score**
- **HAM-D score**
- **MoCA / MMSE cognitive scores**
- **Substance use screening** (CAGE / AUDIT-C)
- **Suicide risk components** (Columbia Protocol responses)
- **Mental Status Exam as structured fields**

When a psychiatrist verbally completes a PHQ-9 with a patient
("Q1 — little interest, score 2; Q2 — feeling down, score 3
…"), L3 may capture each Q&A separately, but there's no place
in the schema for "PHQ-9 total: 12, severity: moderate" as a
single computed field.

L4 then puts the score in free-text Assessment — not queryable
for trending, dashboards, or hand-off.

### Why this is a quality issue

Psychiatry visits revolve around standardized assessments. A
SOAP that lists every question asked but doesn't structure the
total is harder to use clinically. Trending PHQ-9 across visits
is the primary outcome measure for depression management — and
today the data isn't structured.

### Headroom

A psychiatry-aware extension to L3 schema:

```typescript
psychiatry: z.object({
  phq9: z.object({
    total: z.number().min(0).max(27),
    severity: z.enum(['minimal', 'mild', 'moderate', 'moderately_severe', 'severe']),
    item9_si: z.boolean(),  // Critical safety flag — Q9 is suicidal ideation
    evidence_quote: z.string(),
  }).nullable().optional(),
  gad7: z.object({
    total: z.number().min(0).max(21),
    severity: z.enum(['minimal', 'mild', 'moderate', 'severe']),
    evidence_quote: z.string(),
  }).nullable().optional(),
  mse: z.object({
    appearance: z.string().nullable().optional(),
    behavior: z.string().nullable().optional(),
    speech: z.string().nullable().optional(),
    mood: z.string().nullable().optional(),
    affect: z.string().nullable().optional(),
    thought_process: z.string().nullable().optional(),
    thought_content: z.string().nullable().optional(),
    cognition: z.string().nullable().optional(),
    insight: z.string().nullable().optional(),
    judgment: z.string().nullable().optional(),
  }).nullable().optional(),
  safety: z.object({
    suicidal_ideation: z.enum(['denies', 'passive', 'active', 'with_plan']).nullable().optional(),
    homicidal_ideation: z.enum(['denies', 'passive', 'active', 'with_plan']).nullable().optional(),
    means_or_plan_documented: z.boolean().nullable().optional(),
    safety_plan_in_place: z.boolean().nullable().optional(),
  }).nullable().optional(),
}).nullable().optional()
```

L4's psychiatry guidance can then reference the structured
fields: "If `psychiatry.phq9.total` is present, render in
Assessment as 'PHQ-9 = N (severity)'."

### Recommended fix

Two-part:

1. **Schema** — add the psychiatry extension above.
2. **L3 prompt** — when `mode === 'conversation'` AND
   `specialty === 'psychiatry'`, include a psychiatry-specific
   block in the system prompt that:
   - Tells the model to compute PHQ-9/GAD-7 totals from the
     verbalized item scores
   - Defines the severity bands (PHQ-9: 0-4 minimal, 5-9 mild,
     10-14 moderate, 15-19 mod-severe, 20+ severe)
   - Explicitly extracts `item9_si` for PHQ-9 — the suicide
     question
   - Documents MSE in structured form when discussed
3. **Specialty Guidance** — reference these structured fields.

### Recommended model
Use Opus 4.7 for psychiatry L3 + L4 (Finding 04.x). The
clinical risk is high (suicide-risk assessment, med
management), the prompts are denser (specialty extension),
and the second-opinion value is high.

### Estimated PR scope
**Large** — schema + L3 specialty branching + L4 psychiatry-aware rendering + L5 / L7 awareness of structured fields.

---

## 03.3 — Cardiology pilot is missing structured cardiac outputs

**Severity:** Q1
**Layer affected:** L3 → L4 → L5
**Quality dimension:** specialty-fit

### What's happening today

Cardiology guidance in `specialty-guidance.ts:14-20`:

> "Document NYHA class if heart failure is discussed. Note
>  cardiovascular risk factors explicitly. Document any cardiac
>  exam findings (S1/S2, murmurs, JVD, edema) precisely. If
>  acute coronary syndrome is in the differential, capture
>  TIMI/HEART score components that were discussed."

References the right concepts but no L3 schema fields for:
- `nyha_class` (I-IV)
- `ejection_fraction_pct`
- `cardiac_exam` structured (S1/S2/murmurs/JVD/edema/PMI)
- `heart_score_components` (5 axes: history, EKG, age, risk
  factors, troponin)
- `timi_components`
- `vital_trend` (BP/HR over visits)

The CPT allowlist also has gaps for cardiology:
- 93306 (echo, complete) — **not in allowlist**
- 93307 (echo, limited) — **not in allowlist**
- 93000 (ECG with interpretation) — present ✓
- 93015 (stress test) — **not in allowlist**
- 93224-93227 (Holter monitor) — **not in allowlist**

A cardiologist's L7b output for an echo-with-stress-test visit
will hit allowlist rejections.

### Why this is a quality issue

Cardiology is a structured specialty. Echo readings, stress
test results, NYHA class progression, EF — all are first-class
clinical entities. Without structure they're free-text in the
SOAP.

The CPT gaps mean billable codes get dropped to "rejected by
coding-coach" — the doctor sees fewer suggested codes and has
to look up the right one manually.

### Recommended fix

1. Add cardiology fields to L3 schema (NYHA, EF, structured
   cardiac exam, vital trend).
2. Expand CPT allowlist with cardiology codes (93306, 93307,
   93015, 93224, 93225, 93226, 93227 at minimum).
3. Expand ICD-10 allowlist with cardiology codes (heart-failure
   variants I50.21-I50.43, cardiomyopathy I42.0-I42.9, LBBB/
   RBBB, etc.).
4. L4 cardiology rendering — show NYHA + EF as a structured
   header line in Assessment if extracted.

### Estimated PR scope
**Medium** — schema + allowlist expansions + L4 rendering.

---

## 03.4 — Pediatrics pilot is missing growth + developmental structure

**Severity:** Q1
**Layer affected:** L3 → L4 → L7c (Rx)
**Quality dimension:** specialty-fit, safety

### What's happening today

Pediatric guidance in `specialty-guidance.ts:31-36`:

> "Document growth parameters (weight, height, head circumference,
>  percentiles) if given. Document developmental milestones or
>  concerns. Capture caregiver concerns alongside patient
>  statements — distinguish who said what. Note immunization
>  status if discussed. Use age-appropriate language in patient
>  education."

Good, but L3 schema doesn't have:
- `growth: { weight_pct, height_pct, hc_pct, weight_z, …}`
- `developmental_milestones: [{age, milestone, status}]`
- `immunization_status: [{vaccine, due, given_today}]`
- `caregiver_relation` (mother/father/grandparent/foster)

Plus the Rx safety chain (L7c → dose validator) needs the
patient's weight and DOB to compute peds dosing — see Finding
01.1. The patient row has both fields, but they don't flow
into L7c's prompt today.

### Why this is a quality issue

Pediatric visits are weight-and-percentile-driven. Without
structured growth fields, every visit's data has to be re-parsed
from the SOAP free text for trending, charts, growth curves.

The Rx safety risk is the bigger issue — see Finding 01.1.

### Recommended fix

1. Add pediatric extension to L3 schema (growth + milestones +
   immunization).
2. Wire patient weight + DOB into L7c (see Finding 01.1).
3. CPT allowlist expansion: developmental screening (96110),
   fluoride application (99188), audiometry (92551), vision
   screening (99173 already present ✓).
4. ICD-10 allowlist expansion: developmental delay (F88, F89),
   speech delay (F80.x), failure to thrive (R62.51), pediatric
   immunization counters (Z23 present but no specific
   "immunization not up to date" Z28.x).

### Estimated PR scope
**Medium-Large** — schema + dose-validator wiring + allowlist expansions + L4 pediatric rendering.

---

## 03.5 — Pain-management visits need structured pain + functional impact

**Severity:** Q2
**Layer affected:** L3 → L4
**Quality dimension:** specialty-fit

### What's happening today

Pain-management guidance in `specialty-guidance.ts:84-92`:

> "Document pain location, character (sharp / dull / burning /
>  radiating), 0-10 severity, duration, exacerbating + alleviating
>  factors. Note functional impact (sleep, work, ADLs). Capture
>  medication history including doses, frequency, prior trials
>  and outcomes. Document non-pharmacologic modalities tried
>  (PT, injections, behavioral). Note any controlled-substance
>  prescribing decisions and the documented rationale. Be
>  cautious about diagnostic specificity unless the doctor stated
>  a clear diagnosis."

Good guidance. L3 schema has `hpi.severity` (string) but not
specifically a 0-10 score with units. Pain is the canonical
"give me a number" specialty.

The `assessment_discussed` doesn't structure functional impact
either.

### Why this is a quality issue

Trending pain across visits requires the score as a number,
not free text. Pain-management doctors compare "8/10 last
visit, 5/10 today" — that's the outcome measure. Today the
trend is locked in prose.

### Recommended fix

L3 pain-management extension:

```typescript
pain: z.object({
  current_score_0_10: z.number().min(0).max(10).nullable().optional(),
  worst_score_last_week: z.number().min(0).max(10).nullable().optional(),
  location: z.string().nullable().optional(),
  character: z.array(z.enum([
    'sharp','dull','burning','radiating','aching','throbbing','stabbing','tingling','crampy'
  ])).default([]),
  functional_impact: z.object({
    sleep: z.enum(['none','mild','moderate','severe']).nullable().optional(),
    work: z.enum(['none','mild','moderate','severe']).nullable().optional(),
    adls: z.enum(['none','mild','moderate','severe']).nullable().optional(),
  }).partial().optional(),
  controlled_substance_decision: z.object({
    prescribed: z.boolean(),
    rationale: z.string(),
    pdmp_checked: z.boolean(),
  }).nullable().optional(),
}).nullable().optional()
```

### Estimated PR scope
**Medium**.

---

## 03.6 — Urgent-care pilot is well-served on prompts but lacks return-precaution structure

**Severity:** Q3
**Layer affected:** L3 / L7e
**Quality dimension:** specialty-fit

### What's happening today

Urgent-care guidance in `specialty-guidance.ts:76-82`:

> "Document chief complaint precisely with duration and severity.
>  Capture vital signs and red-flag symptoms explicitly … Note
>  disposition decision (discharge home, referral to ED,
>  follow-up timing) and the rationale. Capture return
>  precautions if discussed."

Reasonable. Return-precautions are the urgent-care canonical
patient-facing artifact — and L7e (patient summary) "When to
call us" already does this generically.

Could be tighter: a `return_precautions` array with
`[symptom, action]` would give urgent-care an exportable list
that doesn't require parsing the prose.

### Recommended fix

L3 schema field:
```typescript
return_precautions: z.array(z.object({
  trigger_symptom: z.string(),
  patient_action: z.enum(['call_us', 'go_to_ed', 'urgent_callback']),
  evidence_quote: z.string(),
})).default([]);
```

L7e then uses these directly rather than re-deriving from the
free text.

### Estimated PR scope
**Small** — schema field + L7e prompt update.

---

## 03.7 — ICD-10 + CPT allowlists have a family-medicine bias

**Severity:** Q1
**Layer affected:** L7a / L7b
**Quality dimension:** specialty-fit, billing-completeness

### What's happening today

`icd10-allowlist.ts:28-169` — ~120 codes. Distribution by
specialty (manual count):
- Family/internal medicine: ~37 codes (31%)
- Pediatrics: ~11 codes (9%)
- OB/GYN: ~9 codes (7.5%)
- Orthopedics: ~12 codes (10%)
- Cardiology: ~7 codes (6%)
- Pulmonary: ~8 codes (7%)
- Psychiatry: ~16 codes (13%)
- Pain/neuro: ~6 codes (5%)
- Skin/derm: ~5 codes (4%)
- Other: ~9 codes (7.5%)

For a psychiatry pilot, 16 ICD codes is thin:
- F32.9 / F33.9 (depression) ✓
- F41.x (anxiety) ✓
- F43.10 PTSD ✓
- F90.x ADHD ✓
- F31.9 bipolar ✓
- F50.81 binge eating ✓
- F84.0 autism ✓
- F51.01 / G47.00 insomnia ✓
- **Missing**: F40.x (specific phobias), F42 (OCD), F31.0-F31.6
  (bipolar specific episodes), F60.x (personality disorders),
  F12.x / F19.x (substance use), F50.0/F50.2 (anorexia/
  bulimia), F95.x (Tourette), R45.851 (suicidal ideation
  observation code), Z63.x (family / partner stressors)

For cardiology, 7 codes is very thin (see Finding 03.3).

For pediatrics, 11 codes misses common pediatric diagnoses
(see Finding 03.4).

### Why this is a quality issue

The allowlist filter at L7a is fail-closed: codes not in the
list are dropped + audited. A psychiatrist's L7a output for a
visit involving OCD (F42) gets the code dropped. The doctor
sees fewer ICD suggestions and has to manually look up F42
post-hoc.

### Headroom

Doubling the allowlist to ~250 codes with specialty parity
would resolve most of the rejection traffic. Phase 7 path
(per the file's own documentation) is to swap in the full CMS
canonical list — but that's a Phase 7 task. For pilot-time
quality, hand-curate ~100-150 more codes targeting psychiatry,
cardiology, pediatrics gaps.

### Same gap on CPT side

The CPT allowlist at `cpt-allowlist.ts:27-145` has good E&M
coverage (every level for new/established/inpatient/ER/peds/
preventive) and basic procedures, but misses:

- **Cardiology**: 93306, 93307, 93015, 93016, 93017, 93018,
  93224, 93225, 93226, 93227 (echo + stress + Holter)
- **Pediatrics**: 96110 (developmental screening), 99188
  (fluoride), 92551 (audiometry)
- **OB**: 59025 (NST), 76801, 76802 (OB ultrasound)
- **Pain**: 64483 (ESI lumbar), 27096 (SI joint inj), 64493
  (lumbar facet medial branch)
- **Psychiatry**: most major psych codes already present ✓

### Recommended fix

A single PR adding ~150 codes across the gaps. The file's
existing in-source comments make ownership clear. Each new
code with a 1-line description. ICD-10-CM 2026 codes (latest)
should be used.

Phase 7 follow-up (Q3): swap to the full CMS file.

### Estimated PR scope
**Medium** — research-heavy but mechanical edit. Single PR.

---

## 03.8 — Specialty selection is explicit (good) but no auto-confirmation

**Severity:** Q3
**Layer affected:** orchestration
**Quality dimension:** robustness

### What's happening today

Specialty is explicit per visit (set in user profile,
overridable per visit). `findSpecialty` handles legacy values
gracefully.

There's no detection step that says "you set specialty=
cardiology but the transcript looks pediatric (lots of
'mom said', growth-percentile mentions, developmental
language) — confirm before signing." Such a sanity check
would catch profile-setting mistakes (a primary-care doc
who ALSO sees psychiatry patients but has profile=primary-
care).

### Why this is a quality issue

Profile-vs-actual-content mismatches are rare but are a soft
guardrail miss. Low-severity finding.

### Recommended fix (optional)

Phase 7+ — a specialty-detection check in L3 that flags
mismatches, but doesn't block the pipeline.

### Estimated PR scope
**Small** but defer to Phase 7+.
