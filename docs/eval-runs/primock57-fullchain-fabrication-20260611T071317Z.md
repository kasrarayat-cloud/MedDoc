# PriMock57 FULL-CHAIN fabrication eval — 20260611T071317Z

**Question answered:** what is the CURRENT full-pipeline clinical-fabrication rate (class-c) on PriMock57, real-model?

## Environment (exact)

| Field | Value |
|---|---|
| Pipeline | real Deepgram nova-3-medical → L3 entities → L4 SOAP → L5 self-critique → L6 polish |
| L3 model | `claude-sonnet-4-6` (tm_entities) |
| L4 model | `claude-opus-4-8` (tm_soap_draft) |
| L5 model | `claude-opus-4-8` (tm_critique) |
| L6 model | `claude-sonnet-4-6` (tm_polish) |
| Judge model | `claude-sonnet-4-6` temp 0; one combined call per case rates BOTH SOAPs, a/b/c rubric, present_in dedup |
| MOCK_AI_CALLS | false (real models) |
| DATABASE_URL | meddoc_qa_test on isolated meddoc-qa stack (NOT prod `meddoc`); prisma writes additionally stubbed to no-ops (zero rows) |
| Visits signed | 0 (chain stops at L6; no sign, no email) |

## HEADLINE

- **TODAY's total class-(c) genuine fabrications across the sample (FINAL post-L6 SOAP): 0** across n=1 cases (0 case(s) carry ≥1 class-c).
- Post-L4 (pre-critique) class-(c): 0. Net L5/L6 change on class-c: +0.
- (a)=ASR-propagation, (b)=benign inference, (c)=genuine fabrication. Only (c) is the dangerous "hallucination" number.

## Per-case table

| Case | src | WER | post-L4 (a/b/c) | FINAL (a/b/c) | L5 overall (crit) | notes |
|---|---|---|---|---|---|---|
| day1_consultation04 | audio | 20.4% | 0/4/0 | 0/5/0 | high (0) |  |

**Totals (FINAL):** class-a=0, class-b=5, class-c=0.

## Class-(c) genuine fabrications — verbatim evidence

_No class-(c) genuine fabrications found in EITHER the post-L4 or the final SOAP across the sample._

## Did L5 self-critique / L6 polish change the fabrication set?

- class-(c) REMOVED by L5/L6 (in L4, gone from FINAL): 0
- class-(c) INTRODUCED at/after L6 (not in L4): 0
- class-(c) SURVIVED L4→FINAL unchanged: 0

## Raw per-case dump (combined-judge flags + both SOAPs)

<details><summary>day1_consultation04 — src=audio, WER=20.4%, dur=615.48s</summary>

**L5 critique:** overall=high, safe_to_sign=false, issues=4, critical=0

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "The sore throat was quite painful to swallow for one of the days",
    "class": "b",
    "severity": "low",
    "transcript_span": "it was quite painful to swallow, for one or two days",
    "present_in": "both",
    "rationale": "The SOAP says 'one of the days' but the patient said 'one or two days' — a minor paraphrase that slightly narrows the stated duration but does not invent a clinical fact."
  },
  {
    "invented_text": "Nasal discharge is clear",
    "class": "b",
    "severity": "low",
    "transcript_span": "it's uh it's clearing up",
    "present_in": "both",
    "rationale": "The patient said the discharge is 'clearing up' (i.e., improving/resolving), not necessarily that it is clear in colour; the SOAP interprets this as clear-coloured discharge, which is a reasonable but not fully supported clinical inference."
  },
  {
    "invented_text": "Throat inspection was not performed; patient was unable to self-inspect when asked.",
    "class": "b",
    "severity": "low",
    "transcript_span": "Um no, not really. No. Um I I didn't think about uh",
    "present_in": "final_only",
    "rationale": "The transcript shows the patient simply hadn't looked; 'unable to self-inspect' slightly mischaracterises this as inability rather than not having tried, but this is a minor stylistic inference with no dangerous clinical implication."
  },
  {
    "invented_text": "muscle aches and joint pain beginning in the past couple of days",
    "class": "b",
    "severity": "low",
    "transcript_span": "Yeah, yeah. Yeah that's, that sort of started in the past couple days.",
    "present_in": "both",
    "rationale": "The transcript confirms muscle/joint pain started in the past couple of days; the SOAP combines 'muscle aches and joint pain' from the doctor's question and patient's affirmative, which is a reasonable and supported inference."
  },
  {
    "invented_text": "The patient remains hemodynamically stable enough to attend work",
    "class": "b",
    "severity": "low",
    "transcript_span": "I've been actually going to work, um sort of managing.",
    "present_in": "both",
    "rationale": "Describing the patient as 'hemodynamically stable' is a clinical interpretive label not stated in the transcript; it is a reasonable clinical inference but introduces terminology not present in the source."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling under the weather for the past four days with sore throat, runny nose, and cough.

**HPI:** Per patient, a previously well adult presents with a four-day history of feeling under the weather. Symptoms began with a sore throat and runny nose and have progressed to a cough. The sore throat was quite painful to swallow for one of the days and is now resolving. Nasal discharge is clear with associated nasal congestion that he finds hard to clear. The cough started approximately one day ago, is dry, not very painful, and present constantly throughout the day with no particular time of worsening. He reports night sweats over the past three to four days that make him feel tired. He had a fever at the onset, now settling, for which he has been taking paracetamol and ibuprofen with relief. He reports feeling winded on exertion (e.g., declining gym attendance), which resolves at rest, with no chest pain. He also notes intermittent generalised headaches, reduced appetite, drinking more than usual, and muscle aches and joint pain beginning in the past couple of days. He attributes the illness to a colleague who was sneezing repeatedly at work, whose children may have caught something from kindergarten.

**PMH:** 
- Per patient, no chronic medical problems; not being treated for anything.

**Medications:** 
- Paracetamol [dose/frequency not documented]
- Ibuprofen [dose/frequency not documented]

**Allergies:** 
- No known drug allergies.

**Family History:** 
- Grandmother — type 2 diabetes (per patient)
- Great-grandfather — eczema (per patient)

**Social History:** 
- Smoking: Occasional only — cigars at company parties, not regular.
- Alcohol: Occasional social drinker.
- Occupation: Accountant; reports a stressful period around year-end and feeling slightly slower at work.
- Lives alone.

**ROS:**
- ENT: Sore throat with painful swallowing for one day, now improving; clear nasal discharge with congestion; no ear pain, no ear blockage, no ear discharge.
- Respiratory: Dry, constant cough started yesterday; shortness of breath on exertion only; no chest pain.
- Constitutional: Night sweats for the past three to four days; fever initially present, now settling; fatigue.
- Neurological: Intermittent generalised headaches; no visual disturbance; no photophobia.
- Gastrointestinal: No nausea, no vomiting; bowels working normally; reduced appetite; drinking more than usual.
- Genitourinary: Urine normal.
- Dermatological: No rashes.
- Musculoskeletal: Muscle aches and joint pain starting in the past couple of days.

## Objective
Formal exam not documented in this encounter.

## Assessment
Viral illness, likely a viral upper respiratory tract infection or early influenza, per the doctor's clinical impression. Supporting features include the four-day prodrome beginning with sore throat and runny nose, progression to a dry cough, initial fever now settling, night sweats, generalised headaches, and recent muscle and joint aches, in the context of a likely sick contact at work. The patient remains hemodynamically stable enough to attend work, with shortness of breath only on exertion and no chest pain.

Differentials: [not documented]
Severity/staging: [not documented]

## Plan
1. Reassurance provided: viral illness typically resolves over seven to ten days.
2. Advise rest; take one to two days off work if able.
3. Push fluids and maintain good hydration.
4. Continue regular paracetamol and ibuprofen.
5. Follow-up: return to clinic next week if not improving.
6. Safety-netting: return sooner / call if high fever, worsening or labored breathing, or chest pain develop.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling under the weather for the past four days with sore throat, runny nose, and cough.

**HPI:** Per patient, a previously well adult presents with a four-day history of feeling under the weather. Symptoms began with a sore throat and runny nose and have progressed to a cough. The sore throat was quite painful to swallow for one of the days and is now resolving. Nasal discharge is clear with associated nasal congestion that he finds hard to clear. The cough started approximately one day ago, is dry, not very painful, and present constantly throughout the day with no particular time of worsening. He reports night sweats over the past three to four days that make him feel tired. He had a fever at the onset, now settling, for which he has been taking paracetamol and ibuprofen with relief. He reports feeling winded on exertion (e.g., he has stopped attending the gym due to exertional breathlessness but continues to attend work), which resolves at rest, with no chest pain. He also notes intermittent generalised headaches, reduced appetite, drinking more than usual, and muscle aches and joint pain beginning in the past couple of days. He attributes the illness to a colleague who was sneezing repeatedly at work, whose children may have caught something from kindergarten.

**PMH:** 
- Per patient, no chronic medical problems; not being treated for anything.

**Medications:** 
- Paracetamol [dose/frequency not documented]
- Ibuprofen [dose/frequency not documented]

**Allergies:** 
- No known drug allergies.

**Family History:** 
- Grandmother — type 2 diabetes (per patient)
- Great-grandfather — eczema (per patient)

**Social History:** 
- Smoking: Occasional only — cigars at company parties, not regular.
- Alcohol: Occasional social drinker.
- Occupation: Accountant; reports a stressful period around year-end and feeling slightly slower at work. When screened for mood and anxiety impact, patient denied any negative mood or anxiety effect, characterising the stress as positive ("the good kind of stress").
- Lives alone.

**ROS:**
- ENT: Sore throat with painful swallowing for one day, now improving; clear nasal discharge with congestion; no ear pain, no ear blockage, no ear discharge.
- Respiratory: Dry, constant cough started yesterday; shortness of breath on exertion only; no chest pain.
- Constitutional: Night sweats for the past three to four days; fever initially present, now settling; fatigue.
- Neurological: Intermittent generalised headaches; no visual disturbance; no photophobia.
- Gastrointestinal: No nausea, no vomiting; bowels working normally; reduced appetite; drinking more than usual.
- Genitourinary: Urine normal.
- Dermatological: No rashes.
- Musculoskeletal: Muscle aches and joint pain starting in the past couple of days.
- Mood/Anxiety: Screened; patient denied mood or anxiety impact from current stressors.

## Objective
Formal exam not documented in this encounter. Throat inspection was not performed; patient was unable to self-inspect when asked.

## Assessment
Viral illness, likely a viral upper respiratory tract infection or early influenza, per the doctor's clinical impression. Supporting features include the four-day prodrome beginning with sore throat and runny nose, progression to a dry cough, initial fever now settling, night sweats, generalised headaches, and recent muscle and joint aches, in the context of a likely sick contact at work. The patient remains hemodynamically stable enough to attend work, with shortness of breath only on exertion and no chest pain.

No formal differentials were documented beyond viral URI vs. early influenza; no formal severity staging was discussed.

## Plan
1. Reassurance provided: viral illness typically resolves over seven to ten days.
2. Advise rest; take one to two days off work if able.
3. Push fluids and maintain good hydration.
4. Continue regular paracetamol and ibuprofen.
5. Follow-up: return to clinic next week if not improving.
6. Safety-netting: return sooner / call if high fever, worsening or labored breathing, or chest pain develop.
```
</details>
