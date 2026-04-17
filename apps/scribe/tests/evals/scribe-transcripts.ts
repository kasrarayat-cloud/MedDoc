// ============================================================================
// Golden transcripts for eval:scribe
// ----------------------------------------------------------------------------
// Each case is a pre-cleaned, diarized transcript (so we skip Whisper and
// the Pass-1 cleanup in the eval — the scoring focuses on SOAP generation
// quality). Expanding the set is a non-engineer task: add a new entry and
// re-run `npm run eval:scribe`.
// ============================================================================

export interface ScribeEvalCase {
  id: string;
  description: string;
  /** Specialty template slug to look up from ScribeSpecialtyTemplate. */
  specialtySlug: string;
  /** Pre-diarized transcript — "CLINICIAN: …\nPATIENT: …". */
  transcript: string;
  /** Keys we expect to see populated in the SOAP subjective/plan sections. */
  expectedSubjectiveKeys: string[];
  expectedPlanKeys: string[];
  /** At least one assessment item must match one of these ICD-10 codes. */
  expectedIcd10Candidates: string[];
  /**
   * M4 extensions (all optional). Added now so cases carry the expectation
   * metadata needed when the eval harness grows to check coding / rx /
   * referrals output tabs directly (M5+ full-bundle evals). Unused today
   * but locked in the test-data contract.
   */
  /** At least one CPT code (E/M or otherwise) must appear. */
  expectedCptCodes?: string[];
  /** At least one Rx draft must mention one of these drug names (case-insensitive substring). */
  expectedRxDrugs?: string[];
  /** If a referral is made, its specialty field must match this string. */
  expectedReferralSpecialty?: string;
}

export const SCRIBE_EVAL_CASES: ScribeEvalCase[] = [
  {
    id: 'primary-care-common-cold',
    description: '4-day URI, mild — typical brief primary-care visit',
    specialtySlug: 'primary-care',
    transcript: `
CLINICIAN: Hi, Jane, come on in. What brings you in today?
PATIENT: Hi. I've had this cough and runny nose for about four days now. It's worse at night.
CLINICIAN: Any fevers?
PATIENT: No fevers that I've noticed.
CLINICIAN: Shortness of breath, wheezing, chest pain?
PATIENT: No, just kind of a scratchy throat and the cough.
CLINICIAN: Any sick contacts at home or at work?
PATIENT: Yeah, my son had the same thing last week.
CLINICIAN: Let me take a look. Vitals look good — temp is 37.0, blood pressure 122 over 78, heart rate 82, saturation 98 percent.
CLINICIAN: Throat is a little red but no exudate. Ears are clear. Neck is soft, no swollen glands.
CLINICIAN: This looks like a viral upper respiratory infection. I'd hold off on antibiotics — they wouldn't help a virus anyway. Rest, fluids, and over-the-counter decongestants should cover it.
PATIENT: Okay, that sounds good.
CLINICIAN: If you spike a fever over 101, or start getting short of breath, or this isn't better in seven to ten days, come back in or go urgent care.
PATIENT: Got it. Thanks, doc.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['medications', 'counseling'],
    expectedIcd10Candidates: ['J06.9', 'J00', 'J06'],
    expectedCptCodes: ['99213', '99214', '99212'],
    expectedRxDrugs: [],
  },
  {
    id: 'primary-care-htn-refill',
    description: 'Short med-refill visit — established HTN',
    specialtySlug: 'primary-care',
    transcript: `
CLINICIAN: Hi Mr. Rivera, good to see you. You're due for your lisinopril refill, right?
PATIENT: Yeah, I ran out yesterday. Sorry I didn't call sooner.
CLINICIAN: No problem. How have you been feeling? Any dizziness, headaches, swelling?
PATIENT: No, I feel fine on it. I've been taking it every morning like you said.
CLINICIAN: Great. Blood pressure today is 128 over 82. Heart rate 74. That's right where we want it.
CLINICIAN: Any other concerns today?
PATIENT: No, that's it.
CLINICIAN: I'll send in three months of lisinopril 20 milligrams daily. Let's get another BP check in six weeks and labs before your next annual.
PATIENT: Sounds good. Thanks.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint'],
    expectedPlanKeys: ['medications', 'follow_up'],
    expectedIcd10Candidates: ['I10'],
    expectedCptCodes: ['99213', '99212', '99214'],
    expectedRxDrugs: ['lisinopril'],
  },
  {
    id: 'primary-care-annual-brief',
    description: 'Compressed annual exam — covers most required elements',
    specialtySlug: 'primary-care',
    transcript: `
CLINICIAN: Good morning, Ms. Chen. This is your annual check — no specific complaints today, right?
PATIENT: No, I feel pretty good. Just here for the yearly.
CLINICIAN: Any changes in your health since last year — new symptoms, medications, hospitalizations?
PATIENT: No. Still on the metformin for the diabetes and the atorvastatin.
CLINICIAN: How's your blood sugar been? Are you checking it?
PATIENT: Fasting numbers are usually 110 to 125. Haven't been great about the afternoon ones.
CLINICIAN: Any vision changes, foot numbness, tingling?
PATIENT: No numbness. My eyes are fine — I saw the eye doctor six months ago.
CLINICIAN: Alright, let's examine. Vitals — BP 124 over 78, HR 70, temp 36.8, BMI 26.
CLINICIAN: General — you look well, in no distress.
CLINICIAN: Heart — regular rate and rhythm, no murmurs.
CLINICIAN: Lungs — clear to auscultation bilaterally.
CLINICIAN: Abdomen — soft, no tenderness, no masses.
CLINICIAN: Feet exam — skin intact, good pulses, sensation preserved to monofilament.
CLINICIAN: Plan — I'll order a lipid panel, A1c, CMP, and urine microalbumin. Continue metformin 1000 twice daily and atorvastatin 20. I'd like to see your A1c come down a point this year — let's add 15 minutes of walking daily. Follow-up in three months with the labs.
PATIENT: Okay, I'll do the walks.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['diagnostics', 'medications', 'follow_up'],
    expectedIcd10Candidates: ['E11.9', 'E78.5', 'Z00.00'],
    expectedCptCodes: ['99214', '99213', '99395', '99396'],
    expectedRxDrugs: ['metformin', 'atorvastatin'],
  },

  // ──────────────────────────────────────────────────────────────────
  // M5 — one synthetic case per new specialty. Transcripts are short
  // and engineer-authored; use them as smoke tests for the templates,
  // NOT as clinical gold standards. Expand + curate with a clinical
  // advisor before relying on them in CI gates beyond schema/grounding.
  // ──────────────────────────────────────────────────────────────────
  {
    id: 'internal-medicine-multiproblem',
    description: 'Established multi-problem IM visit — HTN + DM2 + HLD, meds adjustment',
    specialtySlug: 'internal-medicine',
    transcript: `
CLINICIAN: Good to see you, Mr. Alvarez. We're checking in on your blood pressure, diabetes, and cholesterol today.
PATIENT: Yeah. The pressure's been up a little on the home cuff — around 145 over 90 most mornings.
CLINICIAN: Any headaches, chest pain, shortness of breath?
PATIENT: No, just feel fine otherwise.
CLINICIAN: How's the metformin going? Any stomach issues?
PATIENT: No, I'm tolerating it. My sugars are 130 to 150 fasting, still.
CLINICIAN: And the atorvastatin?
PATIENT: Taking it every night. No muscle aches.
CLINICIAN: Let me examine. BP today 148 over 92, HR 76. General — alert, well-appearing. Heart — regular rate, no murmurs. Lungs clear. Abdomen soft, non-tender. Extremities no edema, good pulses.
CLINICIAN: Alright — your pressure's creeping up. Let's increase the lisinopril to 20 milligrams daily. Continue metformin 1000 twice daily and atorvastatin 40 at bedtime. I want a basic metabolic panel and A1c today, and I'll see you in six weeks for a pressure check.
PATIENT: Sounds good.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['diagnostics', 'medications', 'follow_up'],
    expectedIcd10Candidates: ['I10', 'E11.9', 'E78.5'],
    expectedCptCodes: ['99214', '99213', '99215'],
    expectedRxDrugs: ['lisinopril', 'metformin', 'atorvastatin'],
  },
  {
    id: 'cardiology-afib-followup',
    description: 'Established cardiology visit — afib on apixaban, rate-controlled on metoprolol',
    specialtySlug: 'cardiology',
    transcript: `
CLINICIAN: Hi Mrs. Park. Here to check in on your atrial fibrillation today. How have you been?
PATIENT: I've been okay. No palpitations lately. The apixaban hasn't caused any bleeding issues.
CLINICIAN: Any chest pain, shortness of breath, or dizziness?
PATIENT: No, none of that.
CLINICIAN: And you're still on the metoprolol, 50 twice a day?
PATIENT: Yes, every day.
CLINICIAN: Let me examine you. BP 124 over 76. Heart rate 72 — irregularly irregular, consistent with afib, no murmurs. Lungs are clear. No JVD. Extremities: no peripheral edema. Pulses 2+ and equal.
CLINICIAN: ECG today shows atrial fibrillation with controlled ventricular response at 74. Your CHA2DS2-VASc score is 3, so we'll continue the apixaban 5 milligrams twice daily. Continue the metoprolol succinate 50 milligrams twice daily. Let's get a follow-up echo in six months and see you back in three.
PATIENT: Thank you.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['medications', 'diagnostics', 'follow_up'],
    expectedIcd10Candidates: ['I48.91'],
    expectedCptCodes: ['99213', '99214', '93000'],
    expectedRxDrugs: ['apixaban', 'metoprolol'],
  },
  {
    id: 'dermatology-actinic-keratosis',
    description: 'Dermatology — multiple actinic keratoses, cryotherapy in clinic',
    specialtySlug: 'dermatology',
    transcript: `
CLINICIAN: Hi Mr. Kane, you're here for some rough spots on your face and scalp.
PATIENT: Yeah. My wife has been after me to get them checked. A few are kind of scaly.
CLINICIAN: Any bleeding, rapid growth, change in color?
PATIENT: No, just rough patches.
CLINICIAN: Let me take a look. On the forehead I see three pink, scaly macules, each about four to six millimeters, consistent with actinic keratosis. On the right temple there's one similar lesion, about five millimeters. On the scalp vertex, two more scaly papules, four millimeters each. No suspicious pigmented lesions. No palpable lymphadenopathy.
CLINICIAN: These are actinic keratoses — pre-cancerous sun damage. I'm going to treat them with cryotherapy today. That's six lesions total. I'll also recommend you start using daily SPF 30 or higher sunscreen and consider fluorouracil cream for field treatment. Let's follow up in three months for a full skin check.
PATIENT: Okay.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['procedures_in_clinic', 'counseling', 'follow_up'],
    expectedIcd10Candidates: ['L57.0'],
    expectedCptCodes: ['17000', '17003'],
    expectedRxDrugs: [],
  },
  {
    id: 'psychiatry-safety-positive',
    description: 'Psychiatry follow-up with SI disclosure — safety clause must fire',
    specialtySlug: 'psychiatry',
    transcript: `
CLINICIAN: Hi Sarah, how have you been doing since our last visit?
PATIENT: Honestly, not good. The sertraline hasn't helped much. I've been having thoughts of not wanting to be here anymore.
CLINICIAN: I'm really glad you're telling me. Have you had any thoughts about how you might hurt yourself?
PATIENT: I've thought about my medication bottles. I haven't done anything. But I keep thinking about it.
CLINICIAN: Thank you for being honest. That's a very important thing to share. Are you safe right now, sitting here with me?
PATIENT: Yes. I don't want to act on it. I'm scared.
CLINICIAN: Okay. Let's think about this together. First, I want to give the medication to your partner to hold for the next week. Second, I want to increase the sertraline to 150 milligrams and add a follow-up in three days. Can you commit to calling 988 or going to the ER if the thoughts get worse?
PATIENT: Yes, I can do that.
CLINICIAN: Mental status today — alert, tearful, mood "not good," affect constricted and congruent, thought process linear, thought content notable for passive and active suicidal ideation with vague plan but no intent, no psychosis, cognition intact, insight and judgment fair. Current safety is contracted with means restriction and close follow-up.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['medications', 'safety_plan', 'follow_up'],
    // Generator may pick a more specific MDD code (F33.0 mild, F33.1
    // moderate, F33.2 severe, etc.) over the unspecified F33.9 when the
    // transcript supports severity — accept any MDD code.
    expectedIcd10Candidates: ['F32.9', 'F33.9', 'F32.0', 'F32.1', 'F32.2', 'F33.0', 'F33.1', 'F33.2'],
    expectedCptCodes: ['99214', '99215', '90833', '90836'],
    expectedRxDrugs: ['sertraline'],
  },
  {
    id: 'pediatrics-otitis-media',
    description: 'Pediatrics — acute otitis media in a toddler, amoxicillin Rx',
    specialtySlug: 'pediatrics',
    transcript: `
CLINICIAN: Hi — mom, what's going on with Emma today?
PATIENT: She's been fussy for two days, pulling at her right ear, and had a fever of 38.8 last night. She had a runny nose before that.
CLINICIAN: Any vomiting, diarrhea, cough, trouble breathing?
PATIENT: No vomiting, no diarrhea. A little cough but that's it.
CLINICIAN: Any trouble eating or drinking?
PATIENT: She's drinking okay but not eating much.
CLINICIAN: Let me check her. Weight today is 12.4 kilos. Temperature 37.8 right now. Alert and interactive. Right tympanic membrane is erythematous and bulging with loss of landmarks. Left tympanic membrane is normal. Nose has clear rhinorrhea. Throat mildly injected, no exudate. Neck supple. Heart regular, lungs clear. Abdomen soft. Skin intact.
CLINICIAN: She has right acute otitis media. I'll start amoxicillin 90 milligrams per kilo per day divided twice daily — that's about 560 milligrams twice daily for ten days. Continue acetaminophen for fever and pain as needed. Call if she's not better in 48 to 72 hours, or sooner if the fever spikes above 39, or she becomes lethargic.
PATIENT: Got it.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['medications', 'anticipatory_guidance', 'follow_up'],
    // Generator may pick a more specific AOM code (suppurative with/without
    // rupture, ear-specific) over the unspecified H66.90. Accept any H66.x.
    expectedIcd10Candidates: [
      'H66.90', 'H66.91', 'H66.001', 'H66.002', 'H66.003', 'H66.004',
      'H66.011', 'H66.012', 'H66.013', 'H66.019',
    ],
    expectedCptCodes: ['99213', '99214'],
    expectedRxDrugs: ['amoxicillin'],
  },
  {
    id: 'orthopedics-knee-pain',
    description: 'Orthopedics — right knee OA, corticosteroid injection',
    specialtySlug: 'orthopedics',
    transcript: `
CLINICIAN: Hi Mr. Davies. Back again for the right knee?
PATIENT: Yes, it's been aching pretty badly for the last two months. Walking up stairs is the worst.
CLINICIAN: Any swelling, locking, giving way?
PATIENT: Some swelling after I'm on my feet all day. No locking. Hasn't given way.
CLINICIAN: Let me examine. Right knee: mild effusion, no warmth, no erythema. Tenderness along the medial joint line. Range of motion zero to one hundred twenty degrees, limited by pain at end flexion. Neurovascular exam — sensation intact, motor five out of five, dorsalis pedis and posterior tibial pulses two plus, capillary refill brisk. Lachman test negative. McMurray negative on the medial side, mildly positive-feeling on the lateral, inconclusive.
CLINICIAN: X-rays from last visit showed medial joint-space narrowing, consistent with primary osteoarthritis of the right knee. I'd like to do an intra-articular corticosteroid injection today — triamcinolone 40 milligrams with 5 milliliters of lidocaine one percent. We'll pair that with meloxicam 15 milligrams daily and start physical therapy. Follow up in six weeks.
PATIENT: Sounds good.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'hpi'],
    expectedPlanKeys: ['procedures_in_clinic', 'medications', 'physical_therapy'],
    expectedIcd10Candidates: ['M17.11', 'M25.561'],
    expectedCptCodes: ['20610', '99213', '99214'],
    expectedRxDrugs: ['meloxicam', 'triamcinolone'],
  },
  {
    id: 'ob-gyn-iud-insertion',
    description: 'OB/GYN — scheduled IUD insertion, contraception counseling',
    specialtySlug: 'ob-gyn',
    transcript: `
CLINICIAN: Hi Ms. Ortega. Today we're placing the Mirena IUD, right?
PATIENT: Yes. I've finished the paperwork and taken the ibuprofen you recommended.
CLINICIAN: Good. Any nausea, vaginal bleeding today, recent unprotected intercourse?
PATIENT: No. Last period was a week ago, ended yesterday.
CLINICIAN: G-P history?
PATIENT: G2 P2. Two vaginal deliveries, no complications. LMP last week, regular cycles.
CLINICIAN: Any NKDA, meds?
PATIENT: No allergies. Not taking anything right now.
CLINICIAN: Let me examine. Abdomen soft, non-tender. On pelvic exam — external genitalia normal, no lesions. Speculum — cervix appears healthy, no discharge. Bimanual — uterus anteverted, mobile, non-tender. Adnexa non-tender without masses.
CLINICIAN: Procedure — I'll cleanse the cervix with Betadine, grasp with a tenaculum, sound the uterus to seven centimeters, and place the Mirena IUD. She tolerated it well. Strings trimmed to three centimeters. I'll see her back in four to six weeks for a string check.
CLINICIAN: Continue barrier protection the first seven days for backup. Call if severe pain, fever, heavy bleeding, or missed strings.
PATIENT: Thank you.
`.trim(),
    expectedSubjectiveKeys: ['chief_complaint', 'menstrual_history', 'obstetric_history'],
    expectedPlanKeys: ['procedures_in_clinic', 'contraception_plan', 'follow_up'],
    // Z30.430 (encounter for insertion of IUD) is the precise code for
    // the procedure; Z30.018 is the broader counselling code. Accept
    // either, plus adjacent Z30.43x for IUD management contexts.
    expectedIcd10Candidates: ['Z30.430', 'Z30.018', 'Z30.09', 'Z30.431', 'Z30.432'],
    expectedCptCodes: ['58300', '99213', '99214'],
    expectedRxDrugs: [],
    expectedReferralSpecialty: undefined,
  },
];
