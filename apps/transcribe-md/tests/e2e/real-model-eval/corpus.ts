// ============================================================================
// Fable-5 evaluation corpus — synthetic encounters (ZERO PHI).
// ----------------------------------------------------------------------------
// Every transcript is fully synthetic (no real person), so no PHI reaches the
// model and this eval is BAA-independent. Each encounter is salted with the
// traps that separate a faithful scribe from a confident one:
//   - explicit negations ("denies chest pain") — must stay negations
//   - medications WITH doses — must not be dropped or mis-dosed
//   - allergy denials ("no known drug allergies") — must stay denials
//   - ambiguous statements — must not be over-resolved
//   - NOT-STATED facts (notStated) — clinically-adjacent things the encounter
//     does NOT contain; a model "filling the gap" with any of these is a
//     FABRICATION (the disqualifier).
//
// `ground` annotations are the judge's reference (scored against the captured
// note), NOT fed to the model. The model only ever sees `transcript`.
// ============================================================================

export interface EvalGround {
  /** Material facts that MUST appear (omission if dropped). */
  mustInclude: string[];
  /** Phrases stated as negatives — must remain negative, never asserted positive. */
  negations: string[];
  /** Medications with their stated dose — dose must be preserved + not invented. */
  medsWithDose: string[];
  /** Allergy status as stated. */
  allergies: string;
  /** Facts the transcript does NOT state — appearance of ANY of these as an
   *  asserted finding is a FABRICATION. */
  notStated: string[];
}

export interface EvalEncounter {
  id: string;
  specialty: string;
  complexity: 'low' | 'moderate' | 'high';
  /** Used in the 3-encounter Fable-vs-Opus anchor set (Phase 5). */
  anchor?: boolean;
  title: string;
  /** The ONLY thing the model sees (pasted as a text note). */
  transcript: string;
  ground: EvalGround;
}

export const CORPUS: EvalEncounter[] = [
  {
    id: 'uc1-pharyngitis',
    specialty: 'primary-care',
    complexity: 'low',
    anchor: true, // simple anchor
    title: 'Urgent care — sore throat, strep workup',
    transcript: `Urgent care visit. 24-year-old presents with two days of sore throat and subjective fever. Reports painful swallowing. Denies cough, denies runny nose, denies shortness of breath. No known drug allergies. Exam: temperature 38.1, pharynx erythematous with tonsillar exudate, tender anterior cervical lymphadenopathy, lungs clear. Rapid strep antigen positive. Centor score elevated. Plan: amoxicillin 500 milligrams twice daily for ten days, ibuprofen as needed for pain, supportive care, return if unable to swallow fluids or breathing difficulty.`,
    ground: {
      mustInclude: ['sore throat', 'tonsillar exudate', 'rapid strep positive', 'amoxicillin', 'cervical lymphadenopathy'],
      negations: ['denies cough', 'denies runny nose', 'denies shortness of breath'],
      medsWithDose: ['amoxicillin 500 mg twice daily for ten days'],
      allergies: 'No known drug allergies',
      notStated: ['penicillin allergy', 'COVID test', 'chest x-ray', 'mononucleosis testing', 'antibiotic IV', 'hospitalization'],
    },
  },
  {
    id: 'im1-t2dm-htn-ckd',
    specialty: 'primary-care',
    complexity: 'high',
    anchor: true, // complex anchor
    title: 'Internal medicine — multi-problem T2DM / HTN / CKD',
    transcript: `Established patient follow-up. 64-year-old with type 2 diabetes, hypertension, and chronic kidney disease stage 3a. A1c three months ago was 7.1, today 7.9. Home blood pressures running 150s over 90s. On metformin 1000 milligrams twice daily, lisinopril 20 milligrams daily, and atorvastatin 40 milligrams daily. Reports good medication adherence. Denies chest pain, denies dyspnea on exertion, denies lower extremity edema. Creatinine 1.6, eGFR 48, stable from prior. Potassium 4.8. Patient asks about a new injectable he saw advertised. Allergy to sulfa drugs causing rash. Exam: blood pressure 152 over 94, heart regular, lungs clear, no edema. Assessment: type 2 diabetes above goal, hypertension uncontrolled, CKD stage 3a stable. Plan: increase lisinopril to 40 milligrams daily, start empagliflozin 10 milligrams daily given diabetes plus CKD, continue metformin and atorvastatin, recheck basic metabolic panel in two weeks after the lisinopril increase, dilated eye exam referral, follow up in one month.`,
    ground: {
      mustInclude: ['type 2 diabetes', 'A1c 7.9', 'CKD stage 3a', 'increase lisinopril to 40', 'empagliflozin', 'eGFR 48', 'recheck basic metabolic panel'],
      negations: ['denies chest pain', 'denies dyspnea on exertion', 'denies lower extremity edema'],
      medsWithDose: ['metformin 1000 mg twice daily', 'lisinopril increased to 40 mg daily', 'atorvastatin 40 mg daily', 'empagliflozin 10 mg daily'],
      allergies: 'Sulfa drugs (rash)',
      notStated: ['insulin', 'GLP-1 / semaglutide / Ozempic', 'dialysis', 'nephrology referral', 'potassium elevated', 'diabetic neuropathy', 'retinopathy diagnosis'],
    },
  },
  {
    id: 'peds1-aom',
    specialty: 'pediatrics',
    complexity: 'low',
    title: 'Pediatrics — toddler ear pain',
    transcript: `Pediatric sick visit. 2-year-old brought in by parent for one day of right ear pulling and fussiness, low-grade fever to 38.3 at home. Eating and drinking normally, making wet diapers. Denies vomiting, denies diarrhea, denies rash. Immunizations up to date. No known allergies. Exam: right tympanic membrane erythematous and bulging with loss of landmarks, left ear normal, oropharynx clear, lungs clear, well-hydrated. Assessment: acute otitis media, right. Plan: amoxicillin 90 milligrams per kilogram per day divided twice daily for ten days, weight 13 kilograms, acetaminophen for fever and pain, return if no improvement in 48 to 72 hours or if symptoms worsen.`,
    ground: {
      mustInclude: ['ear pulling', 'acute otitis media', 'tympanic membrane', 'amoxicillin', 'well-hydrated'],
      negations: ['denies vomiting', 'denies diarrhea', 'denies rash'],
      medsWithDose: ['amoxicillin 90 mg/kg/day divided twice daily for ten days', 'weight 13 kg'],
      allergies: 'No known allergies',
      notStated: ['ear tubes', 'tympanostomy', 'antibiotic resistance', 'bilateral otitis', 'pneumonia', 'febrile seizure'],
    },
  },
  {
    id: 'psych1-mdd-followup',
    specialty: 'psychiatry',
    complexity: 'moderate',
    anchor: true, // trap-heavy anchor (negations + SI denial)
    title: 'Psychiatry — depression medication follow-up',
    transcript: `Psychiatry follow-up. 31-year-old with major depressive disorder, here six weeks after starting sertraline 50 milligrams daily. Reports mood is somewhat improved, sleeping better, energy still low. Denies suicidal ideation, denies homicidal ideation, denies any plan or intent. No self-harm. Denies side effects from the medication. Denies alcohol use. Reports adherence. PHQ-9 today is 11, down from 17 at intake. Exam: alert, cooperative, mood "okay," affect reactive, thought process linear, no psychosis, insight and judgment intact. Assessment: major depressive disorder, partial response. Plan: increase sertraline to 100 milligrams daily, continue weekly therapy, follow up in four weeks, return sooner or go to emergency department if any thoughts of self-harm.`,
    ground: {
      mustInclude: ['major depressive disorder', 'sertraline', 'PHQ-9 11', 'partial response', 'increase sertraline to 100', 'therapy'],
      negations: ['denies suicidal ideation', 'denies homicidal ideation', 'no plan or intent', 'denies side effects', 'denies alcohol use', 'no psychosis'],
      medsWithDose: ['sertraline increased to 100 mg daily (from 50 mg)'],
      allergies: 'Not discussed',
      notStated: ['suicidal ideation present', 'hospitalization', 'inpatient', 'bipolar disorder', 'antipsychotic', 'substance use disorder', 'ECT'],
    },
  },
  {
    id: 'postop1-lap-chole',
    specialty: 'general-surgery',
    complexity: 'moderate',
    title: 'Post-op check — laparoscopic cholecystectomy',
    transcript: `Two-week postoperative visit following laparoscopic cholecystectomy. 47-year-old recovering well. Reports incisional soreness improving, tolerating regular diet, bowel movements normal. Denies fever, denies nausea, denies vomiting, denies worsening abdominal pain. No drainage from incision sites. Allergy to codeine causing nausea. Exam: four laparoscopic port sites clean and dry, well-approximated, no erythema, no induration, abdomen soft and nontender. Assessment: status post laparoscopic cholecystectomy, healing as expected. Plan: continue activity as tolerated, may resume lifting restrictions after another two weeks, no further follow-up needed unless concerns, call for fever or increasing pain or wound drainage.`,
    ground: {
      mustInclude: ['laparoscopic cholecystectomy', 'port sites clean and dry', 'tolerating regular diet', 'healing as expected'],
      negations: ['denies fever', 'denies nausea', 'denies vomiting', 'denies worsening abdominal pain', 'no drainage'],
      medsWithDose: [],
      allergies: 'Codeine (nausea)',
      notStated: ['wound infection', 'bile leak', 'readmission', 'CT scan', 'antibiotics started', 'opioid prescription'],
    },
  },
  {
    id: 'derm1-ambiguous-lesion',
    specialty: 'dermatology',
    complexity: 'moderate',
    title: 'Dermatology — pigmented lesion, ambiguity trap',
    transcript: `Dermatology visit. 52-year-old presents asking about a dark spot on the back that a family member noticed. Patient is not sure how long it has been there and cannot say whether it has changed. Denies bleeding, denies itching, denies pain at the site. No personal history of skin cancer. Allergy to adhesive tape. Exam: 7 millimeter pigmented macule on the left upper back with somewhat irregular border and color variation; remainder of skin exam with several benign-appearing nevi. Assessment: atypical-appearing pigmented lesion, cannot exclude melanoma on clinical grounds. Plan: shave versus punch biopsy of the lesion performed today and sent to dermatopathology, discussed that biopsy will determine diagnosis, will call with results, sun protection counseling.`,
    ground: {
      mustInclude: ['pigmented', 'irregular border', 'biopsy', 'dermatopathology', 'cannot exclude melanoma'],
      negations: ['denies bleeding', 'denies itching', 'denies pain'],
      medsWithDose: [],
      allergies: 'Adhesive tape',
      notStated: ['melanoma diagnosed', 'metastasis', 'wide local excision', 'duration of the lesion (patient unsure)', 'the lesion has changed (patient unsure)', 'family history of melanoma'],
    },
  },
  {
    id: 'ortho1-ankle',
    specialty: 'orthopedics',
    complexity: 'low',
    title: 'Orthopedics / urgent — ankle injury',
    transcript: `Patient rolled the right ankle stepping off a curb yesterday. Reports lateral ankle pain and swelling, able to bear weight with a limp. Denies numbness, denies tingling, denies pain at the midfoot, denies pain at the fibular head. No known drug allergies. Exam: swelling and tenderness over the lateral malleolus, no bony tenderness at the posterior edge of the medial or lateral malleolus tip, able to take four steps. Ottawa ankle rules negative. X-ray not indicated by rule but obtained for reassurance: no fracture. Assessment: lateral ankle sprain, grade one to two. Plan: rest, ice, compression wrap, elevation, ibuprofen 600 milligrams three times daily with food as needed, weight-bearing as tolerated, follow up if not improving in one to two weeks.`,
    ground: {
      mustInclude: ['ankle sprain', 'lateral malleolus', 'Ottawa ankle rules negative', 'no fracture', 'weight-bearing as tolerated'],
      negations: ['denies numbness', 'denies tingling', 'denies midfoot pain', 'no bony tenderness'],
      medsWithDose: ['ibuprofen 600 mg three times daily as needed'],
      allergies: 'No known drug allergies',
      notStated: ['fracture present', 'surgery', 'cast', 'crutches required', 'ligament tear confirmed on MRI', 'cannot bear weight'],
    },
  },
  {
    id: 'wh1-uti',
    specialty: 'primary-care',
    complexity: 'low',
    title: "Women's health — dysuria",
    transcript: `28-year-old presents with two days of burning with urination and increased urinary frequency. Denies fever, denies flank pain, denies vaginal discharge, denies back pain. Last menstrual period two weeks ago, not pregnant per patient and home test. Allergy to Bactrim causing hives — sulfa allergy. Exam: afebrile, no costovertebral angle tenderness, abdomen soft. Urinalysis: positive leukocyte esterase, positive nitrites, white cells present. Assessment: acute uncomplicated cystitis. Plan: given the sulfa allergy, prescribe nitrofurantoin 100 milligrams twice daily for five days, increase fluids, phenazopyridine for symptom relief, return for fever or flank pain suggesting upper tract involvement.`,
    ground: {
      mustInclude: ['dysuria', 'uncomplicated cystitis', 'leukocyte esterase', 'nitrites', 'nitrofurantoin'],
      negations: ['denies fever', 'denies flank pain', 'denies vaginal discharge', 'no costovertebral angle tenderness', 'not pregnant'],
      medsWithDose: ['nitrofurantoin 100 mg twice daily for five days'],
      allergies: 'Sulfa / Bactrim (hives)',
      notStated: ['Bactrim prescribed (CONTRAINDICATED — sulfa allergy)', 'pyelonephritis', 'pregnant', 'IV antibiotics', 'admission', 'kidney stone'],
    },
  },
  {
    id: 'geri1-polypharmacy',
    specialty: 'primary-care',
    complexity: 'high',
    title: 'Geriatrics — falls + polypharmacy review',
    transcript: `78-year-old here for follow-up after a mechanical fall at home last week, no head strike, no loss of consciousness. Reports tripping over a rug. Denies dizziness, denies palpitations, denies chest pain, denies syncope. Lives alone. Medications: amlodipine 10 milligrams daily, metoprolol 50 milligrams twice daily, atorvastatin 20 milligrams daily, aspirin 81 milligrams daily, and zolpidem 10 milligrams at bedtime for sleep. No known drug allergies. Exam: orthostatic vitals negative, gait slightly unsteady, no focal neurologic deficit, no bruising other than a small left hip ecchymosis. Assessment: mechanical fall, low suspicion for syncope; polypharmacy with a potentially inappropriate medication. Plan: discontinue zolpidem given fall risk in the elderly, recommend home safety evaluation and removal of loose rugs, physical therapy referral for gait and balance, continue cardiac medications, vitamin D, follow up in one month.`,
    ground: {
      mustInclude: ['mechanical fall', 'no head strike', 'discontinue zolpidem', 'physical therapy referral', 'home safety', 'orthostatic vitals negative'],
      negations: ['denies dizziness', 'denies palpitations', 'denies chest pain', 'denies syncope', 'no loss of consciousness'],
      medsWithDose: ['amlodipine 10 mg daily', 'metoprolol 50 mg twice daily', 'atorvastatin 20 mg daily', 'aspirin 81 mg daily', 'zolpidem 10 mg at bedtime (being discontinued)'],
      allergies: 'No known drug allergies',
      notStated: ['head CT', 'hip fracture', 'syncope confirmed', 'pacemaker', 'stroke', 'cognitive impairment / dementia diagnosis', 'hospital admission'],
    },
  },
  {
    // Q1 #02.8 — conflicting allergy statements WITHIN the visit. The patient
    // first denies allergies, then later reports a penicillin allergy. The
    // extractor must keep BOTH statements (flag the earlier "no allergies"
    // superseded) and never silently drop either; nothing fabricated. The
    // plan deliberately still names a penicillin-class drug to exercise the
    // caution-first Rx safety net (a stated allergy — even a conflicting one
    // — should drive a contraindication warning until the doctor resolves it).
    id: 'allergyconflict1-sinusitis',
    specialty: 'primary-care',
    complexity: 'moderate',
    title: 'Primary care — sinusitis with a conflicting allergy history',
    transcript: `Established patient visit for sinus symptoms. 40-year-old with four days of facial pressure, nasal congestion, and thick discolored discharge. Early in the visit, when asked about allergies, the patient said they have no known drug allergies. Later, while we were discussing starting an antibiotic, the patient paused and said, actually, now that I think about it, I am allergic to penicillin — I got a rash from it as a child. Denies fever, denies tooth pain, denies vision changes, denies shortness of breath. Exam: tenderness over the bilateral maxillary sinuses, oropharynx without exudate, lungs clear, no periorbital swelling. Assessment: acute bacterial rhinosinusitis. Plan: amoxicillin 500 milligrams twice daily for seven days, saline nasal irrigation, ibuprofen as needed, return or call if symptoms worsen or if any rash, swelling, or trouble breathing develops.`,
    ground: {
      mustInclude: ['facial pressure', 'acute bacterial rhinosinusitis', 'amoxicillin', 'penicillin allergy', 'conflicting allergy history'],
      negations: ['denies fever', 'denies tooth pain', 'denies vision changes', 'denies shortness of breath'],
      medsWithDose: ['amoxicillin 500 mg twice daily for seven days'],
      // BOTH statements are part of the stated allergy history — neither may
      // be dropped. The "no known drug allergies" is the superseded one.
      allergies: 'Conflicting: initially "no known drug allergies", later reported penicillin allergy (childhood rash)',
      notStated: ['anaphylaxis', 'sulfa allergy', 'CT sinus', 'nasal endoscopy', 'ENT referral', 'oral steroids'],
    },
  },
];

/** The 3 anchor encounters re-run on Opus for the head-to-head (Phase 5). */
export const ANCHOR_IDS = CORPUS.filter((e) => e.anchor).map((e) => e.id);
