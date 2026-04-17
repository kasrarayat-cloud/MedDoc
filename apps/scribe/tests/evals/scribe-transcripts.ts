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
  },
];
