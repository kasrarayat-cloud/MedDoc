// ============================================================================
// Cross-input-mode audit scenarios (2026-05-13).
// ----------------------------------------------------------------------------
// One script per (specialty, scenario). Each script is the doctor-dictation
// form — used verbatim as text_notes input, synthesized to TTS audio for
// both voice_dictation (single-speaker L1b) and audio_upload (L1 with
// diarization disabled-by-monologue) modes.
//
// Per-scenario expectations are intentionally LOOSE (at-least-one-of) so
// the parity check doesn't trip on legitimate model variance. The
// load-bearing demo scenarios (Bariatric calcium, Vascular iohexol,
// Vascular prasugrel, Weight-Mgmt GLP-1) carry stronger expectations
// for the safety rules they're designed to test.
// ============================================================================

export interface ScenarioExpectation {
  /** ICD-10 codes that ideally appear in L7a output. At least one
   *  from each sub-array should fire (the model has discretion on
   *  laterality / specificity). */
  icdAnyOf?: string[][];
  /** CPT E&M code(s) that match the visit complexity. */
  cptEmAnyOf?: string[];
  /** CPT procedure codes that ideally appear (when relevant). */
  cptProcsAnyOf?: string[];
  /** Drug names the model should draft. */
  rxDrugsAnyOf?: string[][];
  /** Free-text safety-rule patterns — regex applied to rxDrafts.warnings
   *  messages. The load-bearing demo moments (calcium-carbonate,
   *  contrast-AKI, prasugrel-TIA, GLP-1 thyroid). */
  rxSafetyRules?: { label: string; pattern: RegExp; required?: boolean }[];
}

export interface Scenario {
  /** Lowercase code: e.g. 'BS1', 'VS2'. */
  tag: string;
  specialty: string;          // matches transcribe_visits.specialty values
  specialtyLabel: string;     // for the report
  /** ~30-50 char demo subtitle. */
  title: string;
  /** Dictation-style script (~150-300 words). One paragraph or a
   *  sequence of clinical bullets. Used verbatim for text_notes;
   *  TTS-synthesized for voice_dictation + audio_upload. */
  script: string;
  expect: ScenarioExpectation;
}

export const SCENARIOS: Scenario[] = [
  // ── Primary Care ────────────────────────────────────────────────────
  {
    tag: 'PC1',
    specialty: 'primary-care',
    specialtyLabel: 'Primary Care',
    title: 'T2DM follow-up — A1c rising, statin uptitration',
    script: `
Patient is a 58-year-old female with a 12-year history of type 2 diabetes mellitus presenting for routine follow-up. Last A1c three months ago was 7.4, today's value is 8.2 with fasting glucose 168. Patient has been compliant with metformin 1000 milligrams twice daily and is also on lisinopril 20 milligrams daily for hypertension and atorvastatin 20 milligrams daily for hyperlipidemia. Recent lipid panel shows LDL 112 which is above goal for this ASCVD-equivalent patient. Patient reports neuropathic tingling in both feet over the last two months without ulceration. Blood pressure today 138 over 82.
Assessment: type 2 diabetes mellitus with hyperglycemia and likely diabetic peripheral neuropathy, hyperlipidemia not at goal, essential hypertension. Plan: continue metformin, add empagliflozin 10 milligrams daily for both glycemic control and cardiovascular benefit, increase atorvastatin to 40 milligrams daily targeting LDL under 70 in this high-risk patient, continue lisinopril, start gabapentin 100 milligrams three times daily for the neuropathic symptoms, order microalbumin, foot exam annually, and three-month follow-up with repeat A1c.
This is an established patient visit with moderate-complexity medical decision-making and approximately 25 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['E11.65', 'E11.9', 'E11.40', 'E11.42'],
        ['I10'],
        ['E78.5', 'E78.4'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      rxDrugsAnyOf: [['metformin'], ['empagliflozin', 'jardiance'], ['atorvastatin'], ['gabapentin']],
    },
  },
  {
    tag: 'PC2',
    specialty: 'primary-care',
    specialtyLabel: 'Primary Care',
    title: 'Uncontrolled HTN — three-drug regimen',
    script: `
Patient is a 66-year-old African American male presenting for hypertension follow-up. Home blood pressure readings averaging 158 over 96 over the last two weeks despite triple therapy with lisinopril 40 milligrams daily, amlodipine 10 milligrams daily, and hydrochlorothiazide 25 milligrams daily. He denies medication non-adherence. No chest pain, no shortness of breath, no headaches. Past medical history significant for type 2 diabetes mellitus controlled on metformin with A1c 6.8, chronic kidney disease stage 2 with creatinine 1.1 and eGFR 78, and a remote NSTEMI in 2021 status post one drug-eluting stent to the LAD. Today's vitals: blood pressure 162 over 98, heart rate 78 regular. Exam unremarkable apart from elevated blood pressure.
Assessment: resistant hypertension despite three appropriate antihypertensive classes, chronic kidney disease stage 2, type 2 diabetes mellitus, atherosclerotic heart disease status post stent. Plan: add spironolactone 25 milligrams daily, order morning aldosterone-to-renin ratio, repeat BMP in two weeks to monitor potassium, continue current antihypertensive regimen, continue metformin and aspirin 81, recheck blood pressure in four weeks.
Established patient, moderate-to-high complexity MDM, approximately 30 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['I10', 'I12.9', 'I13.10'],
        ['E11.9', 'E11.65'],
        ['N18.2', 'N18.30', 'N18.9'],
        ['I25.10', 'I25.2'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      rxDrugsAnyOf: [['lisinopril'], ['amlodipine'], ['spironolactone'], ['metformin']],
    },
  },

  // ── Cardiology ──────────────────────────────────────────────────────
  {
    tag: 'C1',
    specialty: 'cardiology',
    specialtyLabel: 'Cardiology',
    title: 'AF — CHA2DS2-VASc 4, DOAC selection',
    script: `
Patient is a 72-year-old female with new-onset atrial fibrillation diagnosed last week on routine ECG, now referred for management. Symptoms include intermittent palpitations and mild fatigue but no syncope, no chest pain, and no overt heart failure symptoms. CHA2DS2-VASc score is 4 based on age greater than 65, female sex, hypertension, and type 2 diabetes mellitus. HAS-BLED score is 2 based on hypertension and age. She is currently on metoprolol succinate 50 milligrams daily for rate control, lisinopril 20 milligrams daily, atorvastatin 40 milligrams daily, and metformin 1000 milligrams twice daily. Renal function shows eGFR 62, hemoglobin 13.4, platelets 240. Today's vitals: heart rate 88 irregularly irregular, blood pressure 132 over 78. Echocardiogram from last week shows left ventricular ejection fraction 55 percent and mild left atrial dilation.
Assessment: paroxysmal atrial fibrillation with CHA2DS2-VASc 4, clear indication for oral anticoagulation, hypertension, type 2 diabetes, hyperlipidemia, rate-controlled on metoprolol. Plan: start apixaban 5 milligrams twice daily for stroke prevention, continue metoprolol succinate for rate control, continue antihypertensive and statin regimen, schedule cardioversion if symptoms persist after rate optimization, lifestyle counseling on alcohol limitation, follow-up in four weeks.
New patient consult, high MDM, approximately 50 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['I48.0', 'I48.1', 'I48.91', 'I48.2'],
        ['I10'],
        ['E11.9', 'E11.65'],
      ],
      cptEmAnyOf: ['99204', '99205', '99214', '99215'],
      rxDrugsAnyOf: [['apixaban', 'eliquis'], ['metoprolol', 'metoprolol succinate']],
    },
  },
  {
    tag: 'C2',
    specialty: 'cardiology',
    specialtyLabel: 'Cardiology',
    title: 'HFrEF — quadruple therapy + ICD eligibility',
    script: `
Patient is a 64-year-old male with ischemic cardiomyopathy following an anterior myocardial infarction six years ago, presenting for heart failure follow-up. NYHA class 2 symptoms with dyspnea on moderate exertion, denies orthopnea or paroxysmal nocturnal dyspnea. Most recent echocardiogram shows left ventricular ejection fraction 28 percent, severely reduced. Current heart failure regimen includes sacubitril-valsartan 97-103 milligrams twice daily, metoprolol succinate 200 milligrams daily, spironolactone 25 milligrams daily, and dapagliflozin 10 milligrams daily. Also on aspirin 81 milligrams daily, atorvastatin 80 milligrams daily, and clopidogrel 75 milligrams daily for ASCVD. He has no implantable cardioverter defibrillator. Today's vitals: blood pressure 108 over 64, heart rate 68 in sinus rhythm. Patient has been on optimal guideline-directed medical therapy for greater than three months.
Assessment: chronic systolic heart failure with reduced ejection fraction at 28 percent, ischemic cardiomyopathy, NYHA class 2 on optimal medical therapy, meets primary prevention indication for ICD per current guidelines. Plan: refer to electrophysiology for primary prevention implantable cardioverter defibrillator evaluation, continue quadruple therapy, continue dual antiplatelet therapy, three-month follow-up with repeat echocardiogram, sodium-restricted diet counseling.
Established patient, high MDM, approximately 40 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['I50.22', 'I50.20', 'I50.21'],
        ['I25.2', 'I25.10'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      rxDrugsAnyOf: [
        ['sacubitril-valsartan', 'sacubitril/valsartan', 'entresto'],
        ['metoprolol', 'metoprolol succinate'],
        ['spironolactone'],
        ['dapagliflozin', 'farxiga'],
      ],
    },
  },

  // ── Psychiatry ──────────────────────────────────────────────────────
  {
    tag: 'PSY1',
    specialty: 'psychiatry',
    specialtyLabel: 'Psychiatry',
    title: 'MDD — SSRI start + suicide screen',
    script: `
Patient is a 34-year-old female presenting for initial evaluation of depression of approximately six months' duration. Symptoms include depressed mood most days, anhedonia, sleep disruption with both initial and middle insomnia, fatigue, impaired concentration affecting her work as an accountant, and feelings of worthlessness. Appetite mildly decreased with five-pound weight loss. PHQ-9 score today is 17 indicating moderately severe depression. Patient explicitly denies suicidal ideation, plan, or intent, and denies prior suicide attempts. No history of mania or hypomania. No psychotic features. Past psychiatric history is otherwise unremarkable. No prior psychotropic medication trials. No substance use. Past medical history significant for hypothyroidism on levothyroxine 75 micrograms daily with most recent TSH 1.8. No current medications other than levothyroxine. No known drug allergies.
Assessment: major depressive disorder single episode moderate severity, hypothyroidism stable on current dose. Plan: start sertraline 50 milligrams daily, counsel on common side effects, two-to-four week titration timeline, and not to discontinue abruptly, refer for cognitive behavioral therapy, safety contract obtained verbally, patient is to call our office or go to emergency department for any suicidal ideation, follow-up in two weeks to monitor tolerance and response.
New patient consult, moderate MDM, approximately 60 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['F32.1', 'F32.0', 'F32.2', 'F32.9'],
        ['E03.9'],
      ],
      cptEmAnyOf: ['99204', '99205', '90792', '99214', '99215'],
      rxDrugsAnyOf: [['sertraline', 'zoloft']],
    },
  },
  {
    tag: 'PSY2',
    specialty: 'psychiatry',
    specialtyLabel: 'Psychiatry',
    title: 'GAD on chronic alprazolam — taper consideration',
    script: `
Patient is a 52-year-old male with longstanding generalized anxiety disorder presenting for medication management. He has been on alprazolam 0.5 milligrams three times daily as needed for the past seven years, prescribed by his prior psychiatrist. He acknowledges escalating use over the past year and is now using all three doses daily including one at bedtime. He recognizes this represents physical dependence and wants to discuss tapering given concerns about cognitive effects and recent fall risk. He is also on escitalopram 20 milligrams daily for several years with partial response. He denies alcohol use, denies illicit drug use, denies suicidal ideation. Past medical history unremarkable. GAD-7 today is 12 indicating moderate anxiety.
Assessment: generalized anxiety disorder with chronic benzodiazepine use and physical dependence, on appropriate SSRI baseline therapy. Plan: cross-taper plan initiated, switch alprazolam to longer-acting clonazepam 0.5 milligrams twice daily for two weeks, then begin a 12-week taper reducing dose by 0.125 milligrams every two weeks, continue escitalopram, refer for cognitive behavioral therapy specifically for anxiety, prescribe hydroxyzine 25 milligrams as needed up to four times daily for breakthrough anxiety during taper, counsel on the risks of abrupt discontinuation including seizure, follow-up in two weeks.
Established patient, high MDM, approximately 50 minutes face-to-face.
`.trim(),
    expect: {
      icdAnyOf: [
        ['F41.1', 'F41.9'],
        ['F13.20', 'F13.21', 'F13.10'],
      ],
      cptEmAnyOf: ['99214', '99215', '90833', '90836'],
      rxDrugsAnyOf: [['clonazepam', 'klonopin'], ['escitalopram', 'lexapro'], ['hydroxyzine']],
    },
  },

  // ── Pediatrics ──────────────────────────────────────────────────────
  {
    tag: 'PED1',
    specialty: 'pediatrics',
    specialtyLabel: 'Pediatrics',
    title: 'Acute otitis media — amoxicillin weight-based dosing',
    script: `
Patient is a 4-year-old female brought in by mother for two days of right ear pain, fever to 101.8 degrees Fahrenheit, and decreased oral intake. No vomiting, no diarrhea. Past medical history significant for recurrent otitis media with three episodes over the past 12 months. Up to date on immunizations including pneumococcal and Hib. No known drug allergies, specifically tolerates amoxicillin without reaction in the past. Weight today 16 kilograms. Temperature 101.4, heart rate 118, pulse oximetry 99 percent. Otoscopy: right tympanic membrane bulging, erythematous, with loss of normal landmarks; left tympanic membrane normal. Posterior cervical lymphadenopathy bilaterally, small. Lungs clear, no respiratory distress.
Assessment: acute right otitis media in an immunocompetent toddler with recurrent disease. Plan: start amoxicillin 90 milligrams per kilogram per day divided twice daily, which calculates to 720 milligrams twice daily for this 16-kilogram child, for 10 days, ibuprofen 10 milligrams per kilogram every six hours as needed for pain and fever, recheck in 48 to 72 hours if not improving, return precautions reviewed including worsening pain, persistent fever, neck stiffness, or any change in mental status.
Established pediatric patient, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['H66.91', 'H66.001', 'H66.011', 'H66.90'],
      ],
      cptEmAnyOf: ['99213', '99214'],
      rxDrugsAnyOf: [['amoxicillin'], ['ibuprofen']],
    },
  },
  {
    tag: 'PED2',
    specialty: 'pediatrics',
    specialtyLabel: 'Pediatrics',
    title: 'Pediatric asthma exacerbation — step up',
    script: `
Patient is a 7-year-old male with a known history of mild persistent asthma, brought in by father for worsening cough and wheeze over the past three days following a viral upper respiratory infection. He has needed his albuterol rescue inhaler approximately every three to four hours during the day and was awakened twice last night by cough. He is currently on fluticasone 88 micrograms inhaled twice daily as his controller. No fever, no chest pain. Weight today 24 kilograms, temperature 98.4, heart rate 108, respiratory rate 26, pulse oximetry 95 percent on room air. Exam shows mild accessory muscle use, diffuse expiratory wheezing bilaterally with prolonged expiratory phase. Peak expiratory flow today 60 percent of personal best.
Assessment: acute moderate asthma exacerbation in a child with mild persistent asthma, viral-triggered. Plan: in-office albuterol nebulizer 2.5 milligrams via mouthpiece, after which oxygen saturation improved to 98 percent and wheezing decreased significantly, start oral prednisolone 1 milligram per kilogram per day which is 24 milligrams daily for 5 days, increase fluticasone to 110 micrograms twice daily as step-up controller therapy given recurrent exacerbation pattern, continue albuterol HFA 90 micrograms 2 puffs every 4 to 6 hours as needed, asthma action plan reviewed with parent, follow-up in 7 days.
Established pediatric patient, moderate-to-high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['J45.41', 'J45.40', 'J45.21', 'J45.20', 'J45.901', 'J45.902'],
      ],
      cptEmAnyOf: ['99213', '99214', '99215'],
      rxDrugsAnyOf: [['prednisolone', 'prednisone'], ['fluticasone'], ['albuterol']],
    },
  },

  // ── OB-GYN ──────────────────────────────────────────────────────────
  {
    tag: 'OB1',
    specialty: 'ob-gyn',
    specialtyLabel: 'OB-GYN',
    title: 'GDM screen — 28-week visit',
    script: `
Patient is a 31-year-old gravida 2 para 1 at 28 weeks and 3 days gestational age by accurate first-trimester dating, presenting for routine prenatal visit. Pregnancy has been uncomplicated to date. She denies vaginal bleeding, leakage of fluid, contractions, or decreased fetal movement. Family history significant for type 2 diabetes mellitus in both parents. Pre-pregnancy BMI was 31. Today's vitals: blood pressure 118 over 72, weight gain 18 pounds since the start of pregnancy. Fundal height 28 centimeters, fetal heart tones 142, fetal movement reported as active. One-hour 50-gram glucose challenge result this morning was 168 milligrams per deciliter, exceeding the cutoff of 140.
Assessment: 28-week intrauterine pregnancy in a woman with significant risk factors for gestational diabetes mellitus, abnormal one-hour glucose challenge requiring confirmatory testing. Plan: schedule three-hour 100-gram oral glucose tolerance test within the next week, dietary counseling on carbohydrate distribution, fetal kick counts daily starting at 28 weeks, prenatal vitamin with iron continued, Tdap at this visit, RhoGAM at 28 weeks reviewed and patient is Rh-positive so not indicated, return in two weeks or sooner with three-hour OGTT results.
Established prenatal patient, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['Z34.83', 'Z34.93', 'O36.0991'],
        ['R73.01', 'R73.03', 'O24.410'],
      ],
      cptEmAnyOf: ['99213', '99214'],
      rxDrugsAnyOf: [['prenatal vitamin', 'multivitamin']],
    },
  },
  {
    tag: 'OB2',
    specialty: 'ob-gyn',
    specialtyLabel: 'OB-GYN',
    title: 'Postpartum visit — 6-week follow-up',
    script: `
Patient is a 29-year-old gravida 1 para 1 at six weeks postpartum after an uncomplicated vaginal delivery of a term infant. Breastfeeding is going well. Lochia has resolved. No vaginal bleeding currently. She denies postpartum mood symptoms, depression screen with Edinburgh Postnatal Depression Scale today scored 4 which is normal. Sexual activity has resumed and she is seeking contraception. Vital signs: blood pressure 122 over 76, BMI 27, returning toward her pre-pregnancy weight. Pelvic exam shows well-healed second-degree laceration, no cervical motion tenderness, uterus involuted. Patient is exclusively breastfeeding and prefers a non-hormonal or progestin-only contraception.
Assessment: routine postpartum visit at six weeks, uncomplicated recovery, contraception desired. Plan: place levonorgestrel-releasing intrauterine device today, contraception counseling, continue prenatal vitamin with iron while breastfeeding, pelvic floor exercises, resume regular activity, follow-up as needed.
Established postpartum patient, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['Z39.2', 'Z30.430', 'Z30.431'],
      ],
      cptEmAnyOf: ['99213', '99214'],
      cptProcsAnyOf: ['58300'],
      rxDrugsAnyOf: [['levonorgestrel'], ['prenatal vitamin']],
    },
  },

  // ── Dermatology ─────────────────────────────────────────────────────
  {
    tag: 'DERM1',
    specialty: 'dermatology',
    specialtyLabel: 'Dermatology',
    title: 'Suspicious nevus — biopsy',
    script: `
Patient is a 48-year-old fair-skinned female presenting for evaluation of a changing pigmented lesion on the left upper back, noted by her spouse two months ago. The lesion has darkened and now measures approximately 8 millimeters in greatest diameter. She has a personal history of three previous benign nevi removed by shave biopsy and significant cumulative sun exposure during her career as a marine biologist. Family history includes melanoma in her father at age 62. On exam she has approximately 50 melanocytic nevi total across her back and arms. The lesion of concern on the left scapular area is asymmetric, has irregular borders, varied pigmentation with brown and black areas, and is 8 millimeters in diameter. Several other nevi are also notable but appear stable.
Assessment: clinically atypical pigmented lesion of the left upper back, ABCDE criteria positive, melanoma cannot be excluded. Plan: perform full-thickness excisional biopsy with narrow 2 millimeter margins today under local lidocaine 1 percent infiltration, specimen sent for dermatopathology, patient to return in 7 to 10 days for results, complete skin exam performed and patient counseled on monthly self-skin exams plus annual screening given her family history, sunscreen SPF 30 minimum daily reinforced.
New patient consult, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['D22.5', 'D48.5', 'L57.0', 'Z80.8'],
      ],
      cptEmAnyOf: ['99204', '99214', '99203', '99213'],
      cptProcsAnyOf: ['11102', '11104', '11402', '11602'],
    },
  },
  {
    tag: 'DERM2',
    specialty: 'dermatology',
    specialtyLabel: 'Dermatology',
    title: 'Severe nodulocystic acne — isotretinoin counseling',
    script: `
Patient is a 19-year-old female with severe nodulocystic acne refractory to multiple prior treatments including topical retinoids, benzoyl peroxide, oral doxycycline 100 milligrams twice daily for 12 weeks, and a 6-month trial of combined oral contraceptive. She continues to have active inflammatory and cystic lesions across the face, upper back, and chest, with early scarring. She is highly motivated to start isotretinoin and has been counseled previously. Her menstrual periods are regular. She is using condoms and an oral contraceptive for contraception and willing to commit to abstinence or two methods of contraception per iPLEDGE requirements. She has no history of depression. Baseline labs drawn last week show normal CBC, normal lipid panel, normal ALT and AST, normal beta-hCG pregnancy test.
Assessment: severe nodulocystic acne refractory to multiple lines of therapy, candidate for systemic isotretinoin. Plan: enroll in iPLEDGE today, start isotretinoin 0.5 milligrams per kilogram per day for the first month then increase to 1 milligram per kilogram per day, monthly labs including lipid panel, AST, ALT, and pregnancy test required per iPLEDGE protocol, two forms of contraception confirmed, counsel on teratogenicity and that pregnancy is absolutely contraindicated during therapy and for one month after, mood monitoring discussed, follow-up monthly.
Established patient, moderate-to-high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['L70.0', 'L70.1', 'L70.8', 'L70.9'],
      ],
      cptEmAnyOf: ['99213', '99214', '99215'],
      rxDrugsAnyOf: [['isotretinoin']],
      rxSafetyRules: [
        {
          label: 'isotretinoin pregnancy / iPLEDGE',
          pattern: /(?:pregnancy|teratogen|iPLEDGE|contracept|two methods)/i,
          required: false,
        },
      ],
    },
  },

  // ── Orthopedics ─────────────────────────────────────────────────────
  {
    tag: 'ORT1',
    specialty: 'orthopedics',
    specialtyLabel: 'Orthopedics',
    title: 'Knee OA — corticosteroid injection',
    script: `
Patient is a 64-year-old female with longstanding bilateral knee osteoarthritis, right knee worse than left, presenting with worsening right knee pain over the past three months. Pain is medial, worse with stairs and after prolonged standing, mild morning stiffness lasting less than 30 minutes, no locking or instability. She has tried scheduled acetaminophen, topical diclofenac gel, and weight loss without adequate relief. She is not a current candidate for total knee arthroplasty as the orthopedic surgeon she saw two months ago recommended a trial of intra-articular corticosteroid injection before surgical consultation. Past medical history significant for hypertension on lisinopril 20 milligrams daily, and type 2 diabetes on metformin with A1c 6.9. BMI 32. Today's exam: right knee with medial joint line tenderness, mild effusion, range of motion 5 to 120 degrees, stable to varus and valgus stress, McMurray negative.
Assessment: bilateral primary osteoarthritis of the knee, right worse than left, refractory to conservative measures. Plan: under sterile technique, right knee aspirated of 8 milliliters of straw-colored fluid using a 20-gauge needle, then injected with 40 milligrams of methylprednisolone acetate combined with 5 milliliters of 1 percent lidocaine, knee placed through gentle range of motion, sterile dressing applied. Patient counseled on temporary glucose elevation given her diabetes, expected onset of relief 2 to 7 days, ice and acetaminophen for short-term discomfort, follow-up in 6 weeks.
Established patient, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['M17.0', 'M17.11', 'M17.12', 'M17.9'],
        ['I10'],
        ['E11.9', 'E11.65'],
      ],
      cptEmAnyOf: ['99213', '99214'],
      cptProcsAnyOf: ['20610', '20611'],
      rxDrugsAnyOf: [['methylprednisolone'], ['lidocaine']],
    },
  },
  {
    tag: 'ORT2',
    specialty: 'orthopedics',
    specialtyLabel: 'Orthopedics',
    title: 'Acute lateral ankle sprain',
    script: `
Patient is a 22-year-old male presenting one day after an inversion injury to the right ankle that occurred during a recreational soccer game. He felt a pop, was unable to bear weight immediately, but is now able to weight-bear with significant pain. No history of prior ankle injury. Past medical history is unremarkable. No medications. No allergies. On exam: lateral ankle swelling and ecchymosis, point tenderness over the anterior talofibular ligament, no tenderness over the navicular, fifth metatarsal base, posterior medial or lateral malleolus, or the proximal fibula. Patient is able to take four limping steps. Anterior drawer test mildly positive. Range of motion limited by pain. Distal neurovascular exam intact. Ottawa Ankle Rules: tenderness over the ATFL but no bony tenderness at the malleoli or navicular or fifth metatarsal base, and patient was able to bear weight both immediately after injury and in the emergency department, so no foot or ankle x-rays are clinically indicated by Ottawa criteria.
Assessment: acute right lateral ankle sprain, likely grade 2, no clinical features mandating imaging by Ottawa rules. Plan: PRICE protocol over the next 48 to 72 hours, weight-bear as tolerated, ibuprofen 400 milligrams every 6 hours with food as needed for 5 to 7 days, ankle brace prescription, early functional rehabilitation with calf stretches and proprioception exercises, return precautions for worsening pain, swelling, or numbness, follow-up if not improved in 2 weeks.
New patient consult, low-to-moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['S93.401A', 'S93.402A', 'S93.409A', 'S93.421A'],
      ],
      cptEmAnyOf: ['99203', '99204', '99213', '99214'],
      rxDrugsAnyOf: [['ibuprofen']],
    },
  },

  // ── Urgent Care ─────────────────────────────────────────────────────
  {
    tag: 'UC1',
    specialty: 'urgent-care',
    specialtyLabel: 'Urgent Care',
    title: 'Streptococcal pharyngitis — rapid testing',
    script: `
Patient is a 9-year-old male brought in by mother with a two-day history of sore throat, fever to 102 degrees Fahrenheit, and headache. No cough, no rhinorrhea, no nasal congestion. Decreased oral intake due to throat pain. Several classmates have been out sick with similar symptoms this week per mother. Past medical history is unremarkable, no antibiotic allergies. Vital signs: temperature 101.8, heart rate 102, oxygen saturation 99 percent. Exam: tonsillar erythema bilaterally with exudates, tender anterior cervical lymphadenopathy bilaterally, no cough during the visit, no rhinorrhea, no conjunctivitis. McIsaac criteria score is 4 indicating high probability of streptococcal infection. Rapid antigen detection test for group A streptococcus is positive.
Assessment: acute streptococcal pharyngitis confirmed by positive rapid antigen testing. Plan: prescribe amoxicillin 50 milligrams per kilogram per day divided into two doses for 10 days, give the first dose in the office, ibuprofen 10 milligrams per kilogram every 6 hours as needed for fever and pain, encourage oral fluids, return to school no sooner than 24 hours after the first dose of antibiotics and once afebrile, return precautions reviewed including signs of peritonsillar abscess or worsening clinical course.
Urgent care visit, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['J02.0', 'J03.00', 'J03.01', 'J03.90'],
      ],
      cptEmAnyOf: ['99213', '99214', '99204'],
      cptProcsAnyOf: ['87880'],
      rxDrugsAnyOf: [['amoxicillin'], ['ibuprofen']],
    },
  },
  {
    tag: 'UC2',
    specialty: 'urgent-care',
    specialtyLabel: 'Urgent Care',
    title: 'Acute musculoskeletal low back pain',
    script: `
Patient is a 38-year-old male warehouse worker presenting with two days of acute low back pain that began after lifting a heavy box at work. Pain is localized to the lumbar paraspinal region, does not radiate below the buttocks, no leg weakness, no bowel or bladder dysfunction, no saddle anesthesia. No prior history of back surgery or chronic back pain. He denies trauma other than the lifting injury. No fevers, no recent infections, no IV drug use, no significant unintentional weight loss, no history of cancer, no immunosuppression. He is not on chronic steroids. Today's exam: alert, no distress, mild bilateral paraspinal tenderness from L2 through L5 with palpable spasm, range of motion limited by pain at the extremes of flexion and extension, straight leg raise negative bilaterally to 60 degrees, neurologic exam intact with normal strength, sensation, and reflexes in both lower extremities, no saddle anesthesia, normal anal sphincter tone.
Assessment: acute non-radicular mechanical low back strain, no red flags by history or exam. Plan: no imaging indicated at this time per current guidelines for uncomplicated mechanical low back pain without red flags, ibuprofen 600 milligrams every 6 hours with food as needed for 5 to 7 days, cyclobenzaprine 5 milligrams three times daily as needed for short-term spasm not to exceed 2 weeks, encouragement to stay active and avoid prolonged bed rest, ergonomics counseling and safe lifting techniques, return precautions for any new weakness, bowel or bladder symptoms, follow up with primary care in 1 to 2 weeks if not improving.
Urgent care visit, low-to-moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['M54.50', 'M54.5', 'S39.012A', 'M54.9'],
      ],
      cptEmAnyOf: ['99213', '99214', '99204'],
      rxDrugsAnyOf: [['ibuprofen'], ['cyclobenzaprine']],
    },
  },

  // ── Pain Management ─────────────────────────────────────────────────
  {
    tag: 'PM1',
    specialty: 'pain-management',
    specialtyLabel: 'Pain Management',
    title: 'Chronic low back pain — epidural steroid injection',
    script: `
Patient is a 55-year-old female with a 14-year history of chronic axial and radicular low back pain referred from primary care for procedural consideration. Pain radiates from her low back into the posterior left thigh and calf, consistent with L5 distribution. MRI lumbar spine from last month shows L4-L5 disc protrusion with moderate left foraminal stenosis impinging the exiting L5 nerve root, plus mild facet arthropathy at multiple levels. She has previously tried 12 weeks of physical therapy, NSAIDs, gabapentin 600 milligrams three times daily, and duloxetine 60 milligrams daily, with only partial relief. Today's pain rating is 7 out of 10. Numbness and tingling along the posterolateral left leg. No bowel or bladder dysfunction. No saddle anesthesia. No constitutional symptoms.
Assessment: chronic left L5 radiculopathy secondary to L4-L5 disc protrusion with moderate left foraminal stenosis, suboptimal response to conservative measures and oral neuropathic agents, appropriate candidate for transforaminal epidural steroid injection. Plan: schedule fluoroscopically guided left L4-L5 transforaminal epidural steroid injection of 80 milligrams methylprednisolone and 1 milliliter of 1 percent lidocaine, continue gabapentin and duloxetine, continue active home exercise program, hold any NSAID 5 days before procedure if patient is on one, consent obtained, post-procedure pain diary, follow-up 2 weeks after procedure for response assessment.
Established patient consult, high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['M54.16', 'M54.17', 'M54.1', 'G55'],
        ['M51.16', 'M51.26', 'M51.27'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      cptProcsAnyOf: ['64483', '64484'],
      rxDrugsAnyOf: [['gabapentin'], ['duloxetine']],
    },
  },
  {
    tag: 'PM2',
    specialty: 'pain-management',
    specialtyLabel: 'Pain Management',
    title: 'Post-herpetic neuralgia — gabapentin start',
    script: `
Patient is a 68-year-old male presenting with persistent right T6 dermatomal neuropathic pain four months after a documented episode of right thoracic herpes zoster. The acute vesicular rash resolved with a 7-day course of valacyclovir but he was left with severe burning and electric-shock-like pain in the same dermatomal distribution that has not improved. Pain is rated 8 out of 10 currently, interferes significantly with sleep. Allodynia is present such that even light contact from clothing is painful. Past medical history significant for type 2 diabetes mellitus controlled on metformin, hyperlipidemia, and recent unprovoked deep vein thrombosis status post 6 months of anticoagulation with rivaroxaban that was completed last month. No current bleeding diathesis. Renal function adequate with eGFR 64. He is not on any other neuropathic agents currently.
Assessment: post-herpetic neuralgia involving right T6 dermatome, severe and disabling, refractory to time alone. Plan: start gabapentin titration, 100 milligrams orally three times daily for 3 days, then 300 milligrams three times daily for 3 days, then increase by 300 milligrams every 3 days as tolerated up to a target of 1800 milligrams per day in three divided doses, also prescribe 5 percent lidocaine patches, one to three patches over the affected area for up to 12 hours daily, counsel on common gabapentin side effects of sedation, dizziness, and peripheral edema, follow-up in 3 weeks for titration and response assessment.
Established patient, moderate-to-high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['B02.22', 'B02.29', 'G53.0'],
        ['E11.9'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      rxDrugsAnyOf: [['gabapentin'], ['lidocaine']],
    },
  },

  // ── Weight Management ───────────────────────────────────────────────
  {
    tag: 'WM1',
    specialty: 'weight-management',
    specialtyLabel: 'Weight Management',
    title: 'Semaglutide start — GLP-1 thyroid + pancreatitis screen',
    script: `
Patient is a 42-year-old female with BMI 38 and three obesity-associated comorbidities, presenting for initial weight-management consultation. She has failed two prior medically-supervised dietary attempts, each achieving less than 5 percent loss with regain. Comorbidities include type 2 diabetes mellitus with A1c 7.6 on metformin 1000 milligrams twice daily, obstructive sleep apnea on nightly CPAP, and dyslipidemia on atorvastatin 40 milligrams daily. Patient explicitly denies personal or family history of medullary thyroid carcinoma or multiple endocrine neoplasia type 2. No personal or family history of pancreatitis. No history of gallbladder disease. Recent labs: lipase 24, amylase 28, comprehensive metabolic panel normal, TSH 1.4, calcitonin not indicated absent risk factors.
Assessment: class 2 obesity with appropriate comorbidities and prior failure of structured medical interventions, no contraindications to GLP-1 receptor agonist therapy. Plan: initiate semaglutide weekly subcutaneous injection at 0.25 milligrams weekly for 4 weeks, then 0.5 milligrams weekly for 4 weeks, then escalate up to a maintenance dose of 2.4 milligrams weekly per FDA-approved Wegovy titration, counsel extensively that semaglutide is contraindicated in personal or family history of medullary thyroid carcinoma or MEN-2, counsel on the increased risk of acute pancreatitis, dose-limiting nausea, vomiting, and constipation, baseline weight today is 102 kilograms, target initial loss is 5 to 10 percent over 3 months, dietary and lifestyle plan reviewed, return in 4 weeks for tolerance check.
New patient consult, moderate-to-high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['E66.01', 'E66.9'],
        ['E11.9', 'E11.65'],
        ['G47.33'],
        ['E78.5', 'E78.4'],
      ],
      cptEmAnyOf: ['99204', '99205'],
      rxDrugsAnyOf: [['semaglutide', 'wegovy', 'ozempic'], ['metformin'], ['atorvastatin']],
      rxSafetyRules: [
        {
          label: 'GLP-1 thyroid / MEN-2 contraindication',
          pattern: /(?:medullary thyroid|MEN-2|MEN 2|thyroid)/i,
          required: false,
        },
        {
          label: 'GLP-1 pancreatitis screen',
          pattern: /(?:pancreatit)/i,
          required: false,
        },
      ],
    },
  },
  {
    tag: 'WM2',
    specialty: 'weight-management',
    specialtyLabel: 'Weight Management',
    title: 'Tirzepatide titration — month 3 follow-up',
    script: `
Patient is a 49-year-old male returning for 3-month follow-up on tirzepatide therapy for class 1 obesity with metabolic syndrome. He started tirzepatide at 2.5 milligrams weekly three months ago, escalated to 5 milligrams weekly one month ago. Starting weight at initiation was 96 kilograms with BMI 32. Current weight today is 88 kilograms, representing an 8 kilogram loss or approximately 8 percent total body weight loss in 12 weeks. He tolerates the medication well with only mild nausea on the day of the injection and one episode of mild constipation that resolved with hydration. No vomiting, no signs of pancreatitis. Comorbidities: type 2 diabetes mellitus, A1c at baseline 8.1, today's A1c is 6.4 representing a significant improvement, hypertension on lisinopril 20 milligrams daily and amlodipine 5 milligrams daily, blood pressure today 124 over 78. Family history negative for medullary thyroid carcinoma and MEN-2. No personal history of pancreatitis or gallstones.
Assessment: excellent response to tirzepatide at 5 milligrams weekly with 8 percent weight loss and major A1c improvement, target weight loss trajectory on track, no concerning side effects. Plan: increase tirzepatide to 7.5 milligrams weekly, continue metformin, continue antihypertensives, hold any further dose escalation pending 1-month tolerance and weight response, repeat A1c and lipid panel in 3 months, follow-up at 4 weeks for tolerance check.
Established patient, moderate MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['E66.01', 'E66.9', 'E66.811', 'E66.812'],
        ['E11.65', 'E11.9'],
        ['I10'],
      ],
      cptEmAnyOf: ['99213', '99214'],
      rxDrugsAnyOf: [['tirzepatide', 'mounjaro', 'zepbound'], ['metformin'], ['lisinopril'], ['amlodipine']],
    },
  },

  // ── Bariatric Surgery ───────────────────────────────────────────────
  {
    tag: 'BS1',
    specialty: 'bariatric-surgery',
    specialtyLabel: 'Bariatric Surgery',
    title: 'Month 6 post-RYGB — calcium carbonate switch (LOAD-BEARING)',
    script: `
Patient is a 45-year-old female at month 6 post laparoscopic Roux-en-Y gastric bypass, returning for routine follow-up. She has lost approximately 44 kilograms from a pre-operative weight of 132 kilograms to a current weight of 88 kilograms, representing approximately 67 percent excess weight loss. She tolerates a regular bariatric-appropriate diet, eats protein first, and reports 80 ounces of fluids daily between meals. She is exercising 60 minutes of walking plus strength training three times weekly. Importantly, on review of her current supplement regimen, she switched three months ago from calcium citrate to calcium carbonate 1200 milligrams twice daily because the citrate was more expensive at her pharmacy. She is also taking a bariatric multivitamin twice daily, sublingual vitamin B12 1000 micrograms daily, vitamin D3 5000 international units daily, and elemental iron 65 milligrams daily. She reports occasional post-prandial dumping-syndrome symptoms with sugar but has learned to avoid simple carbohydrates. Today's A1c is 5.6, off all diabetes medications since postoperative day 1, representing T2DM remission. Blood pressure is 122 over 74.
Assessment: month-6 post-RYGB with excellent weight loss trajectory and durable T2DM remission. Critical issue: inappropriate calcium supplementation with carbonate rather than citrate post-Roux-en-Y. Post-bypass anatomy bypasses the acidic gastric environment required to dissolve calcium carbonate, making it functionally unabsorbed and placing the patient at risk for secondary hyperparathyroidism and accelerated bone loss. Plan: discontinue calcium carbonate immediately and switch to calcium citrate 1500 milligrams daily split into divided doses since absorption is limited per dose, continue bariatric multivitamin, B12, D3, and iron supplementation, dietary counseling reinforced, follow-up in 3 months.
Established post-op patient, moderate-to-high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['Z98.84'],
        ['Z90.3'],
      ],
      cptEmAnyOf: ['99214', '99215'],
      rxDrugsAnyOf: [
        ['calcium carbonate'],
        ['calcium citrate'],
        ['cyanocobalamin', 'vitamin b12'],
      ],
      rxSafetyRules: [
        {
          label: 'Calcium carbonate post-RYGB hard safety bullet',
          pattern: /(?:calcium\s+carbonate.*(?:contraindicat|non-substitut|post-RYGB|bypass|citrate)|carbonate.*bypass|carbonate.*citrate|citrate.*carbonate)/i,
          required: true,
        },
      ],
    },
  },
  {
    tag: 'BS2',
    specialty: 'bariatric-surgery',
    specialtyLabel: 'Bariatric Surgery',
    title: 'POD 5 post-RYGB — leak + dehydration workup',
    script: `
Patient is a 47-year-old female on postoperative day 5 after an uncomplicated laparoscopic Roux-en-Y gastric bypass, returning to clinic with concerning symptoms. She has persistent left upper quadrant pain rated 5 out of 10, started yesterday, that does not radiate. Her oral intake has been poor for 48 hours with only 16 ounces of fluids daily compared to a 64-ounce target. She had two episodes of non-bloody emesis yesterday after attempting a protein shake. She reports tachycardia at home with home monitor readings of heart rate 110 to 115 and a low-grade temperature of 99.8 degrees Fahrenheit. No fevers above 100.4, no shoulder-tip pain, no chest pain. Exam today: temperature 99.6, heart rate 112, blood pressure 102 over 68. Mucous membranes dry. Mild left upper quadrant tenderness without rebound or guarding. Surgical incisions are clean, dry, and intact. Labs drawn today show WBC 14.2 with left shift, hemoglobin 10.8, BUN 32 increased from the admission baseline of 14, creatinine 1.4 increased from the admission baseline of 0.8, lactate 2.6, and CRP 142.
Assessment: postoperative day 5 post-Roux-en-Y gastric bypass with high suspicion for anastomotic leak versus intra-abdominal abscess based on tachycardia, left upper quadrant pain, leukocytosis with left shift, low-grade fever, elevated CRP, plus secondary acute kidney injury with creatinine doubled from baseline and clinical dehydration. Plan: urgent CT abdomen pelvis with oral and IV contrast pending, admit for IV hydration, NPO, empiric piperacillin-tazobactam 3.375 grams IV every 6 hours, IV pantoprazole continuous infusion, enoxaparin 40 milligrams subcutaneous twice daily for venous thromboembolism prophylaxis since patient is now inpatient, acetaminophen and low-dose IV opioid as needed avoiding NSAIDs lifelong post-RYGB for marginal ulcer prevention, surgery team to evaluate based on CT result.
Initial hospital care, high MDM, approximately 45 minutes.
`.trim(),
    expect: {
      icdAnyOf: [
        ['K91.83', 'K91.89', 'T81.4XXA', 'T81.40XA', 'T81.49XA'],
        ['N17.9', 'N17.0', 'N17.8'],
        ['E86.0', 'E86.9'],
        ['R10.12', 'R10.13'],
      ],
      cptEmAnyOf: ['99221', '99222', '99223', '99232', '99233', '99214', '99215'],
      rxDrugsAnyOf: [
        ['piperacillin-tazobactam', 'piperacillin/tazobactam', 'zosyn'],
        ['pantoprazole'],
        ['enoxaparin', 'lovenox'],
      ],
    },
  },

  // ── Vascular Surgery ────────────────────────────────────────────────
  {
    tag: 'VS1',
    specialty: 'vascular-surgery',
    specialtyLabel: 'Vascular Surgery',
    title: 'TIA + 85% carotid — prasugrel contraindication (LOAD-BEARING)',
    script: `
Patient is a 72-year-old right-handed male presenting 8 days after a transient ischemic attack with sudden right arm weakness and dysarthria lasting approximately 20 minutes, fully resolved without intervention. Brain MRI at the time of presentation showed no acute infarct. Carotid imaging with duplex and CT angiography showed 85 percent stenosis of the left internal carotid artery at the bulb with associated plaque ulceration on CT angiography. He was started by neurology on aspirin 81 milligrams daily plus clopidogrel 75 milligrams daily for dual antiplatelet therapy planned for 21 days then continuing aspirin monotherapy long-term. He was also started on high-intensity statin atorvastatin 80 milligrams daily. Past medical history includes hypertension, hyperlipidemia, and type 2 diabetes on metformin 1000 milligrams twice daily plus dulaglutide weekly. He is a former smoker who quit 5 years ago with a 30 pack-year history. No prior stroke, no prior myocardial infarction. Recent 30-day event monitor placed by neurology showed no atrial fibrillation. Today's blood pressure 134 over 78. Left carotid bruit audible. No focal neurologic deficits today. NEUROLOGIC SAFETY NOTE: this patient has had a TIA 8 days ago, so any antiplatelet agent with a contraindication in prior TIA or stroke is ruled out, specifically prasugrel which is contraindicated in any prior TIA or stroke per TRITON-TIMI-38 boxed warning, and vorapaxar which is contraindicated in prior TIA, stroke, or intracranial hemorrhage per TRA-2P-TIMI-50 boxed warning.
Assessment: symptomatic 85 percent left internal carotid artery stenosis status post TIA 8 days ago, high risk for ipsilateral recurrent stroke, early revascularization indicated within 14 days of symptom onset per current AHA-ACC guidelines, type 2 diabetes, hypertension, hyperlipidemia, all stable. Plan: schedule carotid endarterectomy with intraoperative neuro monitoring within the next 6 days, continue aspirin and clopidogrel through surgery, continue atorvastatin 80 milligrams, blood pressure target less than 140 over 80 pre-op to preserve cerebral perfusion, do not substitute clopidogrel with prasugrel or vorapaxar given contraindication, continue metformin and dulaglutide.
New patient consult, very high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['G45.9', 'G45.8', 'G45.0', 'G45.1', 'G45.2'],
        ['I65.22', 'I65.21', 'I65.23'],
        ['I10'],
        ['E11.9', 'E11.65'],
      ],
      cptEmAnyOf: ['99204', '99205'],
      cptProcsAnyOf: ['93880'],
      rxDrugsAnyOf: [
        ['aspirin'],
        ['clopidogrel', 'plavix'],
        ['atorvastatin'],
      ],
      rxSafetyRules: [
        {
          label: 'Prasugrel / vorapaxar TIA-stroke contraindication',
          pattern: /(?:prasugrel|vorapaxar).*(?:contraindicat|TIA|stroke|history|prior|boxed warning|do not)/i,
          required: false,
        },
      ],
    },
  },
  {
    tag: 'VS2',
    specialty: 'vascular-surgery',
    specialtyLabel: 'Vascular Surgery',
    title: 'EVAR for 5.8 cm AAA — iohexol contrast/CKD (LOAD-BEARING)',
    script: `
Patient is a 72-year-old male admitted today for elective endovascular aneurysm repair of a known 5.8 centimeter infrarenal abdominal aortic aneurysm with 4 millimeter growth over the past 6 months, asymptomatic. Pre-operative CTA demonstrated suitable anatomy for endovascular repair including adequate proximal neck length of 18 millimeters, non-thrombotic neck, and patent bilateral iliac access. Anatomy meets the SVS practice guideline threshold for repair in men of 5.5 centimeters or greater. Past medical history significant for hypertension, hyperlipidemia, former smoker who quit in 2019, coronary artery disease with non-ST elevation myocardial infarction in 2021 currently on dual antiplatelet with aspirin 81 milligrams daily plus clopidogrel 75 milligrams daily, chronic kidney disease stage 3a with eGFR of 58 milliliters per minute per 1.73 meters squared. No iodine contrast allergy.
Procedure: endovascular aneurysm repair was performed using a bifurcated infrarenal modular endograft, Gore Excluder device. Bilateral percutaneous femoral access with ProGlide pre-close was achieved. Initial aortography used 25 milliliters of iohexol contrast. The main body was deployed below the lowest renal artery, contralateral gate was cannulated, and the contralateral limb was deployed to the right common iliac artery. The ipsilateral limb was extended to the left common iliac artery. Final angiography demonstrated full sac exclusion with no type I or type III endoleak. A small type II endoleak from a lumbar source was noted and will be managed conservatively with surveillance imaging. Total iohexol contrast used was 110 milliliters, characterized by the operator as the highest-risk-tolerable dose given baseline eGFR 58 and CKD stage 3a. Estimated blood loss 80 milliliters. Patient was extubated in the operating room and tolerated the procedure well.
Plan: inpatient overnight observation on telemetry, continue aspirin and clopidogrel, basic metabolic panel at 12 and 24 hours post-procedure for contrast-related acute kidney injury surveillance given the 110 milliliters of iohexol with baseline eGFR 58, complete blood count, surveillance CTA at 1 month, 6 months, 12 months, and annually thereafter, continue rosuvastatin 40 milligrams daily, continue lisinopril 20 milligrams daily but consider holding peri-procedurally pending stable post-procedure renal function.
Initial hospital care, high MDM.
`.trim(),
    expect: {
      icdAnyOf: [
        ['I71.4'],
        ['I25.2', 'I25.10'],
        ['N18.31', 'N18.30', 'N18.3'],
        ['Z79.02', 'Z79.01'],
        ['Z87.891'],
      ],
      cptEmAnyOf: ['99221', '99222', '99223', '99204', '99205'],
      cptProcsAnyOf: ['34703', '34701', '34702', '34705'],
      rxDrugsAnyOf: [
        ['aspirin'],
        ['clopidogrel', 'plavix'],
        ['rosuvastatin'],
        ['lisinopril'],
      ],
      rxSafetyRules: [
        {
          label: 'Iohexol contrast-AKI with eGFR<60 / lisinopril hold',
          pattern: /(?:iohexol|contrast).*(?:AKI|nephropathy|renal|eGFR|kidney|hold.*lisinopril|hold.*ACE)|(?:lisinopril|ACE).*hold.*(?:contrast|peri-procedure|renal)/i,
          required: true,
        },
      ],
    },
  },
];

export const INPUT_MODES = ['text_notes', 'voice_dictation', 'audio_upload'] as const;
export type InputMode = (typeof INPUT_MODES)[number];

/** Distinct count for the report headline. */
export const SCENARIO_COUNT = SCENARIOS.length;
