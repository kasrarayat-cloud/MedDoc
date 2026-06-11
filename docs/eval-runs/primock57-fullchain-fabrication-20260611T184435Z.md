# PriMock57 FULL-CHAIN fabrication eval — 20260611T184435Z

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

- **TODAY's total class-(c) genuine fabrications across the sample (FINAL post-L6 SOAP): 2** across n=12 cases (2 case(s) carry ≥1 class-c).
- Post-L4 (pre-critique) class-(c): 3. Net L5/L6 change on class-c: -1.
- **Polish-survival rate:** 3/12 polished notes kept (9 L6b gate fallbacks → pre-L6 draft served: day5_consultation10, day1_consultation05, day1_consultation02, day4_consultation08, day1_consultation01, day1_consultation03, day1_consultation04, day3_consultation01, day3_consultation05).
- (a)=ASR-propagation, (b)=benign inference, (c)=genuine fabrication. Only (c) is the dangerous "hallucination" number.
- **[unclear in recording] markers (clarity pass):** 200 total across 12 cases (per-case in the table) — the notes should hedge where these appear.

## Per-case table

| Case | src | WER | [unclear] | post-L4 (a/b/c) | FINAL (a/b/c) | L5 overall (crit) | L6b gate | notes |
|---|---|---|---|---|---|---|---|---|
| day5_consultation10 | audio | 17.5% | 23 | 0/3/0 | 0/3/0 | medium (2) | REJECTED→draft |  |
| day1_consultation05 | audio | 17.4% | 18 | 0/0/1 | 0/0/1 | low (3) | REJECTED→draft |  |
| day1_consultation02 | audio | 18.9% | 16 | 1/2/0 | 1/2/0 | medium (2) | REJECTED→draft |  |
| day1_consultation08 | audio | 20.4% | 11 | 1/1/1 | 1/1/0 | medium (1) | kept |  |
| day4_consultation08 | audio | 18.2% | 15 | 1/0/0 | 1/0/0 | high (1) | REJECTED→draft |  |
| day1_consultation01 | audio | 19.4% | 13 | 1/1/0 | 1/1/0 | high (1) | REJECTED→draft |  |
| day1_consultation03 | audio | 17.1% | 21 | 1/0/0 | 1/0/0 | medium (0) | REJECTED→draft |  |
| day1_consultation04 | audio | 20.4% | 18 | 1/5/0 | 1/5/0 | high (0) | REJECTED→draft |  |
| day2_consultation01 | audio | 17.8% | 13 | 0/2/1 | 0/2/1 | high (0) | kept |  |
| day2_consultation05 | audio | 14.5% | 21 | 0/6/0 | 0/5/0 | high (1) | kept |  |
| day3_consultation01 | audio | 15.6% | 20 | 1/1/0 | 1/1/0 | low (3) | REJECTED→draft |  |
| day3_consultation05 | audio | 13.8% | 11 | 0/3/0 | 0/3/0 | low (2) | REJECTED→draft |  |

**Totals (FINAL):** class-a=7, class-b=23, class-c=2.

## Class-(c) genuine fabrications — verbatim evidence

### day1_consultation05 (WER 17.4%, src audio)

- invented: `orally` — severity **low** — _L4 emitted → SURVIVED L5/L6 into FINAL_
  - transcript span: _absent (nothing in transcript)_
  - judge rationale: The route of administration for trimethoprim is never stated in the ASR transcript; 'orally' is a patient-specific prescribing detail invented by the model, though clinically it is the expected route for this drug.

### day1_consultation08 (WER 20.4%, src audio)

- invented: `no cracked skin` — severity **low** — _L4 emitted → REMOVED by L5/L6 (not in FINAL)_
  - transcript span: _absent (nothing in transcript)_
  - judge rationale: The doctor asked about cracked skin but the patient never confirmed or denied it in the ASR transcript; the SOAP-A assertion of 'no cracked skin' as a patient-reported finding is not supported by the ASR transcript.

### day2_consultation01 (WER 17.8%, src audio)

- invented: `self-resolving` — severity **low** — _L4 emitted → SURVIVED L5/L6 into FINAL_
  - transcript span: _absent (nothing in transcript)_
  - judge rationale: The ASR transcript states the prior episode 'only lasted a couple of days' but never describes it as self-resolving; this causal/outcome characterisation is not supported by the transcript.

## Did L5 self-critique / L6 polish change the fabrication set?

- class-(c) REMOVED by L5/L6 (in L4, gone from FINAL): 1 — day1_consultation08: "no cracked skin"
- class-(c) INTRODUCED at/after L6 (not in L4): 0
- class-(c) SURVIVED L4→FINAL unchanged: 2

## Raw per-case dump (combined-judge flags + both SOAPs)

<details><summary>day5_consultation10 — src=audio, WER=17.5%, dur=586.08s</summary>

**L5 critique:** overall=medium, safe_to_sign=false, issues=5, critical=2

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "fundoscopy (examination of the back of the eyes)",
    "class": "b",
    "severity": "low",
    "transcript_span": "look at the back of your eyes as well",
    "present_in": "both",
    "rationale": "The ASR transcript describes looking at the back of the eyes; 'fundoscopy' is the standard clinical term for this procedure and introduces no new patient-specific fact."
  },
  {
    "invented_text": "full physical examination",
    "class": "b",
    "severity": "low",
    "transcript_span": "we should do [unclear in recording] examination",
    "present_in": "both",
    "rationale": "The ASR has '[unclear in recording] examination' where the reference confirms 'neurological examination'; the SOAP uses the broader 'full physical examination,' which is a reasonable inference from the garbled input rather than a fabrication."
  },
  {
    "invented_text": "combined oral contraceptive pill",
    "class": "b",
    "severity": "low",
    "transcript_span": "that pill, if you're having [unclear in recording] migraines with flashing lights or [unclear in recording] symptoms, it wouldn't be suitable to stay on that pill",
    "present_in": "both",
    "rationale": "The ASR never explicitly states 'combined' OCP, but the doctor's advice about changing the pill if migraine with aura is confirmed is clinically specific to combined (estrogen-containing) pills; this is a reasonable clinical inference with no new patient-specific fact invented."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Blinding headache for a few days.

**HPI:** Per patient, this is a blinding headache that began suddenly three days ago, present on waking in the morning. The pain is constant and located all over the head, but stronger over the right eye. Per patient, severity is mostly 8/10, decreasing to about 5/10 with ibuprofen but not resolving. The headache is worse with quick positional change (stabbing pain on standing up quickly) and head movement (a sensation of "something moving inside"). Associated symptoms include photosensitivity, visual disturbance described as "shooting light" sometimes, nausea ("feeling a bit sick") without vomiting, and lack of energy that the patient attributes to the headache. The headache does not wake the patient at night, and sleep is reported as normal. Per patient, prior headaches were occasional, lasting no more than two days, described as pressure between the eyes, with no visual symptoms and no nausea/vomiting, and resolved with ibuprofen. The patient has worked from home and missed work due to difficulty focusing during this episode.

**PMH:**
- Per patient, possible prior illness when younger — "[unclear in recording]" — no diagnosis found, resolved spontaneously [clarify with patient].

**Medications:**
- Oral contraceptive pill — "Methylene" [unclear in recording], started about a year ago [clarify with patient]
- Ibuprofen, as needed for headache (dose not stated)

**Allergies:**
- No known allergies.

**Family History:**
- Mother: migraines (described as severe, with vomiting).

**Social History:**
- Smoking: non-smoker.
- Alcohol: approximately three beers once a week.
- Drugs: denies recreational drug use.
- Occupation: works from home.
- Lives alone.

**ROS:**
- Neurological: No tingling, numbness, or weakness. No change in smell or taste.
- Ophthalmological: Photosensitivity and visual disturbance (shooting/flashing lights).
- Gastrointestinal: Nausea present, no vomiting.
- ENT/Haematological: No nosebleeds; no haemoptysis.
- Constitutional: No weight change; lack of energy (attributed to headache); no fever; no recent travel abroad.

## Objective
Formal exam not documented in this encounter.

Per patient, blood pressure was checked at a pharmacy approximately one year ago (when starting the contraceptive pill) and reported as normal.

## Assessment
Per the doctor, the presentation could possibly be a migraine-type headache, with visual disturbance (flashing lights). Given the symptoms have been ongoing for three days, an in-person examination was advised. The doctor noted that if migraine with aura is confirmed, the combined oral contraceptive pill may not be suitable and would need to be changed. Family history of migraines (mother) noted.

Differentials beyond migraine-type headache: [not documented].

## Plan
1. Book in-person appointment for full physical examination, including fundoscopy (examination of the back of the eyes) and blood pressure check to confirm appropriateness of contraceptive pill.
2. Prescribe an NSAID alternative to ibuprofen — "[unclear in recording]" — to be taken with food, alongside paracetamol [clarify with patient].
3. Continue current contraceptive pill for now; review and potentially change if migraine with aura is confirmed.
4. Safety-net advice: if headache becomes unbearable, worsens, or changes before the appointment, call for further advice or attend A&E for examination.
5. If headache settles before the appointment, the appointment may be cancelled.
6. Patient education provided regarding shared decision-making on contraceptive pill suitability if migraine with aura is confirmed.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Blinding headache for a few days.

**HPI:** Per patient, this is a blinding headache that began suddenly three days ago, present on waking in the morning. The pain is constant and located all over the head, but stronger over the right eye. Per patient, severity is mostly 8/10, decreasing to about 5/10 with ibuprofen but not resolving. The headache is worse with quick positional change (stabbing pain on standing up quickly) and head movement (a sensation of "something moving inside"). Associated symptoms include photosensitivity, visual disturbance described as "shooting light" sometimes, nausea ("feeling a bit sick") without vomiting, and lack of energy that the patient attributes to the headache. The headache does not wake the patient at night, and sleep is reported as normal. Per patient, prior headaches were occasional, lasting no more than two days, described as pressure between the eyes, with no visual symptoms and no nausea/vomiting, and resolved with ibuprofen. The patient has worked from home and missed work due to difficulty focusing during this episode.

**PMH:**
- Per patient, possible prior illness when younger — "[unclear in recording]" — no diagnosis found, resolved spontaneously [clarify with patient].

**Medications:**
- Oral contraceptive pill — "Methylene" [unclear in recording], started about a year ago [clarify with patient]
- Ibuprofen, as needed for headache (dose not stated)

**Allergies:**
- No known allergies.

**Family History:**
- Mother: migraines (described as severe, with vomiting).

**Social History:**
- Smoking: non-smoker.
- Alcohol: approximately three beers once a week.
- Drugs: denies recreational drug use.
- Occupation: works from home.
- Lives alone.

**ROS:**
- Neurological: No tingling, numbness, or weakness. No change in smell or taste.
- Ophthalmological: Photosensitivity and visual disturbance (shooting/flashing lights).
- Gastrointestinal: Nausea present, no vomiting.
- ENT/Haematological: No nosebleeds; no haemoptysis.
- Constitutional: No weight change; lack of energy (attributed to headache); no fever; no recent travel abroad.

## Objective
Formal exam not documented in this encounter.

Per patient, blood pressure was checked at a pharmacy approximately one year ago (when starting the contraceptive pill) and reported as normal.

## Assessment
Per the doctor, the presentation could possibly be a migraine-type headache, with visual disturbance (flashing lights). Given the symptoms have been ongoing for three days, an in-person examination was advised. The doctor noted that if migraine with aura is confirmed, the combined oral contraceptive pill may not be suitable and would need to be changed. Family history of migraines (mother) noted.

Differentials beyond migraine-type headache: [not documented].

## Plan
1. Book in-person appointment for full physical examination, including fundoscopy (examination of the back of the eyes) and blood pressure check to confirm appropriateness of contraceptive pill.
2. Prescribe an NSAID alternative to ibuprofen — "[unclear in recording]" — to be taken with food, alongside paracetamol [clarify with patient].
3. Continue current contraceptive pill for now; review and potentially change if migraine with aura is confirmed.
4. Safety-net advice: if headache becomes unbearable, worsens, or changes before the appointment, call for further advice or attend A&E for examination.
5. If headache settles before the appointment, the appointment may be cancelled.
6. Patient education provided regarding shared decision-making on contraceptive pill suitability if migraine with aura is confirmed.
```
</details>

<details><summary>day1_consultation05 — src=audio, WER=17.4%, dur=577.02s</summary>

**L5 critique:** overall=low, safe_to_sign=false, issues=7, critical=3

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "orally",
    "class": "c",
    "severity": "low",
    "transcript_span": "absent",
    "present_in": "both",
    "rationale": "The route of administration for trimethoprim is never stated in the ASR transcript; 'orally' is a patient-specific prescribing detail invented by the model, though clinically it is the expected route for this drug."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Lower abdominal pain with feeling hot and sweaty.

**HPI:** Per patient, a female who presents with lower abdominal pain that began about two days ago. The pain is located below the umbilicus, described as a burning quality, and is constant and progressively worsening. Per patient, the onset was gradual. She remains able to move and walk around but is aware of the pain at all times. Associated symptoms include feeling hot and sweaty (no measured temperature), mild nausea without vomiting, pink-coloured urine, and increased urinary frequency without dysuria or stinging. Per patient, she had constipation since last week which has since resolved, with normal bowel movements now and no diarrhoea or loose stools. Per patient, she is sexually active with the same partner, with last intercourse four days ago, has an Implanon in place inserted about a year ago, and her last period was about two weeks ago. She uses no barrier contraception. Per patient, her last STI screen was normal.

**PMH:** [not documented]

**Medications:**
- Implanon — inserted about a year ago

**Allergies:** [not documented]

**Family History:** Per patient, no relevant bowel or gynaecological family history.

**Social History:**
- Smoking: Non-smoker
- Alcohol: Per patient, drinks socially, not more than normal
- Occupation: Accountant
- Lives in a share house with two roommates

**ROS:**
- Constitutional: Per patient, feeling hot and sweaty; no measured temperature.
- Gastrointestinal: Lower abdominal burning pain below umbilicus, constant and worsening; recent constipation now resolved; no diarrhoea or loose stools; mild nausea, no vomiting.
- Genitourinary: Pink-coloured urine; increased urinary frequency; no dysuria.
- Respiratory: No shortness of breath, no cough.
- Cardiovascular: No palpitations.
- Neurological: No headaches, no visual disturbance.

## Objective
Formal exam not documented in this encounter.

Tests mentioned:
- Per patient, prior STI screen result normal (timing [unclear in recording]).

## Assessment
Lower abdominal pain, cause not yet established. The clinician discussed a differential including urinary tract infection, a gastrointestinal cause, or a pregnancy-related cause. Given pink-coloured urine and increased urinary frequency over two days, empirical treatment for a presumed urinary tract infection was discussed, with a pregnancy test recommended to exclude a pregnancy-related cause. Severity/staging [not documented].

## Plan
1. Start trimethoprim, one tablet twice a day for three days, orally. *(Note transcript stated "two tablets... One tablet twice a day for three days" — [clarify with patient].)*
2. Paracetamol for analgesia.
3. Increase fluid intake; may try cranberry juice for urinary symptoms.
4. Perform a pregnancy test to exclude a pregnancy-related cause.
5. Prescription sent electronically to patient's pharmacy.
6. Safety-netting: return / seek review in a few days if symptoms do not improve or worsen. Red flags discussed include worsening abdominal pain, persistent fever/feeling hot and sweaty, and vomiting.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Lower abdominal pain with feeling hot and sweaty.

**HPI:** Per patient, a female who presents with lower abdominal pain that began about two days ago. The pain is located below the umbilicus, described as a burning quality, and is constant and progressively worsening. Per patient, the onset was gradual. She remains able to move and walk around but is aware of the pain at all times. Associated symptoms include feeling hot and sweaty (no measured temperature), mild nausea without vomiting, pink-coloured urine, and increased urinary frequency without dysuria or stinging. Per patient, she had constipation since last week which has since resolved, with normal bowel movements now and no diarrhoea or loose stools. Per patient, she is sexually active with the same partner, with last intercourse four days ago, has an Implanon in place inserted about a year ago, and her last period was about two weeks ago. She uses no barrier contraception. Per patient, her last STI screen was normal.

**PMH:** [not documented]

**Medications:**
- Implanon — inserted about a year ago

**Allergies:** [not documented]

**Family History:** Per patient, no relevant bowel or gynaecological family history.

**Social History:**
- Smoking: Non-smoker
- Alcohol: Per patient, drinks socially, not more than normal
- Occupation: Accountant
- Lives in a share house with two roommates

**ROS:**
- Constitutional: Per patient, feeling hot and sweaty; no measured temperature.
- Gastrointestinal: Lower abdominal burning pain below umbilicus, constant and worsening; recent constipation now resolved; no diarrhoea or loose stools; mild nausea, no vomiting.
- Genitourinary: Pink-coloured urine; increased urinary frequency; no dysuria.
- Respiratory: No shortness of breath, no cough.
- Cardiovascular: No palpitations.
- Neurological: No headaches, no visual disturbance.

## Objective
Formal exam not documented in this encounter.

Tests mentioned:
- Per patient, prior STI screen result normal (timing [unclear in recording]).

## Assessment
Lower abdominal pain, cause not yet established. The clinician discussed a differential including urinary tract infection, a gastrointestinal cause, or a pregnancy-related cause. Given pink-coloured urine and increased urinary frequency over two days, empirical treatment for a presumed urinary tract infection was discussed, with a pregnancy test recommended to exclude a pregnancy-related cause. Severity/staging [not documented].

## Plan
1. Start trimethoprim, one tablet twice a day for three days, orally. *(Note transcript stated "two tablets... One tablet twice a day for three days" — [clarify with patient].)*
2. Paracetamol for analgesia.
3. Increase fluid intake; may try cranberry juice for urinary symptoms.
4. Perform a pregnancy test to exclude a pregnancy-related cause.
5. Prescription sent electronically to patient's pharmacy.
6. Safety-netting: return / seek review in a few days if symptoms do not improve or worsen. Red flags discussed include worsening abdominal pain, persistent fever/feeling hot and sweaty, and vomiting.
```
</details>

<details><summary>day1_consultation02 — src=audio, WER=18.9%, dur=559.2s</summary>

**L5 critique:** overall=medium, safe_to_sign=false, issues=5, critical=2

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "pyrritin",
    "class": "a",
    "severity": "low",
    "transcript_span": "pyrritin",
    "present_in": "both",
    "rationale": "The ASR transcript transcribed 'Piriton' as 'pyrritin'; the SOAP faithfully reproduced the ASR text (with an [unclear in recording] hedge), but the reference transcript confirms the correct drug name is Piriton — this is an ASR recognition error, not a model invention."
  },
  {
    "invented_text": "the visit was conducted by phone/remotely",
    "class": "b",
    "severity": "low",
    "transcript_span": "Hello? Can you hear me? ... the sound quality is not great",
    "present_in": "both",
    "rationale": "The ASR transcript never explicitly states the visit modality; the SOAP infers a remote/phone encounter from the audio-quality remarks, which is a reasonable organizational inference introducing no new clinical fact."
  },
  {
    "invented_text": "previously prescribed a cream and a shower product",
    "class": "b",
    "severity": "low",
    "transcript_span": "they gave me, like, some cream and something to... When I, like, was shower... When I was in the shower, had to put something",
    "present_in": "both",
    "rationale": "The ASR transcript describes a cream and something used in the shower without naming it as a 'shower product'; calling it a 'shower product' is a reasonable paraphrase that introduces no new clinical fact."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Sore, red, itchy skin for a few days.

**HPI:** Per patient, a 31-year-old presents with a four-day history of sore, red, and very itchy skin affecting the chest, hands, and inside of the elbows. Per patient, the itching is constant ("all the time") and severe enough to prevent sleep at night and to interfere with concentration at work and with leisure activities such as hiking. Per patient, the skin is cracked in some parts; he denies any bleeding, pus, or discharge. Per patient, he has a history of eczema previously confined to the arms, and these current symptoms are more itchy and more widespread than his prior eczema. Per patient, he is unaware of any new triggers (no change in shower gel or clothing reported). Per patient, he bought an over-the-counter steroid cream from the pharmacy the previous night, which did not help, and has tried antihistamines, which also did not help. Per patient, he takes daily showers to ease the itching. He denies fever, cough, breathing difficulties, and bowel or urinary symptoms.

**PMH:**
- Eczema (previously prescribed a cream and a shower product)
- Asthma (per patient, in the past; not anymore)

**Medications:**
- Steroid cream (OTC, name unknown), topical — used last night
- Antihistamines (OTC, name unknown) — tried recently
- Per patient, no regular medications currently.

**Allergies:**
- No known allergies.

**Family History:** [not documented]

**Social History:**
- Smoking: Non-smoker.
- Alcohol: Per patient, a few beers per week; reports drinking more when younger.
- Occupation: Project manager at a pharmaceutical company.
- Living situation: Per patient, lives with a few flatmates.

**ROS:**
- Constitutional: No fever.
- Respiratory: No cough, no breathing difficulties.
- Gastrointestinal: Bowels working normally.
- Genitourinary: Passing urine normally.
- Dermatology: Itchy, sore, red, cracked skin on chest, hands, and inside elbows; no bleeding or discharge.

## Objective
Formal exam not documented in this encounter. (Of note, the clinician stated he normally would examine the patient; the visit was conducted by phone/remotely and the clinician remarked the rash "does appear quite familiar," but no formal physical examination was documented.)

## Assessment
Likely flare-up of eczema. The clinician's reasoning is based on the patient's history of eczema combined with the very itchy, sore, cracked skin affecting the chest and other areas. Severity/staging: [not documented].

Differentials: [not documented].

## Plan
1. Prescribe a stronger topical prescription steroid cream.
2. Prescribe emollients to moisturize the skin, for use in the bath and shower.
3. Use the steroid and emollients regularly for the first 7–10 days before reassessing whether they are working.
4. Antihistamines for itch: OTC options such as loratadine or "pyrritin" [unclear in recording] suggested; a stronger prescription antihistamine, fexofenadine, offered today. Note: patient reports prior antihistamines did not help.
5. Keep a diary of potential triggers (clothing, shower gels, soaps) to review at the next visit.
6. Follow-up in one week if symptoms do not improve.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Sore, red, itchy skin for a few days.

**HPI:** Per patient, a 31-year-old presents with a four-day history of sore, red, and very itchy skin affecting the chest, hands, and inside of the elbows. Per patient, the itching is constant ("all the time") and severe enough to prevent sleep at night and to interfere with concentration at work and with leisure activities such as hiking. Per patient, the skin is cracked in some parts; he denies any bleeding, pus, or discharge. Per patient, he has a history of eczema previously confined to the arms, and these current symptoms are more itchy and more widespread than his prior eczema. Per patient, he is unaware of any new triggers (no change in shower gel or clothing reported). Per patient, he bought an over-the-counter steroid cream from the pharmacy the previous night, which did not help, and has tried antihistamines, which also did not help. Per patient, he takes daily showers to ease the itching. He denies fever, cough, breathing difficulties, and bowel or urinary symptoms.

**PMH:**
- Eczema (previously prescribed a cream and a shower product)
- Asthma (per patient, in the past; not anymore)

**Medications:**
- Steroid cream (OTC, name unknown), topical — used last night
- Antihistamines (OTC, name unknown) — tried recently
- Per patient, no regular medications currently.

**Allergies:**
- No known allergies.

**Family History:** [not documented]

**Social History:**
- Smoking: Non-smoker.
- Alcohol: Per patient, a few beers per week; reports drinking more when younger.
- Occupation: Project manager at a pharmaceutical company.
- Living situation: Per patient, lives with a few flatmates.

**ROS:**
- Constitutional: No fever.
- Respiratory: No cough, no breathing difficulties.
- Gastrointestinal: Bowels working normally.
- Genitourinary: Passing urine normally.
- Dermatology: Itchy, sore, red, cracked skin on chest, hands, and inside elbows; no bleeding or discharge.

## Objective
Formal exam not documented in this encounter. (Of note, the clinician stated he normally would examine the patient; the visit was conducted by phone/remotely and the clinician remarked the rash "does appear quite familiar," but no formal physical examination was documented.)

## Assessment
Likely flare-up of eczema. The clinician's reasoning is based on the patient's history of eczema combined with the very itchy, sore, cracked skin affecting the chest and other areas. Severity/staging: [not documented].

Differentials: [not documented].

## Plan
1. Prescribe a stronger topical prescription steroid cream.
2. Prescribe emollients to moisturize the skin, for use in the bath and shower.
3. Use the steroid and emollients regularly for the first 7–10 days before reassessing whether they are working.
4. Antihistamines for itch: OTC options such as loratadine or "pyrritin" [unclear in recording] suggested; a stronger prescription antihistamine, fexofenadine, offered today. Note: patient reports prior antihistamines did not help.
5. Keep a diary of potential triggers (clothing, shower gels, soaps) to review at the next visit.
6. Follow-up in one week if symptoms do not improve.
```
</details>

<details><summary>day1_consultation08 — src=audio, WER=20.4%, dur=466.2s</summary>

**L5 critique:** overall=medium, safe_to_sign=false, issues=4, critical=1

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "Microgynon (contraceptive pill)",
    "class": "b",
    "severity": "low",
    "transcript_span": "It's a contraceptive pill.",
    "present_in": "both",
    "rationale": "The ASR transcript confirms Microgynon is a contraceptive pill; adding the generic drug class label in parentheses is standard clinical documentation and introduces no new patient-specific fact."
  },
  {
    "invented_text": "no cracked skin",
    "class": "c",
    "severity": "low",
    "transcript_span": "absent",
    "present_in": "l4_only",
    "rationale": "The doctor asked about cracked skin but the patient never confirmed or denied it in the ASR transcript; the SOAP-A assertion of 'no cracked skin' as a patient-reported finding is not supported by the ASR transcript."
  },
  {
    "invented_text": "My name is Pfizer",
    "class": "a",
    "severity": "low",
    "transcript_span": "My name is Pfizer, and I'm 26.",
    "present_in": "both",
    "rationale": "Neither SOAP uses the name 'Pfizer', so this ASR recognition error (reference: 'Itha') is not propagated into either note; flagged only for completeness — not actually present in either SOAP."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Dry, itchy, red skin on arms and hands.

**HPI:** Per patient, a 26-year-old primary school teacher presents with dry, itchy, red skin affecting mainly the arms and hands, which began a few days ago. Per patient, symptoms started after going swimming, and she has been before. She reports the skin is red, with no spots, no sweating, and no cracked skin. The rash has not spread to the chest, legs, or face. She has been applying coconut butter for the past few days, which has not helped with the itch. Per patient, she has also been quite tired and has been under work-related stress recently, though she does not feel her stress correlates with her symptoms. She denies fever, vomiting, bleeding, or discharge from the skin. Per patient, she wonders if it might be related to the weather.

**PMH:** [not documented]

**Medications:**
- Microgynon (contraceptive pill)

**Allergies:**
- Lactose — per patient, lactose intolerant

**Family History:**
- Father: asthma
- Mother: hay fever

**Social History:**
- Smoking: Non-smoker
- Alcohol: Does not drink
- Drugs: No recreational drug use
- Occupation: Primary school teacher
- Lives alone

**ROS:**
- Dermatologic: Dry, itchy, red skin on arms and hands; no spots; no sweating; no cracked skin.
- Constitutional: Fatigue reported; no fever.
- Gastrointestinal: Appetite normal; eating and drinking normally; bowels working normally; no vomiting; no loose stools.
- Genitourinary: No urinary problems.

## Objective
Formal exam not documented in this encounter.

## Assessment
Possible dermatitis. Per the clinician's reasoning, the patient presents with a dry, itchy red rash on the hands and arms, with onset a few days ago, possibly after swimming, and no other systemic symptoms — she is otherwise well, with no fever, bleeding, or discharge from the skin. The clinician noted that examination was not performed but offered this working consideration based on the history. No differential diagnoses or staging were documented.

## Plan
1. Start steroid cream to help with inflammation.
2. Apply emollients to the affected skin throughout the day for the next few days to help with dry skin.
3. Try over-the-counter antihistamines as needed for itchiness.
4. Provide patient information leaflet about dermatitis.
5. Return for review next week if symptoms are not improving for re-evaluation.
6. Patient education: paracetamol/painkillers not indicated for this presentation.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Really dry [unclear in recording] skin on arms and hands.

**HPI:** Per patient, a 26-year-old primary school teacher presents with dry skin affecting mainly the arms and hands, which began a few days ago. Per patient, symptoms started after going swimming, and she has been before. On further history, she reports the skin is red and itchy, with no spots, no sweating, and no cracked skin. The rash has not spread to the chest, legs, or face. She has been applying coconut butter for the past few days, which has not helped with the itch. Per patient, she has also been quite tired and has been under work-related stress recently, though she does not feel her stress correlates with her symptoms. She denies fever, vomiting, bleeding, or discharge from the skin. Per patient, she wonders if it might be related to the weather.

**PMH:** [not documented]

**Medications:**
- Microgynon (contraceptive pill)

**Allergies:**
- Lactose — per patient, lactose intolerant

**Family History:**
- Father: asthma
- Mother: hay fever

**Social History:**
- Smoking: Non-smoker
- Alcohol: Does not drink
- Drugs: No recreational drug use
- Occupation: Primary school teacher
- Lives alone

**ROS:**
- Dermatologic: Dry, itchy, red skin on arms and hands; no spots; no sweating; cracked skin not reported.
- Constitutional: Fatigue reported; no fever.
- Gastrointestinal: Appetite normal; eating and drinking normally; bowels working normally; no vomiting; no loose stools.
- Genitourinary: No urinary problems.

## Objective
Formal exam not documented in this encounter.

## Assessment
Possible dermatitis. Per the clinician's reasoning, the patient presents with a dry, itchy red rash on the hands and arms, with onset a few days ago, possibly after swimming, and no other systemic symptoms — she is otherwise well, with no fever, bleeding, or discharge from the skin. The clinician noted that examination was not performed but offered this working consideration based on the history. No differential diagnoses or staging were documented.

## Plan
1. Start steroid cream to help with inflammation.
2. Apply emollients to the affected skin throughout the day for the next few days to help with dry skin.
3. Try over-the-counter antihistamines as needed for itchiness.
4. Provide patient information leaflet about dermatitis.
5. Return for review next week if symptoms are not improving for re-evaluation.
6. Patient education: paracetamol/painkillers not indicated for this presentation.
```
</details>

<details><summary>day4_consultation08 — src=audio, WER=18.2%, dur=721.2s</summary>

**L5 critique:** overall=high, safe_to_sign=false, issues=4, critical=1

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "Per patient, no brothers or sisters",
    "class": "a",
    "severity": "low",
    "transcript_span": "I'm an [unclear in recording] child",
    "present_in": "both",
    "rationale": "The ASR transcript contains '[unclear in recording] child' where the reference transcript confirms 'only child'; the SOAP correctly inferred 'no brothers or sisters' from garbled ASR input, making this an ASR-error propagation rather than fabrication."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Low energy and difficulty waking up over approximately two months.

**HPI:** Per patient, over approximately the past two months (initially described as "a few weeks," later clarified to be closer to two months) he has experienced difficulty getting up in the morning, low energy throughout the day, and a sense that activities he previously found easy have become quite difficult. He reports trouble sleeping, poor appetite ("not eating very much"), low mood, difficulty focusing, and feeling easily distracted. Per patient, his sex drive has decreased over the past few months, and he reports feeling less interested. He notes the onset may have coincided with starting a new job approximately two months ago. Per patient, he has also noticed shortness of breath when doing sports compared to a couple of months ago. He states a wish to return to his previous baseline and to seek advice. Per patient, he denied a change with respect to morning erections.

**PMH:**
- Hypothyroidism (per patient; described after clarification of hyper- vs hypothyroid)
- Per patient, no formal psychiatric diagnosis; expresses suspicion that his father's suicide ~15 years ago may have had an impact on him

**Medications:**
- Thyroxine (currently taking; dose/frequency [not documented])

**Allergies:**
- No known medication allergies

**Family History:**
- Father: suicide approximately fifteen years ago
- Per patient, mother is well; no depression or other condition reported as running in the family
- Per patient, no brothers or sisters

**Social History:**
- Occupation: started a new job approximately two months ago
- Per patient, married for many years

**ROS:**
- General: fatigue, low energy, difficulty waking up, poor appetite
- Neuropsychiatric/Mood: low mood, difficulty focusing, easily distracted, decreased sex drive
- Sleep: difficulty sleeping
- Respiratory: shortness of breath on exertion (sports)
- Ophthalmologic: no change in vision
- Psychiatric – Safety: denies thoughts of harming self or others; denies feeling suicidal

## Objective
Formal exam not documented in this encounter.

## Assessment
Per the doctor's summary, the clinical picture is fatigue, increasing exertional shortness of breath over the last few months, lower mood, and decreased sex drive, with associated difficulty sleeping, difficulty concentrating, and poor appetite over approximately two months. Differential considerations to be investigated include a mood/depressive aetiology and a thyroid-related aetiology, given the patient's history of hypothyroidism on thyroxine. Safety screening was negative for suicidal ideation and thoughts of harm to self or others. Further severity/staging [not documented]; in-person examination and investigations are required to clarify the diagnosis.

## Plan
1. Arrange in-person review with the GP in the next few days for examination.
2. Order blood tests (specific panel [not documented]) as part of further investigation.
3. Reassess symptoms and investigation results at the in-person appointment.
4. Patient education: discussed need for a plan and further investigation; patient agreed this approach makes sense.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Low energy and difficulty waking up over approximately two months.

**HPI:** Per patient, over approximately the past two months (initially described as "a few weeks," later clarified to be closer to two months) he has experienced difficulty getting up in the morning, low energy throughout the day, and a sense that activities he previously found easy have become quite difficult. He reports trouble sleeping, poor appetite ("not eating very much"), low mood, difficulty focusing, and feeling easily distracted. Per patient, his sex drive has decreased over the past few months, and he reports feeling less interested. He notes the onset may have coincided with starting a new job approximately two months ago. Per patient, he has also noticed shortness of breath when doing sports compared to a couple of months ago. He states a wish to return to his previous baseline and to seek advice. Per patient, he denied a change with respect to morning erections.

**PMH:**
- Hypothyroidism (per patient; described after clarification of hyper- vs hypothyroid)
- Per patient, no formal psychiatric diagnosis; expresses suspicion that his father's suicide ~15 years ago may have had an impact on him

**Medications:**
- Thyroxine (currently taking; dose/frequency [not documented])

**Allergies:**
- No known medication allergies

**Family History:**
- Father: suicide approximately fifteen years ago
- Per patient, mother is well; no depression or other condition reported as running in the family
- Per patient, no brothers or sisters

**Social History:**
- Occupation: started a new job approximately two months ago
- Per patient, married for many years

**ROS:**
- General: fatigue, low energy, difficulty waking up, poor appetite
- Neuropsychiatric/Mood: low mood, difficulty focusing, easily distracted, decreased sex drive
- Sleep: difficulty sleeping
- Respiratory: shortness of breath on exertion (sports)
- Ophthalmologic: no change in vision
- Psychiatric – Safety: denies thoughts of harming self or others; denies feeling suicidal

## Objective
Formal exam not documented in this encounter.

## Assessment
Per the doctor's summary, the clinical picture is fatigue, increasing exertional shortness of breath over the last few months, lower mood, and decreased sex drive, with associated difficulty sleeping, difficulty concentrating, and poor appetite over approximately two months. Differential considerations to be investigated include a mood/depressive aetiology and a thyroid-related aetiology, given the patient's history of hypothyroidism on thyroxine. Safety screening was negative for suicidal ideation and thoughts of harm to self or others. Further severity/staging [not documented]; in-person examination and investigations are required to clarify the diagnosis.

## Plan
1. Arrange in-person review with the GP in the next few days for examination.
2. Order blood tests (specific panel [not documented]) as part of further investigation.
3. Reassess symptoms and investigation results at the in-person appointment.
4. Patient education: discussed need for a plan and further investigation; patient agreed this approach makes sense.
```
</details>

<details><summary>day1_consultation01 — src=audio, WER=19.4%, dur=457.92s</summary>

**L5 critique:** overall=high, safe_to_sign=false, issues=5, critical=1

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "Dioralyte from the pharmacy to help replenish minerals and vitamins",
    "class": "b",
    "severity": "low",
    "transcript_span": "There are things like Dioralyte you can get from the pharmacy, which it's... It helps replenish some of your minerals and vitamins.",
    "present_in": "both",
    "rationale": "The SOAP accurately reflects the ASR transcript content; 'vitamins' appears in the ASR but the reference transcript says only 'minerals and vitamins' — this is fully supported by the ASR and is not a fabrication, so this is not a flag. Actually this is fully supported — removing."
  },
  {
    "invented_text": "Paracetamol \"[unclear in recording] tablets up to four times a day\"",
    "class": "a",
    "severity": "medium",
    "transcript_span": "[unclear in recording] tablets up to four times a day for the first few days can also help",
    "present_in": "both",
    "rationale": "The ASR transcript has '[unclear in recording] tablets up to four times a day' where the reference transcript confirms 'two tablets up to four times a day'; the SOAP faithfully reproduced the ASR garble including the unclear marker, so this is an ASR-error propagation rather than fabrication, but the dose 'two tablets' is missing/unclear in the ASR."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Diarrhea for the last three days.

**HPI:** Per patient, a presents with a three-day history of loose, watery stools, going to the toilet approximately six to seven times per day, with no blood in the stool. He reports associated lower abdominal pain localized to the left side, described as a muscular cramp that comes and goes and does not radiate. Per patient, symptoms began around three to four days ago. He notes feeling weak and shaky, and felt hot/feverish at symptom onset (temperature not measured), though he has no fever currently. He reports vomiting at the start of symptoms (normal food color, no blood), which has since resolved. He also describes a loss of appetite and reduced intake but has been able to hold down fluids and light foods such as soups and smoothies. Per patient, he had a takeaway meal at a Chinese restaurant with friends approximately four days ago. Per patient, one of his children was vomiting but did not have diarrhea; no one else in the household has similar symptoms. The symptoms have been affecting his day-to-day activities, requiring him to stay close to the toilet, and he has continued going to work.

**PMH:**
- Asthma (per patient, well controlled with inhaler)

**Medications:**
- Inhaler (for asthma)

**Allergies:** [not documented]

**Family History:** [not documented]

**Social History:**
- Smoking: Non-smoker
- Alcohol: Non-drinker
- Occupation: Accountant
- Lives with wife and two children

**ROS:**
- Gastrointestinal: Loose, watery diarrhea ~6–7 times/day, no blood in stool; left lower abdominal cramping pain, intermittent; vomiting at onset (now resolved), no blood in vomit; loss of appetite, tolerating fluids and light foods.
- Constitutional: Felt hot/feverish at symptom onset; no current fever; weakness and shakiness; no night sweats.

## Objective
Formal exam not documented in this encounter. (Clinician stated intent to examine the patient; no examination findings or vital signs were recorded in the transcript.)

## Assessment
Gastroenteritis — clinician noted this is likely caused by viruses, with a possibility of bacterial cause. The clinician raised the possibility that the Chinese takeaway meal approximately four days ago may be the cause of symptoms. Severity/staging: [not documented].

## Plan
1. Conservative management; antibiotics not indicated at this stage.
2. Maintain hydration with oral fluids.
3. Dioralyte from the pharmacy to help replenish minerals and vitamins.
4. Paracetamol "[unclear in recording] tablets up to four times a day" for the first few days if feeling feverish and weak [clarify with patient].
5. Advise two to three days off work to rest.
6. Return for review if symptoms have not improved in three to four days; if symptoms are ongoing, consider further investigation including a stool sample.
7. Patient education: treatment plan discussed and confirmed clear by patient; no further questions.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Diarrhea for the last three days.

**HPI:** Per patient, a presents with a three-day history of loose, watery stools, going to the toilet approximately six to seven times per day, with no blood in the stool. He reports associated lower abdominal pain localized to the left side, described as a muscular cramp that comes and goes and does not radiate. Per patient, symptoms began around three to four days ago. He notes feeling weak and shaky, and felt hot/feverish at symptom onset (temperature not measured), though he has no fever currently. He reports vomiting at the start of symptoms (normal food color, no blood), which has since resolved. He also describes a loss of appetite and reduced intake but has been able to hold down fluids and light foods such as soups and smoothies. Per patient, he had a takeaway meal at a Chinese restaurant with friends approximately four days ago. Per patient, one of his children was vomiting but did not have diarrhea; no one else in the household has similar symptoms. The symptoms have been affecting his day-to-day activities, requiring him to stay close to the toilet, and he has continued going to work.

**PMH:**
- Asthma (per patient, well controlled with inhaler)

**Medications:**
- Inhaler (for asthma)

**Allergies:** [not documented]

**Family History:** [not documented]

**Social History:**
- Smoking: Non-smoker
- Alcohol: Non-drinker
- Occupation: Accountant
- Lives with wife and two children

**ROS:**
- Gastrointestinal: Loose, watery diarrhea ~6–7 times/day, no blood in stool; left lower abdominal cramping pain, intermittent; vomiting at onset (now resolved), no blood in vomit; loss of appetite, tolerating fluids and light foods.
- Constitutional: Felt hot/feverish at symptom onset; no current fever; weakness and shakiness; no night sweats.

## Objective
Formal exam not documented in this encounter. (Clinician stated intent to examine the patient; no examination findings or vital signs were recorded in the transcript.)

## Assessment
Gastroenteritis — clinician noted this is likely caused by viruses, with a possibility of bacterial cause. The clinician raised the possibility that the Chinese takeaway meal approximately four days ago may be the cause of symptoms. Severity/staging: [not documented].

## Plan
1. Conservative management; antibiotics not indicated at this stage.
2. Maintain hydration with oral fluids.
3. Dioralyte from the pharmacy to help replenish minerals and vitamins.
4. Paracetamol "[unclear in recording] tablets up to four times a day" for the first few days if feeling feverish and weak [clarify with patient].
5. Advise two to three days off work to rest.
6. Return for review if symptoms have not improved in three to four days; if symptoms are ongoing, consider further investigation including a stool sample.
7. Patient education: treatment plan discussed and confirmed clear by patient; no further questions.
```
</details>

<details><summary>day1_consultation03 — src=audio, WER=17.1%, dur=544.32s</summary>

**L5 critique:** overall=medium, safe_to_sign=false, issues=5, critical=0

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "Mother: migraines (not diagnosed per patient)",
    "class": "a",
    "severity": "low",
    "transcript_span": "my mom had has migraines, but not been diagnosed",
    "present_in": "both",
    "rationale": "The ASR garbles the sentence so it reads as the mother's migraines being undiagnosed, but the reference transcript clarifies the patient said her mother does have migraines and it is the patient herself who has not been diagnosed; the SOAP faithfully reproduced the ASR's ambiguous phrasing."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Left-sided headache since midday, associated with nausea and vomiting.

**HPI:** Per patient, the headache started at midday a few hours ago and came on suddenly. It is located on the left side and is throbbing in nature. A few minutes before the headache began, the patient noticed zigzag lines in the vision, followed by bilateral blurred vision. The pain is described as horrible and is making the patient feel very unwell. The headache is worse with movement, specifically leaning forward or moving the head or neck. Associated symptoms include photophobia (the patient is wearing sunglasses, with light hurting the eyes), nausea, and vomiting twice today. The patient reports a similar headache a few weeks ago that lasted a couple of days and was relieved with painkillers and bed rest. The patient expressed significant concern about the possibility of a brain tumor, noting a friend's mother recently died of a brain tumor.

**PMH:**
- Per patient, no prior migraine diagnosis.
- Per patient, no other significant medical history.

**Medications:**
- Microgynon, oral, regular (daily) — for contraception; on it for three months per patient.

**Allergies:** [not documented]

**Family History:**
- Mother: migraines (not diagnosed per patient).
- Mother: underactive thyroid.

**Social History:**
- Smoking: non-smoker.
- Alcohol: does not drink much alcohol.
- Occupation: works in the fashion industry; per patient, work is currently stressful with interpersonal pressures.
- Per patient, lives alone; does not do much exercise.

**ROS:**
- Constitutional: no fever; does not feel feverish.
- Neurological: no speech difficulties; no arm or leg weakness; no balance or coordination difficulties; no recent head injury or fall.
- Ophthalmological: photophobia; bilateral blurred vision and zigzag lines (visual aura) preceding headache.
- Gastrointestinal: nausea; vomited twice.
- Respiratory: no breathlessness.
- Dermatological: no skin rash.

## Objective
Formal exam not documented in this encounter.

## Assessment
Likely migraine with aura. The clinician noted the presentation is classical, with unilateral throbbing headache, nausea, vomiting, photophobia, and visual aura, and this is the second similar episode within the space of a month. Meningitis and brain cancer were considered and felt to be less likely based on the history; the clinician explicitly reassured the patient regarding these concerns. Microgynon (combined oral contraceptive pill) use was flagged by the clinician as requiring discussion in the context of migraine with aura.

## Plan
1. Keep a headache diary to help identify triggers.
2. Treat current episode with analgesia: paracetamol, co-codamol, and/or anti-inflammatories such as ibuprofen or naproxen.
3. Consider prophylactic migraine medication if headaches become more persistent — to be discussed at follow-up.
4. Discuss Microgynon use in the context of migraine with aura (clinician flagged this for discussion).
5. Follow-up appointment in approximately one week.
6. Safety-net: return immediately if symptoms do not improve in the next 2–3 days or worsen — specifically worsening headache not responding to medications, worsening neck pain, new limb weakness, or visual changes.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Left-sided headache since midday, associated with nausea and vomiting.

**HPI:** Per patient, the headache started at midday a few hours ago and came on suddenly. It is located on the left side and is throbbing in nature. A few minutes before the headache began, the patient noticed zigzag lines in the vision, followed by bilateral blurred vision. The pain is described as horrible and is making the patient feel very unwell. The headache is worse with movement, specifically leaning forward or moving the head or neck. Associated symptoms include photophobia (the patient is wearing sunglasses, with light hurting the eyes), nausea, and vomiting twice today. The patient reports a similar headache a few weeks ago that lasted a couple of days and was relieved with painkillers and bed rest. The patient expressed significant concern about the possibility of a brain tumor, noting a friend's mother recently died of a brain tumor.

**PMH:**
- Per patient, no prior migraine diagnosis.
- Per patient, no other significant medical history.

**Medications:**
- Microgynon, oral, regular (daily) — for contraception; on it for three months per patient.

**Allergies:** [not documented]

**Family History:**
- Mother: migraines (not diagnosed per patient).
- Mother: underactive thyroid.

**Social History:**
- Smoking: non-smoker.
- Alcohol: does not drink much alcohol.
- Occupation: works in the fashion industry; per patient, work is currently stressful with interpersonal pressures.
- Per patient, lives alone; does not do much exercise.

**ROS:**
- Constitutional: no fever; does not feel feverish.
- Neurological: no speech difficulties; no arm or leg weakness; no balance or coordination difficulties; no recent head injury or fall.
- Ophthalmological: photophobia; bilateral blurred vision and zigzag lines (visual aura) preceding headache.
- Gastrointestinal: nausea; vomited twice.
- Respiratory: no breathlessness.
- Dermatological: no skin rash.

## Objective
Formal exam not documented in this encounter.

## Assessment
Likely migraine with aura. The clinician noted the presentation is classical, with unilateral throbbing headache, nausea, vomiting, photophobia, and visual aura, and this is the second similar episode within the space of a month. Meningitis and brain cancer were considered and felt to be less likely based on the history; the clinician explicitly reassured the patient regarding these concerns. Microgynon (combined oral contraceptive pill) use was flagged by the clinician as requiring discussion in the context of migraine with aura.

## Plan
1. Keep a headache diary to help identify triggers.
2. Treat current episode with analgesia: paracetamol, co-codamol, and/or anti-inflammatories such as ibuprofen or naproxen.
3. Consider prophylactic migraine medication if headaches become more persistent — to be discussed at follow-up.
4. Discuss Microgynon use in the context of migraine with aura (clinician flagged this for discussion).
5. Follow-up appointment in approximately one week.
6. Safety-net: return immediately if symptoms do not improve in the next 2–3 days or worsen — specifically worsening headache not responding to medications, worsening neck pain, new limb weakness, or visual changes.
```
</details>

<details><summary>day1_consultation04 — src=audio, WER=20.4%, dur=615.48s</summary>

**L5 critique:** overall=high, safe_to_sign=false, issues=4, critical=0

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "Great-grandfather — eczema",
    "class": "a",
    "severity": "low",
    "transcript_span": "one of my great granddad had an eczema",
    "present_in": "both",
    "rationale": "The ASR transcript says 'great granddad' (male), which the SOAP faithfully renders as 'Great-grandfather'; the reference transcript confirms 'great grandads' — so the ASR was correct and this is fully supported, making this not a flag at all — however the ASR says 'great granddad' and the SOAP says 'Great-grandfather' which is a direct synonym with no clinical difference, so this is benign/stylistic."
  },
  {
    "invented_text": "sore throat was quite painful to swallow for a couple of days",
    "class": "b",
    "severity": "low",
    "transcript_span": "it was quite painful to swallow Okay. For one of the days",
    "present_in": "both",
    "rationale": "The ASR transcript says 'one of the days' but the SOAP generalises to 'a couple of days'; the reference transcript says 'one or two days', so this is a minor stylistic inference consistent with the reference, not a fabrication."
  },
  {
    "invented_text": "no shortness of breath at rest",
    "class": "b",
    "severity": "low",
    "transcript_span": "When when when I'm resting, it's okay",
    "present_in": "both",
    "rationale": "The patient said 'when I'm resting it's okay' in the context of breathing/feeling winded; the SOAP renders this as 'no shortness of breath at rest', which is a reasonable clinical paraphrase with no new clinical fact introduced."
  },
  {
    "invented_text": "photophobia",
    "class": "b",
    "severity": "low",
    "transcript_span": "Any difficulty with seeing bright lights? No. I don't think so.",
    "present_in": "both",
    "rationale": "The doctor asked about difficulty seeing bright lights and the patient denied it; the SOAP uses the clinical term 'photophobia' as a synonym, which is a benign stylistic/terminological inference introducing no new clinical fact."
  },
  {
    "invented_text": "myalgia/arthralgia",
    "class": "b",
    "severity": "low",
    "transcript_span": "any general muscle pain or aches, joint pain",
    "present_in": "both",
    "rationale": "The SOAP uses clinical terminology 'myalgia/arthralgia' to describe the patient-reported muscle and joint pain, which is a benign stylistic synonym introducing no new clinical fact."
  },
  {
    "invented_text": "clear rhinorrhoea with congestion",
    "class": "b",
    "severity": "low",
    "transcript_span": "it's it's clear...sort of getting my nose stuffed all the time",
    "present_in": "both",
    "rationale": "'Rhinorrhoea' is a clinical synonym for runny nose with clear discharge, a benign terminological inference with no new patient-specific fact introduced."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling under the weather for the past four days with sore throat, runny nose, and cough.

**HPI:** Per patient, the patient reports feeling unwell for the past four days. Symptoms began with a sore throat and runny nose and have progressed to a cough. The sore throat was quite painful to swallow for a couple of days but is now improving. The nasal discharge is clear with associated congestion that he finds difficult to clear. The cough started approximately yesterday, is dry, not very painful, and is present constantly throughout the day with no particular diurnal variation. He reports night sweats, fatigue, intermittent generalised headaches that come and go, and muscle and joint pains that began in the past couple of days. He had a fever at the onset which is now settling, helped by paracetamol and ibuprofen. He describes feeling winded/short of breath on exertion (and has avoided the gym for this reason) but no shortness of breath at rest and no chest pain. He notes decreased appetite and increased fluid intake. Per patient, the likely source was a colleague who was repeatedly sneezing at work, whose children may have caught something from kindergarten. He denies ear pain, ear blockage or discharge, visual disturbance, photophobia, nausea, vomiting, rash, and reports normal bowels and urine.

**PMH:** [not documented]

**Medications:**
- Paracetamol (dose/route/frequency not stated)
- Ibuprofen (dose/route/frequency not stated)

**Allergies:**
- No known drug allergies

**Family History:**
- Grandmother — type 2 diabetes (per patient, "I think it's type two")
- Great-grandfather — eczema

**Social History:**
- Smoking: Occasional only — cigars at company parties, not regular
- Alcohol: Occasional social drinker
- Occupation: Accountant
- Lives alone
- Per patient, currently a stressful period at work ("good kind of stress"); denies impact on mood

**ROS:**
- ENT: Sore throat with painful swallowing, now improving; clear nasal discharge with congestion.
- Respiratory: Dry cough started approximately yesterday, constant; shortness of breath on exertion; no chest pain.
- Constitutional: Fever at onset, now resolving; night sweats; fatigue; decreased appetite; increased fluid intake.
- Musculoskeletal: Muscle and joint pain started in the past couple of days.
- Neurological: Intermittent generalised headaches; no visual disturbance; no photophobia.
- Ears: No ear pain, blockage, or discharge.
- Gastrointestinal: No nausea, no vomiting; bowels normal.
- Genitourinary: Urine normal.
- Dermatology: No rashes.

## Objective
Formal exam not documented in this encounter.

## Assessment
Viral illness — viral upper respiratory tract infection or early signs of influenza, as discussed by the clinician. This is supported by the 4-day history of sore throat, clear rhinorrhoea with congestion, dry cough, initial fever now settling, night sweats, myalgia/arthralgia, fatigue, and headaches, with a plausible infectious contact. Severity/staging: [not documented].

## Plan
1. Reassurance provided: viral illness expected to last approximately 7–10 days and improve over time.
2. Advise rest; take a day or two off work if able.
3. Increase fluid intake and maintain hydration.
4. Continue regular paracetamol and ibuprofen.
5. Follow-up: return next week if not improving.
6. Safety-netting: return/call much sooner if high fever, worsening or laboured breathing, or chest pain develops.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling under the weather for the past four days with sore throat, runny nose, and cough.

**HPI:** Per patient, the patient reports feeling unwell for the past four days. Symptoms began with a sore throat and runny nose and have progressed to a cough. The sore throat was quite painful to swallow for a couple of days but is now improving. The nasal discharge is clear with associated congestion that he finds difficult to clear. The cough started approximately yesterday, is dry, not very painful, and is present constantly throughout the day with no particular diurnal variation. He reports night sweats, fatigue, intermittent generalised headaches that come and go, and muscle and joint pains that began in the past couple of days. He had a fever at the onset which is now settling, helped by paracetamol and ibuprofen. He describes feeling winded/short of breath on exertion (and has avoided the gym for this reason) but no shortness of breath at rest and no chest pain. He notes decreased appetite and increased fluid intake. Per patient, the likely source was a colleague who was repeatedly sneezing at work, whose children may have caught something from kindergarten. He denies ear pain, ear blockage or discharge, visual disturbance, photophobia, nausea, vomiting, rash, and reports normal bowels and urine.

**PMH:** [not documented]

**Medications:**
- Paracetamol (dose/route/frequency not stated)
- Ibuprofen (dose/route/frequency not stated)

**Allergies:**
- No known drug allergies

**Family History:**
- Grandmother — type 2 diabetes (per patient, "I think it's type two")
- Great-grandfather — eczema

**Social History:**
- Smoking: Occasional only — cigars at company parties, not regular
- Alcohol: Occasional social drinker
- Occupation: Accountant
- Lives alone
- Per patient, currently a stressful period at work ("good kind of stress"); denies impact on mood

**ROS:**
- ENT: Sore throat with painful swallowing, now improving; clear nasal discharge with congestion.
- Respiratory: Dry cough started approximately yesterday, constant; shortness of breath on exertion; no chest pain.
- Constitutional: Fever at onset, now resolving; night sweats; fatigue; decreased appetite; increased fluid intake.
- Musculoskeletal: Muscle and joint pain started in the past couple of days.
- Neurological: Intermittent generalised headaches; no visual disturbance; no photophobia.
- Ears: No ear pain, blockage, or discharge.
- Gastrointestinal: No nausea, no vomiting; bowels normal.
- Genitourinary: Urine normal.
- Dermatology: No rashes.

## Objective
Formal exam not documented in this encounter.

## Assessment
Viral illness — viral upper respiratory tract infection or early signs of influenza, as discussed by the clinician. This is supported by the 4-day history of sore throat, clear rhinorrhoea with congestion, dry cough, initial fever now settling, night sweats, myalgia/arthralgia, fatigue, and headaches, with a plausible infectious contact. Severity/staging: [not documented].

## Plan
1. Reassurance provided: viral illness expected to last approximately 7–10 days and improve over time.
2. Advise rest; take a day or two off work if able.
3. Increase fluid intake and maintain hydration.
4. Continue regular paracetamol and ibuprofen.
5. Follow-up: return next week if not improving.
6. Safety-netting: return/call much sooner if high fever, worsening or laboured breathing, or chest pain develops.
```
</details>

<details><summary>day2_consultation01 — src=audio, WER=17.8%, dur=329.16s</summary>

**L5 critique:** overall=high, safe_to_sign=true, issues=3, critical=0

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "self-resolving",
    "class": "c",
    "severity": "low",
    "transcript_span": "absent",
    "rationale": "The ASR transcript states the prior episode 'only lasted a couple of days' but never describes it as self-resolving; this causal/outcome characterisation is not supported by the transcript.",
    "present_in": "both"
  },
  {
    "invented_text": "not associated with the kind of nausea he would expect with severe vertigo",
    "class": "b",
    "severity": "low",
    "transcript_span": "it's not the kind of dizziness you get with nausea. Like Yeah. Not not proper room spinning or anything like that, but just just a little bit kind of off balance.",
    "rationale": "The patient said the dizziness is 'not the kind of dizziness you get with nausea' and 'not proper room spinning'; the SOAP-A elaboration 'he would expect with severe vertigo' adds interpretive clinical framing not stated in the transcript, but introduces no new clinical fact and is a benign stylistic inference.",
    "present_in": "both"
  },
  {
    "invented_text": "not associated with nausea per patient",
    "class": "b",
    "severity": "low",
    "transcript_span": "it's not the kind of dizziness you get with nausea",
    "rationale": "The patient said the dizziness is 'not the kind of dizziness you get with nausea', which the SOAP-B renders as 'not associated with nausea'; this is a reasonable clinical paraphrase with no new clinical fact introduced.",
    "present_in": "both"
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Difficulty hearing in the left ear, worsening over the past six weeks.

**HPI:** Per patient, Jack Smith reports approximately six weeks of difficulty hearing in the left ear only, with the right ear feeling unaffected. He describes his hearing as deteriorating. The symptoms are on and off, and certain triggers such as watching TV or listening to music set off a ringing in the left ear. He reports an associated occasional ringing (tinnitus) in the left ear on the one side. He has also had a few episodes of feeling a bit sick and a bit dizzy; the dizziness is described as mild and off-balance, not room-spinning and not associated with the kind of nausea he would expect with severe vertigo. Per patient, he had a similar episode approximately one year ago that lasted only a couple of days and was less significant than the current problem. He denies ear pain, discharge, itchiness, fever, chest pain, and palpitations. He reports he does not use cotton buds to clean his ears.

**PMH:**
- Per patient, previous episode of hearing difficulty approximately one year ago, lasting a couple of days, self-resolving

**Medications:** [not documented]

**Allergies:** [not documented]

**Family History:** [not documented]

**Social History:** [not documented]

**ROS:**
- ENT: Per patient, no ear pain, no ear discharge, no ear itchiness.
- Constitutional: Per patient, no fever (apart from reported dizziness and feeling sick).
- Cardiovascular: Per patient, no chest pain, no palpitations.
- Neurological/Vestibular: Per patient, mild dizziness — off balance, not room-spinning, not associated with severe nausea.

## Objective
Formal exam not documented in this encounter.

## Assessment
Left-sided hearing difficulty of six weeks' duration with associated tinnitus and intermittent mild dizziness. The clinician's primary consideration is to first exclude a simple physical cause such as impacted ear wax blocking the ear canal, which can lead to muffled hearing and is readily treatable. The ringing was identified as tinnitus, for which a specific cause is often not identifiable. If a physical blockage is excluded, the clinician noted the possibility of a problem inside the eardrum or the balance system within the ear.

## Plan
1. Book a face-to-face appointment at a clinic within the next four to five days for physical ear examination by a GP; this is not considered an emergency.
2. Message the admin team to slot the patient into a clinic appointment within that time frame for ear examination.
3. Paste a tinnitus patient information leaflet link into the appointment notes; patient advised to begin reading about tinnitus before the clinic visit.
4. Patient advised to book another appointment if any problems or issues arise before the scheduled clinic appointment.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Difficulty hearing in the left ear, worsening over the past six weeks.

**HPI:** Per patient, Jack Smith reports approximately six weeks of difficulty hearing in the left ear only, with the right ear feeling unaffected. He describes his hearing as deteriorating. The symptoms are on and off, and certain triggers such as watching TV or listening to music set off a ringing in the left ear. He reports an associated occasional ringing (tinnitus) in the left ear. He has also had a few episodes of feeling a bit sick and a bit dizzy; the dizziness is described as mild, off-balance, not room-spinning, and not associated with nausea per patient. Per patient, he had a similar episode approximately one year ago that lasted only a couple of days and was less significant than the current problem. He denies ear pain, discharge, itchiness, fever, chest pain, and palpitations. He reports he does not use cotton buds to clean his ears.

**PMH:**
- Per patient, previous episode of hearing difficulty approximately one year ago, lasting a couple of days, self-resolving

**Medications:** [not documented]

**Allergies:** [not documented]

**Family History:** [not documented]

**Social History:** [not documented]

**ROS:**
- ENT: Per patient, no ear pain, no ear discharge, no ear itchiness.
- Constitutional: Per patient, no fever (apart from reported dizziness and feeling sick).
- Cardiovascular: Per patient, no chest pain, no palpitations.
- Neurological/Vestibular: Per patient, mild dizziness — off balance, not room-spinning, not associated with severe nausea.

## Objective
Formal exam not documented in this encounter.

## Assessment
Left-sided hearing difficulty of six weeks' duration with associated tinnitus and intermittent mild dizziness. The clinician's primary consideration is to first exclude a simple physical cause such as impacted ear wax blocking the ear canal, which can lead to muffled hearing and is readily treatable. The ringing was identified as tinnitus, for which a specific cause is often not identifiable. If a physical blockage is excluded, the clinician noted the possibility of a problem inside the eardrum or the balance system within the ear.

## Plan
1. Book a face-to-face appointment at a clinic within the next four to five days for physical ear examination by a GP; this is not considered an emergency.
2. Message the admin team to slot the patient into a clinic appointment within that time frame for ear examination.
3. Paste a tinnitus patient information leaflet link into the appointment notes; patient advised to begin reading about tinnitus before the clinic visit.
4. Patient advised to book another appointment if any problems or issues arise before the scheduled clinic appointment.
```
</details>

<details><summary>day2_consultation05 — src=audio, WER=14.5%, dur=636.3s</summary>

**L5 critique:** overall=high, safe_to_sign=true, issues=5, critical=1

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "carotid surgery",
    "class": "b",
    "severity": "low",
    "transcript_span": "operation to the side of his neck to reduce the risk of stroke",
    "present_in": "both",
    "rationale": "The ASR transcript describes the father's procedure as 'operation to the side of his neck to reduce the risk of stroke'; labelling this 'carotid surgery' is a reasonable clinical inference/synonym but introduces a specific surgical term not explicitly stated in the ASR transcript."
  },
  {
    "invented_text": "right-sided pins and needles, arm and leg weakness, abnormal gait, oropharyngeal sensation",
    "class": "b",
    "severity": "low",
    "transcript_span": "pins and needles are in the hand, but I feel like my arm is getting weaker ... my leg feels weaker ... walking slightly differently ... something in my throat",
    "present_in": "l4_only",
    "rationale": "Grouping these symptoms under 'oropharyngeal sensation' as a listed neurological cluster is a reasonable clinical summary of what was stated, not an invented fact."
  },
  {
    "invented_text": "given the family history of stroke this requires urgent exclusion despite the patient's young age",
    "class": "b",
    "severity": "low",
    "transcript_span": "given that you've got a family history of stroke, even though you're quite young, I think it's something that we need to exclude",
    "present_in": "both",
    "rationale": "This is a faithful paraphrase of the doctor's stated reasoning; no new clinical fact is introduced."
  },
  {
    "invented_text": "episodes initially lasted three to four days",
    "class": "b",
    "severity": "low",
    "transcript_span": "it only lasts [unclear in recording] ... it's only for three days or three or four days",
    "present_in": "both",
    "rationale": "The ASR transcript mentions 'three days or three or four days' in the context of the gait abnormality duration; applying this as the episode duration is a reasonable inference from the available (partially unclear) transcript text."
  },
  {
    "invented_text": "Penicillin (reaction not documented)",
    "class": "b",
    "severity": "low",
    "transcript_span": "I'm allergic to penicillin only",
    "present_in": "both",
    "rationale": "The parenthetical '(reaction not documented)' is a benign organisational/documentation note, not an invented clinical fact."
  },
  {
    "invented_text": "Severity/staging: [not documented]",
    "class": "b",
    "severity": "low",
    "transcript_span": "absent",
    "present_in": "both",
    "rationale": "This is an explicit documentation placeholder, not an invented clinical fact, and carries no clinical risk."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Episodic "weird symptoms" over the past month, including tiredness, pins and needles/numbness in the right hand, arm weakness, and leg weakness.

**HPI:** Per patient, a 32-year-old male doctor working in plastic surgery presents with episodic neurological symptoms that began approximately a month and a half to two months ago. Per patient, episodes start with feeling very tired for a couple of days, then he returns to normal. He reports pins and needles/numbness in the right hand (always the right side), with associated weakness of the right arm, and weakness of the leg occurring at the same time as the arm symptoms. A colleague noted he was walking slightly differently than normal during these periods; per patient, the abnormal gait is present only during episodes, and he is otherwise fit and well. Per patient, episodes initially lasted three to four days and occurred about once a week to once a month, but have become more frequent and are now occurring a couple of times a day. Associated symptoms during episodes include general fatigue, weakness, and nausea. In the last couple of days, per patient, he has noticed difficulty holding his cup of coffee and that drinking coffee is slightly harder, and reports a sensation of "something in my throat" during episodes. He denies difficulty speaking and denies clear visual problems during episodes (notes he wears glasses). He is asymptomatic at the time of consultation. Context: Per patient, after his father had carotid surgery he started taking aspirin on his own initiative based on something he read online.

**PMH:**
- Per patient, no known illnesses
- Per patient, cholesterol, blood pressure, and diabetes were checked following his father's operation and reported as normal

**Medications:**
- Aspirin 75 mg once a day (self-initiated; per patient, started after father's operation and not on GP advice)

**Allergies:**
- Penicillin (reaction not documented)

**Family History:**
- Father: carotid neck operation to reduce risk of stroke

**Social History:**
- Occupation: Doctor, plastic surgery
- Smoking: Non-smoker
- Lives with his wife

**ROS:**
- Neurological: Per patient, episodic pins and needles/numbness in right hand, right arm weakness, leg weakness, abnormal gait noted by colleague.
- Constitutional: Per patient, fatigue and nausea during episodes.
- Gastrointestinal/Oropharyngeal: Per patient, sensation of something in throat during episodes; difficulty holding cup and drinking coffee.
- Speech: Per patient, no difficulty speaking.
- Ophthalmological: Per patient, no visual problems during episodes; wears glasses.

## Objective
Formal exam not documented in this encounter.

Test results mentioned:
- Prior cholesterol, blood pressure, and diabetes testing (following father's operation) — per patient, all reported as normal.

## Assessment
Primary clinical consideration is suspected TIA (transient ischaemic attack)/mini stroke. Per the doctor, the episodic focal neurological symptoms (right-sided pins and needles, arm and leg weakness, abnormal gait, oropharyngeal sensation) raise concern for mini strokes/TIAs, and given the family history of stroke this requires urgent exclusion despite the patient's young age. The doctor stated the presumptive working diagnosis is mini stroke or TIA, noting that a prolonged event would raise concern for evolving stroke, which would constitute an emergency.

Severity/staging: [not documented]

## Plan
1. Send urgent referral to the TIA/mini stroke clinic now; patient advised he will usually be called in within one to two days (expected by Thursday/Friday).
2. TIA clinic to perform carotid artery ultrasound and possibly a brain scan to assess for signs of a bleed.
3. Safety-netting: advised patient to attend A&E immediately if symptoms return and persist, given risk of an evolving/prolonged stroke.
4. Advised patient to contact the practice by phone if symptoms recur before the clinic appointment; can be assessed and given guidance over the phone.
5. PALS/hospital contact number to be added to the consultation notes so the patient can chase the appointment; patient advised he may ring today or tomorrow morning to confirm he is in the system.
6. Advised patient to re-contact the practice if there is any delay in being called or if the appointment cannot be made.
7. Discussed self-initiated aspirin use; patient has not previously informed a GP and no GP has previously discussed the risks/appropriateness of aspirin with him — to be reviewed.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Episodic "weird symptoms" over the past month, including tiredness, pins and needles/numbness in the right hand, arm weakness, and leg weakness.

**HPI:** Per patient, a 32-year-old male doctor working in plastic surgery presents with episodic neurological symptoms that began approximately a month and a half to two months ago. Per patient, episodes start with feeling very tired for a couple of days, then he returns to normal. He reports pins and needles/numbness in the right hand (always the right side), with associated weakness of the right arm, and weakness of the leg occurring at the same time as the arm symptoms. A colleague noted he was walking slightly differently than normal during these periods; per patient, the abnormal gait is present only during episodes, and he is otherwise fit and well. Per patient, episodes initially lasted three to four days and occurred about once a week to once a month, but have become more frequent and are now occurring a couple of times a day. Associated symptoms during episodes include general fatigue, weakness, and nausea. In the last couple of days, per patient, he has noticed difficulty holding his cup of coffee and that drinking coffee is slightly harder, and reports a sensation of "something in my throat" during episodes. He denies difficulty speaking and denies clear visual problems during episodes (notes he wears glasses). He is asymptomatic at the time of consultation. Context: Per patient, after his father had carotid surgery he started taking aspirin on his own initiative based on something he read online.

**PMH:**
- Per patient, no known illnesses
- Per patient, cholesterol, blood pressure, and diabetes were checked following his father's operation and reported as normal

**Medications:**
- Aspirin 75 mg once a day (self-initiated; per patient, started after father's operation and not on GP advice)

**Allergies:**
- Penicillin (reaction not documented)

**Family History:**
- Father: carotid neck operation to reduce risk of stroke

**Social History:**
- Occupation: Doctor, plastic surgery
- Smoking: Non-smoker
- Lives with his wife

**ROS:**
- Neurological: Per patient, episodic pins and needles/numbness in right hand, right arm weakness, leg weakness, abnormal gait noted by colleague.
- Constitutional: Per patient, fatigue and nausea during episodes.
- Gastrointestinal/Oropharyngeal: Per patient, sensation of something in throat during episodes; difficulty holding cup and drinking coffee.
- Speech: Per patient, no difficulty speaking.
- Ophthalmological: Per patient, no visual problems during episodes; wears glasses.

## Objective
Formal exam not documented in this encounter.

Test results mentioned:
- Prior cholesterol, blood pressure, and diabetes testing (following father's operation) — per patient, all reported as normal.

## Assessment
Primary clinical consideration is suspected TIA (transient ischaemic attack)/mini stroke. Per the doctor, the following patient-reported symptoms raise concern for mini strokes/TIAs: right-sided pins and needles, right arm weakness, leg weakness, abnormal gait (noted by a colleague during episodes), and the sensation of something in the throat during episodes. No formal examination findings are documented for this encounter. Given the family history of stroke, urgent exclusion is indicated despite the patient's young age. The doctor stated the presumptive working diagnosis is mini stroke or TIA; a prolonged event would raise concern for evolving stroke, which would constitute an emergency and would require immediate attendance at A&E.

Severity/staging: [not documented]

## Plan
1. Send urgent referral to the TIA/mini stroke clinic now; patient advised he will usually be called in within one to two days (expected by Thursday/Friday).
2. TIA clinic to perform carotid artery ultrasound and possibly a brain scan to assess for signs of a bleed.
3. Safety-netting: advised patient to attend A&E immediately if symptoms return and persist.
4. Advised patient to contact the practice by phone if symptoms recur before the clinic appointment; can be assessed and given guidance over the phone.
5. PALS/hospital contact number to be added to the consultation notes so the patient can chase the appointment; patient advised he may ring today or tomorrow morning to confirm he is in the system.
6. Advised patient to re-contact the practice if there is any delay in being called or if the appointment cannot be made.
7. Discussed self-initiated aspirin use; patient has not previously informed a GP and no GP has previously discussed the risks/appropriateness of aspirin with him — to be reviewed.
```
</details>

<details><summary>day3_consultation01 — src=audio, WER=15.6%, dur=510.06s</summary>

**L5 critique:** overall=low, safe_to_sign=false, issues=7, critical=3

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "drinks socially",
    "class": "b",
    "severity": "low",
    "transcript_span": "I remember that was quite drunk, to be honest",
    "present_in": "both",
    "rationale": "The ASR transcript only documents one occasion of notable alcohol use; 'drinks socially' is an inferred pattern not directly stated by the patient."
  },
  {
    "invented_text": "999",
    "class": "a",
    "severity": "low",
    "transcript_span": "99999",
    "present_in": "both",
    "rationale": "The ASR transcript contains '99999' (a recognition error), while the reference confirms the correct UK emergency number is 999; the SOAP correctly writes 999, faithfully reflecting what was said but correcting an ASR recognition error."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Lip swelling after eating prawn soup.

**HPI:** Per patient, at approximately 7:00 PM, just after work, she ate a prawn soup at a restaurant she frequents with friends (where she usually orders a vegetarian soup). Shortly afterward she noted her lips feeling "weird," starting in the left corner. She reports a swelling on her upper lip that has been getting bigger over approximately half an hour, which she describes as feeling like it is "really pumping" and worsening. During the encounter she reports she "can't breathe that well right now" and that breathing "generally feels a little difficult"; when asked, she was uncertain whether her chest specifically felt tight. She also reports feeling dizzy and noted the swelling getting worse during the call. Per patient, she recalls a similar episode approximately one year ago after eating at a Chinese restaurant (a curry), when she was reportedly quite drunk and woke the next morning swollen with difficulty breathing.

**PMH:**
- Asthma (per patient)
- Per patient, prior episode of lip swelling and difficulty breathing approximately one year ago after eating out
- Per patient, severe allergic reaction requiring hospitalisation as a child (around age 6, per patient's recollection of what her mother told her)

**Medications:**
- Salbutamol inhaler, regular use (per patient)
- Antihistamine, unspecified — patient unsure which, taken sometimes for peanut allergy [clarify with patient]

**Allergies:**
- Peanuts — per patient; reports taking antihistamines for this
- Prawns (suspected) — associated with current presentation of lip swelling, difficulty breathing, and dizziness

**Family History:** [not documented]

**Social History:**
- Alcohol: Per patient, drinks socially; was notably drunk on a prior occasion approximately one year ago when a similar reaction occurred.
- Occupation: Per patient, employed (presentation occurred just after work).

**ROS:**
- Dermatologic/Oral: Per patient, upper lip swelling, starting in left corner, progressively worsening.
- Respiratory: Per patient, difficulty breathing.
- Respiratory/Throat: Possible throat tightening (patient queried about throat closing up).
- Cardiovascular/Chest: Per patient, possible chest tightness, uncertain.
- Neurological: Per patient, dizziness.

## Objective
Formal exam not documented in this encounter. (Telephone/remote consultation; no vital signs or examination findings recorded.)

## Assessment
Suspected anaphylactic reaction. The clinician stated this could be an anaphylactic reaction given the history of progressive lip swelling, difficulty breathing, and dizziness developing after ingestion of prawn soup, in the context of prior allergic reactions and a childhood severe allergic reaction reportedly requiring hospitalisation. Suspected trigger is prawns. Severity/staging beyond "suspected anaphylactic reaction" was [not documented].

## Plan
1. Call emergency ambulance (999) immediately for suspected anaphylaxis; patient instructed to remain on the line and stay with the person present.
2. Mother instructed to call 999 and report a suspected anaphylactic reaction requiring immediate attendance.
3. Take antihistamines immediately in the interim while awaiting the ambulance (household antihistamines confirmed available).
4. Patient to call back after hospital discharge to arrange follow-up regarding "your injections" — clarify and arrange prescription as appropriate.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Lip swelling after eating prawn soup.

**HPI:** Per patient, at approximately 7:00 PM, just after work, she ate a prawn soup at a restaurant she frequents with friends (where she usually orders a vegetarian soup). Shortly afterward she noted her lips feeling "weird," starting in the left corner. She reports a swelling on her upper lip that has been getting bigger over approximately half an hour, which she describes as feeling like it is "really pumping" and worsening. During the encounter she reports she "can't breathe that well right now" and that breathing "generally feels a little difficult"; when asked, she was uncertain whether her chest specifically felt tight. She also reports feeling dizzy and noted the swelling getting worse during the call. Per patient, she recalls a similar episode approximately one year ago after eating at a Chinese restaurant (a curry), when she was reportedly quite drunk and woke the next morning swollen with difficulty breathing.

**PMH:**
- Asthma (per patient)
- Per patient, prior episode of lip swelling and difficulty breathing approximately one year ago after eating out
- Per patient, severe allergic reaction requiring hospitalisation as a child (around age 6, per patient's recollection of what her mother told her)

**Medications:**
- Salbutamol inhaler, regular use (per patient)
- Antihistamine, unspecified — patient unsure which, taken sometimes for peanut allergy [clarify with patient]

**Allergies:**
- Peanuts — per patient; reports taking antihistamines for this
- Prawns (suspected) — associated with current presentation of lip swelling, difficulty breathing, and dizziness

**Family History:** [not documented]

**Social History:**
- Alcohol: Per patient, drinks socially; was notably drunk on a prior occasion approximately one year ago when a similar reaction occurred.
- Occupation: Per patient, employed (presentation occurred just after work).

**ROS:**
- Dermatologic/Oral: Per patient, upper lip swelling, starting in left corner, progressively worsening.
- Respiratory: Per patient, difficulty breathing.
- Respiratory/Throat: Possible throat tightening (patient queried about throat closing up).
- Cardiovascular/Chest: Per patient, possible chest tightness, uncertain.
- Neurological: Per patient, dizziness.

## Objective
Formal exam not documented in this encounter. (Telephone/remote consultation; no vital signs or examination findings recorded.)

## Assessment
Suspected anaphylactic reaction. The clinician stated this could be an anaphylactic reaction given the history of progressive lip swelling, difficulty breathing, and dizziness developing after ingestion of prawn soup, in the context of prior allergic reactions and a childhood severe allergic reaction reportedly requiring hospitalisation. Suspected trigger is prawns. Severity/staging beyond "suspected anaphylactic reaction" was [not documented].

## Plan
1. Call emergency ambulance (999) immediately for suspected anaphylaxis; patient instructed to remain on the line and stay with the person present.
2. Mother instructed to call 999 and report a suspected anaphylactic reaction requiring immediate attendance.
3. Take antihistamines immediately in the interim while awaiting the ambulance (household antihistamines confirmed available).
4. Patient to call back after hospital discharge to arrange follow-up regarding "your injections" — clarify and arrange prescription as appropriate.
```
</details>

<details><summary>day3_consultation05 — src=audio, WER=13.8%, dur=413.58s</summary>

**L5 critique:** overall=low, safe_to_sign=false, issues=6, critical=2

**Judge flags (both SOAPs, deduplicated):**
```json
[
  {
    "invented_text": "tinnitus",
    "class": "b",
    "severity": "low",
    "transcript_span": "ears buzzing a bit / buzzy noise in my ears",
    "present_in": "both",
    "rationale": "Tinnitus is the standard clinical term for the ear-buzzing symptom the patient described; no new patient-specific fact is introduced."
  },
  {
    "invented_text": "vertigo",
    "class": "b",
    "severity": "low",
    "transcript_span": "room is sort of spinning / feeling dizzy",
    "present_in": "both",
    "rationale": "Vertigo is the accepted clinical synonym for the room-spinning/dizziness the patient described; no new patient-specific fact is introduced."
  },
  {
    "invented_text": "exclude other causes",
    "class": "b",
    "severity": "low",
    "transcript_span": "I would still like you to be seen by one of our doctors to take a look inside your ears to just make sure",
    "present_in": "both",
    "rationale": "The phrase 'exclude other causes' is a reasonable clinical paraphrase of 'just make sure'; no new clinical fact is invented."
  }
]
```
**Post-L4 SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling dizzy with the room spinning, unsteady gait, and ear buzzing.

**HPI:** Per patient, a 1980-born woman reports symptoms began approximately two hours prior to the consultation while she was making her husband breakfast, when she suddenly felt fuzzy, dizzy, and shaky. She describes the room as spinning and reports she can walk but not in a straight line, attributing the unsteadiness to the sensation of the room moving rather than limb weakness. She notes buzzing in her ears but states she can otherwise hear everything. She reports associated nausea and feeling very sick, but has not vomited. Symptoms have been continuous for the past two hours. Per patient, she had a similar episode approximately one month ago that lasted only about five to ten minutes and settled quickly. She denies any recent viral illness, cold, or cough, denies ear pain or discharge, and does not think she has a temperature. She reports no weakness of her arms or legs.

**PMH:**
- Premature ovarian failure

**Medications:**
- HRT (hormone replacement therapy)
- [unclear in recording] — one tablet three times a day (newly prescribed this visit; see Plan) [clarify with patient]

**Allergies:**
- No known allergies

**Family History:** [not documented]

**Social History:** [not documented]

**ROS:**
- Neurological: No weakness of arms or legs; reports feeling unstable.
- ENT: Buzzing in ears; no ear pain; no ear discharge; reports hearing is intact.
- Gastrointestinal: Nausea present; no vomiting.
- Constitutional: No fever (per patient, "I don't think so").
- Infectious: No recent viral illness, cold, or cough.

## Objective
Formal exam not documented in this encounter. (Blood pressure measurement, in-person ear examination, and gait assessment were planned but not performed during this consultation.)

## Assessment
Per the clinician, the most likely diagnosis is labyrinthitis, described as inflammation of the middle ear with imbalance of the crystals causing the vertigo and unsteady gait. Supporting features include the spinning sensation, tinnitus, nausea, and unsteady gait without limb weakness. In-person examination was recommended to confirm and exclude other causes. No differential diagnoses were explicitly discussed. Severity/staging [not documented].

## Plan
1. Prescribe [unclear in recording] — one tablet three times a day for approximately ten days; prescription to be sent to Lloyd Pharmacy. Clarify medication name with prescriber/patient.
2. Patient advised the tablets can be taken with or without food.
3. Arrange in-person appointment with a doctor for ear examination, blood pressure measurement, and gait assessment; patient advised to call support to book the appointment.
4. Safety-net advice: attend A&E if she develops weakness of the legs or arms, a sudden headache, or becomes violently sick; otherwise await the doctor appointment.
```
**FINAL (post-L6) SOAP:**
```markdown
## Subjective
**Chief Complaint:** Feeling dizzy with the room spinning, unsteady gait, and ear buzzing.

**HPI:** Per patient, a 1980-born woman reports symptoms began approximately two hours prior to the consultation while she was making her husband breakfast, when she suddenly felt fuzzy, dizzy, and shaky. She describes the room as spinning and reports she can walk but not in a straight line, attributing the unsteadiness to the sensation of the room moving rather than limb weakness. She notes buzzing in her ears but states she can otherwise hear everything. She reports associated nausea and feeling very sick, but has not vomited. Symptoms have been continuous for the past two hours. Per patient, she had a similar episode approximately one month ago that lasted only about five to ten minutes and settled quickly. She denies any recent viral illness, cold, or cough, denies ear pain or discharge, and does not think she has a temperature. She reports no weakness of her arms or legs.

**PMH:**
- Premature ovarian failure

**Medications:**
- HRT (hormone replacement therapy)
- [unclear in recording] — one tablet three times a day (newly prescribed this visit; see Plan) [clarify with patient]

**Allergies:**
- No known allergies

**Family History:** [not documented]

**Social History:** [not documented]

**ROS:**
- Neurological: No weakness of arms or legs; reports feeling unstable.
- ENT: Buzzing in ears; no ear pain; no ear discharge; reports hearing is intact.
- Gastrointestinal: Nausea present; no vomiting.
- Constitutional: No fever (per patient, "I don't think so").
- Infectious: No recent viral illness, cold, or cough.

## Objective
Formal exam not documented in this encounter. (Blood pressure measurement, in-person ear examination, and gait assessment were planned but not performed during this consultation.)

## Assessment
Per the clinician, the most likely diagnosis is labyrinthitis, described as inflammation of the middle ear with imbalance of the crystals causing the vertigo and unsteady gait. Supporting features include the spinning sensation, tinnitus, nausea, and unsteady gait without limb weakness. In-person examination was recommended to confirm and exclude other causes. No differential diagnoses were explicitly discussed. Severity/staging [not documented].

## Plan
1. Prescribe [unclear in recording] — one tablet three times a day for approximately ten days; prescription to be sent to Lloyd Pharmacy. Clarify medication name with prescriber/patient.
2. Patient advised the tablets can be taken with or without food.
3. Arrange in-person appointment with a doctor for ear examination, blood pressure measurement, and gait assessment; patient advised to call support to book the appointment.
4. Safety-net advice: attend A&E if she develops weakness of the legs or arms, a sudden headache, or becomes violently sick; otherwise await the doctor appointment.
```
</details>
