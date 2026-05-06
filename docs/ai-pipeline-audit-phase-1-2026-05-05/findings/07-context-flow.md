# Finding 07 — Context flow across layers

How information propagates from L1 (raw transcript) through to
L7 (coding/Rx/summary). This audits whether downstream layers
have the context they need and where richer propagation would
help.

---

## Context-flow map

| From → To | What flows | What's lost |
|---|---|---|
| L1 → L2 | utterances (with speaker IDs, start times) | confidence per utterance not used |
| L1 → L3 | transcriptText (raw) | speaker boundaries, utterance timing |
| L2 → L3 | speakerMap | confidence values not propagated |
| L3 → L4 | entities + contextText (role-labeled transcript) | utterance-level confidence (Deepgram per-utterance scores) |
| L4 → L5 | soapDraft + entities + roleLabeledTranscript | NONE — L5 sees full context ✓ |
| L5 → L6 | soapDraft + critique | original transcript + entities NOT passed |
| L4/L6 → L7a-e | soapFinal + entitiesJson | original transcript NOT passed; speaker attribution NOT preserved |

Most context loss is between L5 → L6 and between L4/L6 → L7.

---

## 07.1 — L6 polish doesn't see the transcript or entities — only the draft + critique

**Severity:** Q1
**Layer affected:** L6
**Quality dimension:** accuracy

### What's happening today

`06-polish.ts:35-87`:

```typescript
export async function runLayer6Polish(input: Layer6Input): Promise<Layer6Output> {
  const { fixable, unfixable } = classifyCritique(input.critique);
  ...
  const user = [
    'Draft:',
    input.soapDraft,
    '',
    'Issues to apply (apply in order):',
    fixable.map(...).join('\n'),
  ].join('\n');
  ...
}
```

`Layer6Input` is `{ visitId, practiceId, userId, soapDraft, critique }`.
No transcript. No entities. No specialty.

The L6 prompt says (line 54-56):

> "Do NOT introduce new clinical facts. If a fix requires
>  information that is not in the draft, leave the flagged area
>  as-is and keep moving."

This rule is correct in spirit but means: if L5 critique says
"Assessment doesn't address the chronic kidney disease
documented in PMH" and L6 doesn't see the entities, L6 has no
way to verify CKD is actually in PMH (without re-reading the
entire draft section). It treats the critique as the only
ground truth.

### Why this is a quality issue

L5's critique is summary text — it can mis-quote, mis-locate, or
hallucinate issues. Without the entities + transcript, L6 has
no way to verify L5's claims and either:
- Applies a "fix" that introduces incorrect content (the
  critique says "PMH includes CKD" but actually it didn't)
- Refuses to apply a valid fix (when in doubt, leaves alone)

Both modes degrade quality.

### Headroom

If L6 sees `entities + roleLabeledTranscript` (the same context
L5 saw), it can verify each suggested fix against the source
data:
- "L5 said add CKD to Assessment, but entities.past_medical_history
  doesn't have CKD → don't add."
- "L5 said the dose in Plan is wrong; entities.medications has
  dose='10 mg' matching the SOAP — L5 was wrong; don't change."

L6 becomes a fact-checked editor rather than a critique-text-
following editor.

### Recommended fix

Extend `Layer6Input`:

```typescript
export interface Layer6Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  specialty: string;            // NEW
  soapDraft: string;
  critique: CritiqueReport;
  entities: ExtractedEntities;  // NEW
  roleLabeledTranscript: string;// NEW
}
```

Worker passes them. L6 prompt expansion:

```
GROUND TRUTH:
- Verify every "suggested_fix" against the entities + transcript
  before applying. If the fix asks you to add or change content
  that is NOT supported by entities + transcript, SKIP that fix
  and add the issue to a `skipped_fixes` array in your reasoning
  (don't fabricate to satisfy the auditor).
- Apply only fixes that the source data supports.
```

### Estimated PR scope
**Small** — Layer6Input expansion + worker.ts plumbing + prompt update.

---

## 07.2 — L7 layers don't see the original transcript

**Severity:** Q2
**Layer affected:** L7a / L7b / L7c / L7d / L7e
**Quality dimension:** accuracy

### What's happening today

L7 layers receive `soapFinal` + `entitiesJson`. They never see
the original transcript.

For most L7 tasks, this is correct — the SOAP IS the
authoritative source for codes / Rx / referrals (the SOAP is
what the doctor will sign). But there are edge cases:

- **L7a coding**: The SOAP may have rounded a precise quote
  ("BP 148/92 today, has been 130s/80s at home") into prose
  ("blood pressure not at goal"). L7a sees the prose; the
  precise reading is in entities (good) but if entities also
  rounded it, the original quote is lost.

- **L7c Rx warnings**: Allergy "patient says he had a rash with
  ampicillin once" gets summarized in entities as "ampicillin"
  but the original detail "rash" is informative for severity
  classification. L7c sees only the summary.

### Why this is a (lower-severity) quality issue

The SOAP + entities are usually sufficient. The transcript adds
nuance for edge cases that the model could exploit if available.

### Recommended fix

Optional pass: include `roleLabeledTranscript` as a third input
to L7c specifically (the safety-critical layer). Keep it
optional — L7a/b/d/e probably don't need it.

For L7c the prompt expansion would be:

```
TRANSCRIPT REFERENCE:
- The role-labeled transcript is the original recorded
  conversation. Use it to disambiguate when entities or SOAP
  are summarized:
  - For allergies: read the original allergy quote — was it
    a rash? hives? anaphylaxis? — to set severity correctly.
  - For dose changes: read the original "increase to..." quote
    to set the target dose if SOAP rounded it.
- Do NOT use the transcript to invent prescriptions not in
  SOAP. The plan is the SOAP's plan section.
```

### Estimated PR scope
**Small** — L7c only.

---

## 07.3 — Deepgram per-utterance confidence is captured but not propagated

**Severity:** Q1
**Layer affected:** L1 → all downstream
**Quality dimension:** accuracy, robustness

### What's happening today

Deepgram's batch API returns per-utterance `confidence`
values. `01-transcribe.ts` persists `transcriptRaw` (the full
Deepgram payload) but only the flat `transcriptText` and
`utterances` shape is consumed downstream.

L2 doesn't filter low-confidence utterances. L3 doesn't see
confidence at all. The `formatRoleLabeledLine` function
(`03-extract-entities.ts:170-181`) builds:

```
[Doctor #0, 02:14]: utterance text here
```

No confidence indicator. So when L4 builds a SOAP from the
role-labeled transcript, it can't distinguish:
- "Patient reports diabetes" — confidence 0.95 (Deepgram heard
  it clearly)
- "Patient reports diabetes" — confidence 0.45 (model heard
  garbled audio and chose "diabetes" as best guess)

### Why this is a quality issue

The model treats both utterances as ground truth. For low-
confidence utterances the model is structurally over-confident.

This is the structural reason why Finding 02.5 (heavy accent /
mumbling → garbled output → hallucinated SOAP) happens. The
defense isn't model-side; it's surfacing the confidence in the
input.

### Headroom

Two paths:

1. **Soft**: Flag the entire visit's mean utterance confidence
   if low (Finding 02.5 already discusses this). Doctor sees
   a needsReview banner.

2. **Hard**: Annotate per-utterance confidence in the role-
   labeled transcript:

   ```
   [Doctor #0, 02:14, conf=0.95]: I'm prescribing metformin
   [Patient #1, 02:18, conf=0.42]: <unclear/low confidence: I have diabetes>
   ```

   The L3 / L4 prompts then have a rule: "Treat utterances
   with confidence <0.6 as 'I think the patient said X but
   the audio was unclear.' Use [unclear] markers in the
   resulting SOAP rather than asserting X confidently."

(2) is the higher-quality option. Doctors get to see what
the AI was uncertain about, and the L4 SOAP becomes a
faithful reflection of the audio quality, not a polished
overconfident version.

### Recommended fix

Phase 1: include the soft check (Finding 02.5).
Phase 2: include per-utterance confidence in the role-labeled
transcript and update L3/L4/L5 prompts to handle it.

### Estimated PR scope
**Phase 1 small**, **Phase 2 medium**.

---

## 07.4 — L4 sees both entities AND transcript; conflict resolution is unspecified

This overlaps with Finding 01.5 (prompt quality) — listed for
cross-reference here.

L4's user message contains both `entities` (structured) and
`roleLabeledTranscript` (raw). When they disagree, the model
picks inconsistently. See Finding 01.5 for the recommended fix.

---

## 07.5 — Visit-level metadata (patient age, weight, prior visits) doesn't reach the layers

**Severity:** Q1
**Layer affected:** orchestration / L3 / L4 / L7c
**Quality dimension:** accuracy, safety, specialty-fit

### What's happening today

`apps/transcribe-md/src/worker.ts:240-253` — the worker reads:

```typescript
const visit = await prisma.transcribeVisit.findUnique({
  where: { id: visitId },
  select: {
    id: true,
    userId: true,
    audioKey: true,
    audioMimeType: true,
    dictationAudioKey: true,
    rawTextInput: true,
    specialty: true,
    inputMode: true,
    user: { select: { practiceId: true } },
  },
});
```

Patient row is NOT pulled. Patient relation is on the visit
table but never selected. Therefore:
- `patient.dateOfBirth` not available to layers
- `patient.weightKg` not available
- `patient.allergies` not directly available (entities have
  allergies, but those are extracted from THIS visit's
  conversation; chronic allergies recorded historically at the
  patient level aren't passed in)
- Prior-visit history not passed (no "patient was here last
  week with X")

### Why this is a quality issue

- **Pediatric Rx safety** — without DOB + weight, the dose
  validator can't fire its peds path (Finding 01.1 + 06.1).
- **Allergy cross-check** — patient may have a documented
  allergy (penicillin) from a year ago that wasn't mentioned
  in today's conversation. L7c sees only today's entities. If
  the doctor prescribes amoxicillin without the patient
  re-declaring the allergy, L7c misses it.
- **Continuity** — L4 SOAP has no concept of "patient's BP
  trend over last 6 visits." Each visit is independent.

### Headroom

For the pilot, two specific gains:

1. **Safety-critical**: pull `patient.dateOfBirth +
   patient.weightKg + patient.allergies` and pass to L7c.
   Closes the Finding 06.1 gap (pediatric dose validator) AND
   the historical-allergy cross-check.

2. **Continuity nice-to-have**: pull the last 3-5 visits'
   entities for this patient, summarize as
   "patientPriorContext", and pass to L4. Lets the SOAP
   reference "Per chart, A1c was 8.2 last visit; today's is
   7.6 — improving." Today the AI can't see past visits.

### Recommended fix (safety-only for Phase 1)

Worker addition:

```typescript
const visit = await prisma.transcribeVisit.findUnique({
  where: { id: visitId },
  select: {
    ...,
    patient: {
      select: {
        id: true,
        dateOfBirth: true,
        weightKg: true,
        allergies: true,
        // For continuity (Phase 2):
        // priorVisits: {
        //   take: 5,
        //   orderBy: { signedAt: 'desc' },
        //   where: { id: { not: visitId }, signedAt: { not: null } },
        //   select: { entities: true, soapFinal: true, signedAt: true },
        // },
      },
    },
    user: { select: { practiceId: true } },
  },
});
```

Then thread `patient` through to L7c (and L3 for
specialty-aware extraction; see Finding 03.x).

### Estimated PR scope
**Medium** for safety wiring; **Large** if continuity is included.

---

## 07.6 — Deepgram's `transcriptRaw` is persisted but the rich payload is barely used

**Severity:** Q3
**Layer affected:** L1 → downstream
**Quality dimension:** observability, future-proof

### What's happening today

`01-transcribe.ts:91-97` persists the full Deepgram response
as `transcriptRaw`. The downstream consumers only read
`utterances[]` and `transcript` from it.

Deepgram nova-3-medical also returns:
- Per-word timing + confidence
- Detected entities (medications, conditions) — Deepgram has
  its own NER pass
- Topic classification
- Audio metadata (sample rate, codec)

None of these are consumed today.

### Why this is a (low-severity) quality issue

The Deepgram NER pass could provide a deterministic floor for
the L3 entities — anywhere Claude misses a medication that
Deepgram detected, the discrepancy is a signal worth surfacing
(either Deepgram's NER is wrong or L3 missed it).

### Recommended fix

Phase 7+: a cross-check pass between Deepgram NER + L3 entities
that flags discrepancies. Not pre-pilot.

### Estimated PR scope
**Defer to Phase 7**.
