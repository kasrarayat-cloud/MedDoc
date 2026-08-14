// ============================================================================
// Round 3 PR-D — ICD-10-CM allowlist (audit A06-P0-002)
// ----------------------------------------------------------------------------
// Closes False Claims Act exposure: the AI codes layer (07a-icd-coding)
// previously emitted whatever code Claude picked subject only to a regex-
// shape check, so `Z99.999` (not a real code) and `Q9X.XX` (made up) would
// pass through to the doctor's billing-ready code list.
//
// SCOPE LIMITATION (intentional for pre-pilot)
// --------------------------------------------
// This is a STARTER SET — ~120 of the most-common ICD-10-CM codes covering
// pilot specialties (family medicine, internal medicine, pediatrics, OB/GYN,
// orthopedics, cardiology, psychiatry, pain management). It does NOT replace
// the full CMS list (~70 000 codes).
//
// PRE-PILOT SAFETY POSTURE: the validator drops codes NOT in this list,
// emits an audit row (CODING_COACH_REJECTED_INVALID_ICD), and surfaces the
// rejection in the UI as "AI suggested a code (XYZ) that's not on our
// verified list — removed". A code that is real but missing from the
// allowlist gets dropped (false negative) — clinically safer than letting
// hallucinated codes through (false positive on validity).
//
// PHASE 7 PATH (post-pilot): swap this file for a fs-loaded subset of
// the full CMS canonical list (icd10cm_codes_2026.txt, ~1.4 MB). Same
// validator API; the call sites don't change.
// ============================================================================

const STARTER_ICD10_CODES: ReadonlyArray<string> = [
  // === Family / internal med — most common visit reasons ===
  'I10', // Essential (primary) hypertension
  'E11.9', // Type 2 diabetes mellitus without complications
  'E11.65', // Type 2 diabetes mellitus with hyperglycemia
  'E11.22', // Type 2 diabetes mellitus with diabetic chronic kidney disease
  'E78.5', // Hyperlipidemia, unspecified
  'E78.00', // Pure hypercholesterolemia, unspecified
  'E03.9', // Hypothyroidism, unspecified
  'E66.9', // Obesity, unspecified
  'E66.01', // Morbid (severe) obesity due to excess calories
  'I25.10', // ASCVD without angina pectoris
  'I48.91', // Unspecified atrial fibrillation
  'I50.9', // Heart failure, unspecified
  'J44.9', // COPD, unspecified
  'J45.40', // Moderate persistent asthma, uncomplicated
  'J45.909', // Unspecified asthma, uncomplicated
  'K21.9', // GERD without esophagitis
  'K57.30', // Diverticulosis of large intestine without perforation/abscess
  'K58.0', // IBS with diarrhea
  'K59.00', // Constipation, unspecified
  'N39.0', // Urinary tract infection, site not specified
  'R10.9', // Unspecified abdominal pain
  'R51.9', // Headache, unspecified
  'R50.9', // Fever, unspecified
  'R05.9', // Cough, unspecified
  'R06.02', // Shortness of breath
  'R07.9', // Chest pain, unspecified
  'R42', // Dizziness and giddiness
  'R53.83', // Other fatigue
  'R63.5', // Abnormal weight gain
  'R63.4', // Abnormal weight loss
  'Z00.00', // Encounter for general adult medical exam without abnormal findings
  'Z00.01', // Encounter for general adult medical exam with abnormal findings
  'Z23', // Encounter for immunization
  'Z11.59', // Encounter for screening for other viral diseases
  'Z79.4', // Long term (current) use of insulin
  'Z79.84', // Long term (current) use of oral hypoglycemic drugs
  'Z79.890', // Other long term (current) drug therapy
  'Z87.891', // Personal history of nicotine dependence

  // === Cardiology ===
  'I20.9', // Angina pectoris, unspecified
  'I21.9', // Acute myocardial infarction, unspecified
  'I25.2', // Old myocardial infarction
  'I63.9', // Cerebral infarction, unspecified
  'I65.29', // Occlusion/stenosis of unspecified carotid artery
  'I47.1', // Supraventricular tachycardia
  'I49.9', // Cardiac arrhythmia, unspecified

  // === Pulm / acute respiratory ===
  'J18.9', // Pneumonia, unspecified organism
  'J20.9', // Acute bronchitis, unspecified
  'J03.90', // Acute tonsillitis, unspecified
  'J02.9', // Acute pharyngitis, unspecified
  'J06.9', // Acute upper respiratory infection, unspecified
  'J21.9', // Acute bronchiolitis, unspecified
  'J11.1', // Influenza w/ other respiratory manifestations, unspecified virus
  'B34.9', // Viral infection, unspecified

  // === Pediatrics ===
  'Z00.121', // Encounter for routine child health exam w/ abnormal findings
  'Z00.129', // Encounter for routine child health exam w/o abnormal findings
  'Z00.110', // Health exam for newborn under 8 days old
  'P07.30', // Preterm newborn, unspecified weeks of gestation
  'H66.90', // Otitis media, unspecified, unspecified ear
  'H66.91', // Otitis media, unspecified, right ear
  'H66.92', // Otitis media, unspecified, left ear
  'R11.10', // Vomiting, unspecified
  'R11.2', // Nausea with vomiting, unspecified
  'A09', // Infectious gastroenteritis and colitis, unspecified
  'B07.9', // Viral wart, unspecified

  // === OB/GYN ===
  'Z34.00', // Supervision of normal first pregnancy, unspecified trimester
  'Z34.80', // Supervision of other normal pregnancy, unspecified trimester
  'O09.90', // Supervision of high-risk pregnancy, unspecified trimester
  'Z32.01', // Encounter for pregnancy test, positive
  'N91.2', // Amenorrhea, unspecified
  'N92.0', // Excessive and frequent menstruation w/ regular cycle
  'N94.6', // Dysmenorrhea, unspecified
  'N95.1', // Menopausal and female climacteric states
  'O80', // Encounter for full-term uncomplicated delivery

  // === Orthopedics / MSK ===
  'M17.9', // Osteoarthritis of knee, unspecified
  'M16.9', // Osteoarthritis of hip, unspecified
  'M19.90', // Unspecified osteoarthritis, unspecified site
  'M54.5', // Low back pain (legacy — superseded by M54.50/51/59 in 2022+)
  'M54.50', // Low back pain, unspecified
  'M54.2', // Cervicalgia
  'M25.50', // Pain in unspecified joint
  'M75.100', // Unspecified rotator cuff tear or rupture, not specified as traumatic
  'S52.501A', // Unspecified fracture of right radius, initial encounter
  'S82.001A', // Unspecified fracture of right patella, initial encounter
  'S83.20XA', // Tear of unspecified meniscus, current injury, right knee, initial enc
  'M79.7', // Fibromyalgia

  // === Psychiatry / behavioral health ===
  'F32.9', // Major depressive disorder, single episode, unspecified
  'F32.A', // Depression, unspecified
  'F33.9', // Major depressive disorder, recurrent, unspecified
  'F41.1', // Generalized anxiety disorder
  'F41.9', // Anxiety disorder, unspecified
  'F43.10', // PTSD, unspecified
  'F43.23', // Adjustment disorder with mixed anxiety and depressed mood
  'F90.0', // ADHD, predominantly inattentive type
  'F90.1', // ADHD, predominantly hyperactive type
  'F90.2', // ADHD, combined type
  'F90.9', // ADHD, unspecified type
  'F31.9', // Bipolar disorder, unspecified
  'F84.0', // Autistic disorder
  'F50.81', // Binge eating disorder
  'F51.01', // Primary insomnia
  'G47.00', // Insomnia, unspecified

  // === Pain management / neurology ===
  'G89.29', // Other chronic pain
  'G89.4', // Chronic pain syndrome
  'R52', // Pain, unspecified
  'G43.909', // Migraine, unspecified, not intractable, w/o status migrainosus
  'G44.209', // Tension-type headache, unspecified, not intractable
  'M62.830', // Muscle spasm of back

  // === Skin / common derm ===
  'L70.0', // Acne vulgaris
  'L20.9', // Atopic dermatitis, unspecified
  'L23.9', // Allergic contact dermatitis, unspecified cause
  'L30.9', // Dermatitis, unspecified
  'L40.9', // Psoriasis, unspecified

  // === Common labs / screening ===
  'Z12.11', // Encounter for screening for malignant neoplasm of colon
  'Z12.31', // Encounter for screening mammogram for malignant neoplasm of breast
  'Z01.812', // Encounter for preprocedural laboratory examination
  'Z79.01', // Long term (current) use of anticoagulants

  // === Allergic / urticaria ===
  'T78.40XA', // Allergy, unspecified, initial encounter
  'L50.9', // Urticaria, unspecified
  'J30.9', // Allergic rhinitis, unspecified

  // === Weight Management cohort (2026-05-12) ===
  // Added with the L7a prompt fix that instructs the model to code
  // chronic comorbidities documented in PMH. Pre-fix the allowlist
  // dropped K76.0 / G47.33 silently even after the prompt began
  // emitting them — the rejection was invisible because audit rows
  // log "rejectedCodes" which require ICD-shape parse first.
  //
  // Scope: comorbidities that routinely co-document on a weight-loss
  // clinic visit (NAFLD / OSA / GLP-1 surveillance gaps) and the
  // Z68.x BMI ladder + chronic-Rx Z-codes that capture HCC risk-
  // adjustment for these cohorts.
  'K76.0',     // Fatty (change of) liver, not elsewhere classified (NAFLD)
  'K76.89',    // Other specified diseases of liver
  'K85.90',    // Acute pancreatitis without necrosis or infection, unspecified
  'K85.91',    // Acute pancreatitis with uninfected necrosis
  'K80.20',    // Calculus of gallbladder without cholecystitis, without obstruction (GLP-1 watch)
  'G47.33',    // Obstructive sleep apnea (adult) (pediatric)
  'G47.30',    // Sleep apnea, unspecified
  // I25.2 (old MI) is already in the cardiology block above — not re-added.
  // CKD stages — N18.3 was the pre-2018 spelling for "stage 3"; CMS now
  // uses the more-specific N18.30 / .31 / .32 split. We carry both because
  // older NLP / draft outputs still occasionally emit N18.3 verbatim.
  'N18.1',     // Chronic kidney disease, stage 1
  'N18.2',     // Chronic kidney disease, stage 2 (mild)
  'N18.30',    // Chronic kidney disease, stage 3 unspecified
  'N18.31',    // Chronic kidney disease, stage 3a
  'N18.32',    // Chronic kidney disease, stage 3b
  'N18.4',     // Chronic kidney disease, stage 4 (severe)
  'N18.5',     // Chronic kidney disease, stage 5
  'N18.6',     // End stage renal disease
  'N18.9',     // Chronic kidney disease, unspecified
  // BMI ladder — class III obesity / class II / class I / overweight
  'Z68.30',    // BMI 30.0-30.9, adult
  'Z68.31',    // BMI 31.0-31.9, adult
  'Z68.32',    // BMI 32.0-32.9, adult
  'Z68.33',    // BMI 33.0-33.9, adult
  'Z68.34',    // BMI 34.0-34.9, adult
  'Z68.35',    // BMI 35.0-35.9, adult
  'Z68.36',    // BMI 36.0-36.9, adult
  'Z68.37',    // BMI 37.0-37.9, adult
  'Z68.38',    // BMI 38.0-38.9, adult
  'Z68.39',    // BMI 39.0-39.9, adult
  'Z68.41',    // BMI 40.0-44.9, adult
  'Z68.42',    // BMI 45.0-49.9, adult
  'Z68.43',    // BMI 50.0-59.9, adult
  'Z68.44',    // BMI 60.0-69.9, adult
  'Z68.45',    // BMI 70 or greater, adult
  // Z79.4 / Z79.84 / Z79.890 already present in the family-med block; not
  // re-added. Z79.899 is the catch-all "other long-term drug therapy"
  // that 07a now emits for chronic statin / ACE-I use captured from the
  // medication list.
  'Z79.899',   // Other long-term (current) drug therapy
  'Z51.81',    // Encounter for therapeutic drug level monitoring

  // === Bariatric Surgery cohort (2026-05-12) ===
  // Added with the `bariatric-surgery` specialty. Covers post-op status,
  // postsurgical syndromes, common early-postop complications, and the
  // E61.x nutritional-deficiency block specific to malabsorption after
  // bypass / sleeve / BPD-DS. T81.4xxA is the FCA-exposure code — it's
  // billable on a post-op visit where infection at the surgical site is
  // documented; missing it was the dominant gap on pre-fix bariatric
  // notes per the QA cohort.
  'Z98.84',    // Bariatric surgery status
  'Z90.3',     // Acquired absence of stomach [part of]  (post-sleeve / -bypass)
  'K91.1',     // Postgastric surgery syndromes
  'K91.2',     // Postsurgical malabsorption, not elsewhere classified
  'K91.83',    // Postprocedural hematoma and seroma of a digestive system organ following a digestive system procedure
  'K91.86',    // Retained cholelithiasis following cholecystectomy
  'K94.20',    // Gastrostomy complication, unspecified
  'K94.21',    // Gastrostomy hemorrhage
  'K94.22',    // Gastrostomy infection
  'K94.23',    // Gastrostomy malfunction
  // Mechanical bowel obstruction — small-bowel + adhesive cases are the
  // dominant post-bariatric obstruction etiologies (internal hernia at
  // the Petersen's space + mesenteric defects post-RYGB).
  'K56.0',     // Paralytic ileus
  'K56.1',     // Intussusception
  'K56.2',     // Volvulus
  'K56.5',     // Intestinal adhesions [bands] with obstruction (postinfection)
  'K56.60',    // Unspecified intestinal obstruction
  'K56.69',    // Other intestinal obstruction
  'K56.7',     // Ileus, unspecified
  // Nutritional deficiencies — E61.x specific deficiencies + E63.9
  // catch-all. The bariatric multivitamin / supplementation regimen
  // exists precisely to prevent these; the codes get billable when a
  // patient presents with documented low-level vitamin or mineral on
  // labs.
  'E61.0',     // Copper deficiency
  'E61.1',     // Iron deficiency
  'E61.2',     // Magnesium deficiency
  'E61.3',     // Manganese deficiency
  'E61.4',     // Chromium deficiency
  'E61.5',     // Molybdenum deficiency
  'E61.6',     // Vanadium deficiency
  'E61.7',     // Deficiency of multiple nutrient elements
  'E63.9',     // Nutritional deficiency, unspecified
  'E55.9',     // Vitamin D deficiency, unspecified
  'E56.9',     // Vitamin deficiency, unspecified
  'E53.8',     // Deficiency of other specified B group vitamins (B12 sometimes coded here)
  'D51.0',     // Vitamin B12 deficiency anemia due to intrinsic factor deficiency
  'D51.1',     // Vitamin B12 deficiency anemia due to selective vitamin B12 malabsorption with proteinuria
  'D51.8',     // Other vitamin B12 deficiency anemias
  'D51.9',     // Vitamin B12 deficiency anemia, unspecified
  'D50.9',     // Iron deficiency anemia, unspecified
  // Procedure-complication codes the model should reach for when leak /
  // wound / infection signs are documented post-op.
  'T81.40XA',  // Infection following a procedure, unspecified, initial encounter
  'T81.41XA',  // Infection following a procedure, superficial incisional surgical site
  'T81.42XA',  // Infection following a procedure, deep incisional surgical site
  'T81.43XA',  // Infection following a procedure, organ and space surgical site
  'T81.49XA',  // Infection following a procedure, sepsis (organ + space)
  'T81.30XA',  // Disruption of wound, unspecified, initial encounter
  'T81.31XA',  // Disruption of external operation (surgical) wound, NEC, initial encounter
  'T81.32XA',  // Disruption of internal operation (surgical) wound, NEC, initial encounter
  // Dumping syndrome — post-bypass specific, both early + late forms
  // share the same R10.x / R11 family root.
  'K91.89',    // Other postprocedural complications and disorders of digestive system (covers dumping NEC)

  // === Vascular Surgery cohort (2026-05-12) ===
  // Added with the `vascular-surgery` specialty. Covers the I65-I77
  // arterial families (atherosclerosis, aneurysm, dissection, other),
  // the I82-I83 venous families, G45 TIA, peripheral-bypass status,
  // dialysis-access mechanical complications, and chronic-Rx Z-codes
  // for antiplatelet / anticoagulant. The block deliberately includes
  // the laterality-specific 4th and 5th digits (I70.211 right LE
  // claudication, I70.212 left, I70.213 bilateral, I70.219 unspecified)
  // because the L7a model emits the lateralized form when the SOAP
  // names a side — the unsided I70.21 alone would silently drop the
  // lateralized code at the allowlist.

  // ── Arterial atherosclerosis (I70.x — full breakdown) ──────────────
  'I70.0',     // Atherosclerosis of aorta
  'I70.1',     // Atherosclerosis of renal artery
  'I70.201',   // Unspecified atherosclerosis of native arteries of extremities, right leg
  'I70.202',   // … left leg
  'I70.203',   // … bilateral legs
  'I70.208',   // … other extremity
  'I70.209',   // … unspecified extremity
  'I70.211',   // Atherosclerosis of native arteries of extremities with intermittent claudication, right leg
  'I70.212',   // … left leg
  'I70.213',   // … bilateral legs
  'I70.218',   // … other extremity
  'I70.219',   // … unspecified extremity
  'I70.221',   // Atherosclerosis of native arteries of extremities with rest pain, right leg
  'I70.222',   // … left leg
  'I70.223',   // … bilateral legs
  'I70.228',   // … other extremity
  'I70.229',   // … unspecified extremity
  'I70.231',   // Atherosclerosis with ulceration, right leg, calf
  'I70.232',   // … right leg, ankle (other commonly-emitted laterality combo carried)
  'I70.233',   // … right leg, heel and midfoot
  'I70.234',   // … right leg, other site of foot
  'I70.235',   // … right leg, other / unspecified site
  'I70.241',   // … left leg, calf
  'I70.244',   // … left leg, other site of foot
  'I70.245',   // … left leg, other / unspecified site
  'I70.25',    // Atherosclerosis of native arteries of extremities with gangrene
  'I70.261',   // … with gangrene, right leg
  'I70.262',   // … with gangrene, left leg
  'I70.263',   // … with gangrene, bilateral legs
  'I70.268',   // … with gangrene, other extremity
  'I70.269',   // … with gangrene, unspecified extremity
  'I70.301',   // Unspecified atherosclerosis of unspecified type of bypass graft(s) of the extremities, right leg
  'I70.302',   // … left leg
  'I70.311',   // Atherosclerosis of unspec bypass graft of right leg with intermittent claudication
  'I70.312',   // … left leg
  'I70.71',    // Atherosclerosis of other type of bypass graft(s) of the extremities with rest pain
  'I70.79',    // Other atherosclerosis of other type of bypass graft(s) of the extremities
  'I70.8',     // Atherosclerosis of other arteries
  'I70.90',    // Unspecified atherosclerosis
  'I70.92',    // Chronic total occlusion of artery of the extremities

  // ── Peripheral vascular disease (I73.x) ────────────────────────────
  'I73.00',    // Raynaud syndrome without gangrene
  'I73.01',    // Raynaud syndrome with gangrene
  'I73.1',     // Thromboangiitis obliterans (Buerger disease)
  'I73.81',    // Erythromelalgia
  'I73.89',    // Other specified peripheral vascular diseases
  'I73.9',     // Peripheral vascular disease, unspecified

  // ── Arterial embolism / thrombosis (I74.x) ─────────────────────────
  'I74.01',    // Saddle embolus of abdominal aorta
  'I74.09',    // Other arterial embolism and thrombosis of abdominal aorta
  'I74.10',    // Embolism and thrombosis of unspecified parts of aorta
  'I74.11',    // Embolism and thrombosis of thoracic aorta
  'I74.19',    // Embolism and thrombosis of other parts of aorta
  'I74.2',     // Embolism and thrombosis of arteries of the upper extremities
  'I74.3',     // Embolism and thrombosis of arteries of the lower extremities
  'I74.4',     // Embolism and thrombosis of arteries of extremities, unspecified
  'I74.5',     // Embolism and thrombosis of iliac artery
  'I74.8',     // Embolism and thrombosis of other arteries
  'I74.9',     // Embolism and thrombosis of unspecified artery

  // ── Other arterial disorders (I77.x) ───────────────────────────────
  'I77.0',     // Arteriovenous fistula, acquired
  'I77.1',     // Stricture of artery
  'I77.2',     // Rupture of artery
  'I77.3',     // Arterial fibromuscular dysplasia
  'I77.4',     // Celiac artery compression syndrome
  'I77.5',     // Necrosis of artery
  'I77.6',     // Arteritis, unspecified
  'I77.70',    // Dissection of unspecified artery
  'I77.71',    // Dissection of carotid artery
  'I77.72',    // Dissection of iliac artery
  'I77.73',    // Dissection of renal artery
  'I77.74',    // Dissection of vertebral artery
  'I77.75',    // Dissection of other precerebral arteries
  'I77.76',    // Dissection of artery of upper extremity
  'I77.77',    // Dissection of artery of lower extremity
  'I77.79',    // Dissection of other specified artery
  'I77.810',   // Thoracic aortic ectasia
  'I77.811',   // Abdominal aortic ectasia
  'I77.812',   // Thoracoabdominal aortic ectasia
  'I77.89',    // Other specified disorders of arteries and arterioles
  'I77.9',     // Disorder of arteries and arterioles, unspecified

  // ── Aortic aneurysm / dissection (I71.x, I72.x) ────────────────────
  'I71.00',    // Dissection of unspecified site of aorta
  'I71.01',    // Dissection of thoracic aorta
  'I71.02',    // Dissection of abdominal aorta
  'I71.03',    // Dissection of thoracoabdominal aorta
  'I71.1',     // Thoracic aortic aneurysm, ruptured
  'I71.2',     // Thoracic aortic aneurysm, without rupture
  'I71.3',     // Abdominal aortic aneurysm, ruptured
  'I71.4',     // Abdominal aortic aneurysm, without rupture
  'I71.5',     // Thoracoabdominal aortic aneurysm, ruptured
  'I71.6',     // Thoracoabdominal aortic aneurysm, without rupture
  'I71.8',     // Aortic aneurysm of unspecified site, ruptured
  'I71.9',     // Aortic aneurysm of unspecified site, without rupture
  'I72.0',     // Aneurysm of carotid artery
  'I72.1',     // Aneurysm of artery of upper extremity
  'I72.2',     // Aneurysm of renal artery
  'I72.3',     // Aneurysm of iliac artery
  'I72.4',     // Aneurysm of artery of lower extremity
  'I72.5',     // Aneurysm of other precerebral arteries
  'I72.6',     // Aneurysm of vertebral artery
  'I72.8',     // Aneurysm of other specified arteries
  'I72.9',     // Aneurysm of unspecified site

  // ── Carotid + cerebrovascular (I65 / I66 / I63 / G45) ──────────────
  'I65.0',     // Occlusion and stenosis of vertebral artery
  'I65.1',     // Occlusion and stenosis of basilar artery
  'I65.21',    // Occlusion and stenosis of right carotid artery
  'I65.22',    // Occlusion and stenosis of left carotid artery
  'I65.23',    // Occlusion and stenosis of bilateral carotid arteries
  // I65.29 already present above (pre-existing cerebrovascular block)
  'I65.8',     // Occlusion and stenosis of other precerebral arteries
  'I65.9',     // Occlusion and stenosis of unspecified precerebral artery
  'I66.01',    // Occlusion and stenosis of right MCA
  'I66.02',    // Occlusion and stenosis of left MCA
  'I66.03',    // Occlusion and stenosis of bilateral MCAs
  'I63.00',    // Cerebral infarction due to thrombosis of unspecified precerebral artery
  'I63.10',    // Cerebral infarction due to embolism of unspecified precerebral artery
  'I63.20',    // Cerebral infarction due to unspecified occlusion or stenosis of precerebral arteries
  'I63.30',    // Cerebral infarction due to thrombosis of unspecified cerebral artery
  'I63.40',    // Cerebral infarction due to embolism of unspecified cerebral artery
  'I63.50',    // Cerebral infarction due to unspecified occlusion or stenosis of cerebral arteries
  'I63.6',     // Cerebral infarction due to cerebral venous thrombosis, nonpyogenic
  'I63.8',     // Other cerebral infarction
  // I63.9 already present above (pre-existing cerebrovascular block)
  'G45.0',     // Vertebro-basilar artery syndrome
  'G45.1',     // Carotid artery syndrome (hemispheric)
  'G45.2',     // Multiple and bilateral precerebral artery syndromes
  'G45.3',     // Amaurosis fugax
  'G45.4',     // Transient global amnesia
  'G45.8',     // Other transient cerebral ischemic attacks and related syndromes
  'G45.9',     // Transient cerebral ischemic attack, unspecified

  // ── Venous (I82.x / I83.x / I80.x / I87.x) ─────────────────────────
  // The full venous block lands here (Vein Care work referenced in the
  // brief had not yet shipped to main when this PR landed).
  'I80.00',    // Phlebitis and thrombophlebitis of unspecified superficial vessels of lower extremities
  'I80.01',    // … right LE
  'I80.02',    // … left LE
  'I80.03',    // … bilateral LE
  'I80.10',    // Phlebitis and thrombophlebitis of unspecified femoral vein
  'I80.11',    // … right femoral vein
  'I80.12',    // … left femoral vein
  'I80.13',    // … bilateral femoral veins
  'I80.211',   // Phlebitis and thrombophlebitis of right iliac vein
  'I80.212',   // … left iliac vein
  'I80.221',   // Phlebitis and thrombophlebitis of right popliteal vein
  'I80.222',   // … left popliteal vein
  'I80.231',   // Phlebitis and thrombophlebitis of right tibial vein
  'I80.232',   // … left tibial vein
  'I80.291',   // Phlebitis and thrombophlebitis of other deep vessels of right LE
  'I80.292',   // … left LE
  'I80.3',     // Phlebitis and thrombophlebitis of LE, unspecified
  'I82.401',   // Acute embolism and thrombosis of unspecified deep veins of right LE
  'I82.402',   // … left LE
  'I82.403',   // … bilateral LE
  'I82.4Y1',   // Acute embolism and thrombosis of unspecified deep veins of proximal LE, right
  'I82.4Z1',   // … distal LE, right
  'I82.501',   // Chronic embolism and thrombosis of unspecified deep veins of right LE
  'I82.502',   // … left LE
  'I82.503',   // … bilateral LE
  'I82.621',   // Acute embolism and thrombosis of deep veins of right upper extremity
  'I82.622',   // … left upper extremity
  'I82.890',   // Other acute embolism and thrombosis of other specified veins
  'I82.91',    // Embolism and thrombosis of unspecified vein
  'I83.001',   // Varicose veins of right LE with ulcer of thigh
  'I83.002',   // … with ulcer of calf
  'I83.003',   // … with ulcer of ankle
  'I83.004',   // … with ulcer of heel and midfoot
  'I83.008',   // … with ulcer of other part of LE
  'I83.011',   // Varicose veins of left LE with ulcer of thigh
  'I83.012',   // … calf
  'I83.013',   // … ankle
  'I83.014',   // … heel and midfoot
  'I83.018',   // … other part of LE
  'I83.10',    // Varicose veins of unspecified LE with inflammation
  'I83.11',    // … right LE with inflammation
  'I83.12',    // … left LE with inflammation
  'I83.20',    // Varicose veins of unspecified LE with both ulcer and inflammation
  'I83.21',    // … right LE with both ulcer and inflammation
  'I83.22',    // … left LE with both ulcer and inflammation
  // NOTE: the bare 5-char subcategory I83.81 is intentionally NOT allowlisted —
  // it is a non-billable category header whose billable children (…810/811/812/
  // 813) are below; a model that emits the bare code is correctly dropped.
  'I83.810',   // Varicose veins of unspecified LE with pain
  'I83.811',   // Varicose veins of right LE with pain
  'I83.812',   // … left LE
  'I83.813',   // … bilateral LE
  'I83.891',   // Varicose veins of right LE with other complications (swelling/heaviness/edema)
  'I83.892',   // … left LE
  'I83.893',   // … bilateral LE
  'I83.899',   // … unspecified LE
  'I83.90',    // Asymptomatic varicose veins of unspecified LE
  'I83.91',    // … right LE
  'I83.92',    // … left LE
  'I83.93',    // … bilateral LE
  'I87.001',   // Postthrombotic syndrome without complications, right LE
  'I87.002',   // … left LE
  'I87.003',   // … bilateral LE
  'I87.011',   // Postthrombotic syndrome with ulcer of right LE
  'I87.012',   // … left LE
  'I87.013',   // … bilateral LE
  'I87.2',     // Venous insufficiency (chronic) (peripheral)
  'I87.30',    // Chronic venous hypertension (idiopathic) without complications of unspecified LE
  'I87.31',    // … right LE
  'I87.32',    // … left LE
  'I87.33',    // … bilateral LE
  'I87.8',     // Other specified disorders of veins
  'I87.9',     // Disorder of vein, unspecified

  // ── Status codes — vascular implants + dialysis dependence ─────────
  'Z95.5',     // Presence of coronary angioplasty implant and graft
  'Z95.811',   // Presence of heart assist device
  'Z95.820',   // Presence of peripheral vascular graft
  'Z95.828',   // Presence of other vascular implants and grafts
  'Z95.9',     // Presence of cardiac and vascular implant and graft, unspecified
  'Z45.89',    // Encounter for adjustment and management of other implanted devices
  'Z99.2',     // Dependence on renal dialysis

  // ── Mechanical complications of vascular / dialysis devices ────────
  'T82.41XA',  // Breakdown (mechanical) of dialysis catheter, initial encounter
  'T82.42XA',  // Displacement of dialysis catheter
  'T82.43XA',  // Leakage of dialysis catheter
  'T82.49XA',  // Other complication of dialysis catheter
  'T82.510A',  // Breakdown of surgically created arteriovenous fistula
  'T82.520A',  // Displacement of surgically created arteriovenous fistula
  'T82.530A',  // Leakage of surgically created arteriovenous fistula
  'T82.590A',  // Other mechanical complication of surgically created AV fistula
  'T82.510X',  // (shape carried — same family, X-suffix variant for completeness)
  'T82.61XA',  // Infection and inflammatory reaction due to cardiac valve prosthesis
  'T82.7XXA',  // Infection and inflammatory reaction due to other cardiac and vascular devices, implants and grafts
  'T82.818A',  // Embolism due to vascular prosthetic devices, implants and grafts
  'T82.828A',  // Fibrosis due to vascular prosthetic devices, implants and grafts
  'T82.838A',  // Hemorrhage due to vascular prosthetic devices, implants and grafts
  'T82.848A',  // Pain from vascular prosthetic devices, implants and grafts
  'T82.858A',  // Stenosis of vascular prosthetic devices, implants and grafts
  'T82.868A',  // Thrombosis due to vascular prosthetic devices, implants and grafts
  'T82.898A',  // Other specified complication of vascular prosthetic devices, implants and grafts
  'T85.71XA',  // Infection and inflammatory reaction due to peritoneal dialysis catheter
  // F-codes — smoking dependence (the BIGGEST PAD risk-factor modifier)
  // is documented in nearly every vascular consult.
  'F17.200',   // Nicotine dependence, unspecified, uncomplicated
  'F17.201',   // … in remission
  'F17.210',   // Nicotine dependence, cigarettes, uncomplicated
  'F17.211',   // … in remission
  'F17.218',   // … with other nicotine-induced disorders
  'F17.219',   // … with unspecified nicotine-induced disorders
  // Long-term anticoagulant / antiplatelet Z-codes — every PAD / post-
  // stent / post-bypass / post-EVAR patient carries one.
  'Z79.02',    // Long-term (current) use of antiplatelet/antithrombotic

  // === G1 deep-audit additions (2026-05-12) ===
  // Codes the L7a layer emitted in the deep-audit's 19-visit synthetic
  // run but which were missing from the allowlist (and therefore would
  // have been silently dropped if the model had picked them). Added
  // here so the L7a prompt extension that hoists these conditions can
  // produce codes that survive the post-LLM allowlist filter.

  // Heart failure subtypes — the existing I50.9 (unspecified) was the
  // only HF code present; pre-fix, "HFpEF" / "HFrEF" documentation
  // upstream had no specific allowlist landing spot. Audit-finding B3
  // (BPD-DS BMI 55 patient with HFpEF + NYHA Class II) is the index
  // reproduction.
  'I50.1',     // Left ventricular failure, unspecified
  'I50.20',    // Unspecified systolic (congestive) heart failure
  'I50.21',    // Acute systolic (congestive) heart failure (HFrEF acute)
  'I50.22',    // Chronic systolic (congestive) heart failure (HFrEF chronic)
  'I50.23',    // Acute on chronic systolic (congestive) heart failure
  'I50.30',    // Unspecified diastolic (congestive) heart failure (HFpEF)
  'I50.31',    // Acute diastolic (congestive) heart failure (HFpEF acute)
  'I50.32',    // Chronic diastolic (congestive) heart failure (HFpEF chronic)
  'I50.33',    // Acute on chronic diastolic (congestive) heart failure
  'I50.40',    // Unspecified combined systolic + diastolic heart failure
  'I50.41',    // Acute combined systolic + diastolic heart failure
  'I50.42',    // Chronic combined systolic + diastolic heart failure
  'I50.43',    // Acute on chronic combined systolic + diastolic heart failure

  // Acute kidney injury — audit-finding B4 (POD #5 RYGB with leak +
  // dehydration → Cr 1.4 from baseline 0.8) is the index reproduction.
  'N17.0',     // Acute kidney failure with tubular necrosis
  'N17.1',     // Acute kidney failure with acute cortical necrosis
  'N17.2',     // Acute kidney failure with medullary necrosis
  'N17.8',     // Other acute kidney failure
  'N17.9',     // Acute kidney failure, unspecified

  // Dehydration / volume depletion — common acute finding on every
  // post-bariatric leak workup + every CLI / ulcer presentation +
  // every elderly-fall workup. Audit-finding B4 driver.
  'E86.0',     // Dehydration
  'E86.1',     // Hypovolemia
  'E86.9',     // Volume depletion, unspecified

  // Site-specific abdominal pain — the existing R10.9 (unspecified)
  // catches everything but loses specificity for billing. B4 (LUQ
  // tenderness post-RYGB leak workup) wanted R10.12 / R10.13.
  'R10.10',    // Upper abdominal pain, unspecified
  'R10.11',    // Right upper quadrant pain
  'R10.12',    // Left upper quadrant pain
  'R10.13',    // Epigastric pain
  'R10.30',    // Lower abdominal pain, unspecified
  'R10.31',    // Right lower quadrant pain
  'R10.32',    // Left lower quadrant pain
  'R10.84',    // Generalized abdominal pain
  'R10.819',   // Abdominal tenderness, unspecified site

  // Personal-history Z-codes (Z86.7x family) — audit-finding B6
  // (POD #28 post-RYGB with prior provoked DVT — needed Z86.718) +
  // V2 (CEAP C6 ulcer with prior left iliofemoral DVT — same gap).
  'Z86.71',    // Personal history of venous thrombosis and embolism
  'Z86.718',   // Personal history of other venous thrombosis and embolism
  'Z86.711',   // Personal history of pulmonary embolism
  'Z86.73',    // Personal history of TIA / cerebral infarction w/o residual
  'Z86.74',    // Personal history of sudden cardiac arrest
  'Z86.79',    // Personal history of other diseases of the circulatory system
  'Z86.39',    // Personal history of other endocrine, nutritional + metabolic disease
  'Z86.59',    // Personal history of other mental and behavioral disorders

  // Acquired-absence / post-surgical anatomy Z-codes — audit-finding
  // B7 (Month-6 post-RYGB with calcium-citrate switch) wanted Z90.3.
  // Every post-bariatric visit at month 1+ has either Z90.3 or Z90.49.
  // Z98.84 (status of bariatric surgery) was already present; Z90.3
  // is the anatomical-status counterpart.
  // (Z90.3 already in bariatric-surgery cluster above — not re-listed.)
  'Z90.49',    // Acquired absence of other specified parts of digestive tract

  // Severe protein-calorie malnutrition (E43-E46) — audit-finding B9
  // (Year-2 post-RYGB with albumin 2.8, sarcopenia, edema → "PROTEIN-
  // CALORIE MALNUTRITION" documented diagnosis). Prior allowlist only
  // had the symptom-level codes R63.4 / R53.83.
  'E40',       // Kwashiorkor
  'E41',       // Nutritional marasmus
  'E42',       // Marasmic kwashiorkor
  'E43',       // Unspecified severe protein-calorie malnutrition
  'E44.0',     // Moderate protein-calorie malnutrition
  'E44.1',     // Mild protein-calorie malnutrition
  'E45',       // Retarded development following protein-calorie malnutrition
  'E46',       // Unspecified protein-calorie malnutrition
  'E63.0',     // Essential fatty acid deficiency
  'E63.1',     // Imbalance of constituents of food intake
  // (E63.9 already in bariatric-surgery cluster above — not re-listed.)

  // === Procedure-dominant cohort additions (2026-05-13) ===
  // Cross-input-mode audit (PR #232) surfaced empty `codes: []` returns
  // for procedure-dominant scenarios — DERM1 (suspicious nevus biopsy),
  // OB2 (postpartum visit), ORT2 (acute ankle sprain). Pattern: the L7a
  // model treated the visit as procedure-billing-dominant and emitted
  // zero diagnosis codes. OB2 missing Z39.2 (routine postpartum
  // encounter) is the most-concerning miss for billing compliance.
  //
  // Adds the canonical "every visit needs at least one diagnosis or
  // encounter code" coverage for these three families so the L7a
  // prompt strengthening that requires a minimum 1 code per visit has
  // valid codes to choose from.

  // ── OB-GYN postpartum + supervision-of-pregnancy + delivery ──────
  // Z39.x — postpartum-care encounter codes. OB2 demands Z39.2.
  'Z39.0',     // Encounter for care + examination of mother immediately after delivery
  'Z39.1',     // Encounter for care + examination of lactating mother
  'Z39.2',     // Encounter for routine postpartum follow-up
  // Z34.x — supervision of normal pregnancy by trimester. The starter
  // set had Z34.00 + Z34.80 only; full coverage avoids precision drift.
  'Z34.01',    // Supervision of normal first pregnancy, 1st trimester
  'Z34.02',    // … 2nd trimester
  'Z34.03',    // … 3rd trimester
  'Z34.81',    // Supervision of other normal pregnancy, 1st trimester
  'Z34.82',    // … 2nd trimester
  'Z34.83',    // … 3rd trimester
  'Z34.90',    // Supervision of normal pregnancy, unspecified, unspecified trimester
  'Z34.91',    // … 1st trimester
  'Z34.92',    // … 2nd trimester
  'Z34.93',    // … 3rd trimester
  // O80 + O82 — uncomplicated delivery encounter codes.
  'O82',       // Encounter for cesarean delivery without indication
  // O36.x — surveillance of high-risk pregnancy for maternal+fetal problems
  'O36.0991',  // Supervision other materno-fetal problems w/o suspected immune incompatibility, third trimester, fetus 1
  // GDM — O24.4xx family.
  'O24.410',   // Gestational diabetes mellitus in pregnancy, diet controlled
  'O24.414',   // … insulin controlled
  'O24.415',   // … controlled by oral hypoglycemic drugs
  'O24.419',   // … unspecified control
  // Common pregnancy ICDs for billing context.
  'O09.211',   // Supervision of pregnancy w/ history of pre-term labor, 1st trimester
  'O09.213',   // … 3rd trimester
  // Z30.x — contraception encounter codes (postpartum visits often pair).
  'Z30.430',   // Encounter for IUD insertion
  'Z30.431',   // Encounter for routine IUD checking
  'Z30.432',   // Encounter for IUD removal
  'Z30.433',   // Encounter for IUD removal + reinsertion
  'Z30.09',    // Encounter for other general counseling and advice on contraception

  // ── Dermatology — benign-lesion + biopsy + skin-malignancy hx ────
  // D22.x — melanocytic nevi by site (the actual diagnosis for a
  // suspicious-mole biopsy when path is benign nevus).
  'D22.0',     // Melanocytic nevi of lip
  'D22.1',     // Melanocytic nevi of eyelid (incl. canthus)
  'D22.2',     // Melanocytic nevi of ear + external auricular canal
  'D22.3',     // Melanocytic nevi of other + unspecified parts of face
  'D22.4',     // Melanocytic nevi of scalp + neck
  'D22.5',     // Melanocytic nevi of trunk
  'D22.60',    // Melanocytic nevi of unspecified upper limb (incl. shoulder)
  'D22.70',    // Melanocytic nevi of unspecified lower limb (incl. hip)
  'D22.9',     // Melanocytic nevi, unspecified
  // L82.x — seborrheic keratosis (the second-most-common derm biopsy).
  'L82.0',     // Inflamed seborrheic keratosis
  'L82.1',     // Other seborrheic keratosis
  // L57.x — UV-damage / solar keratosis (already partially present
  // via I77/L57 in vascular block; explicit derm coverage below).
  'L57.0',     // Actinic keratosis
  'L57.8',     // Other skin changes due to chronic UV-exposure
  // Z85.828 — personal history of malignant melanoma + other skin
  // (drives surveillance + influences current biopsy decisions).
  'Z85.828',   // Personal history of malignant neoplasm of other skin
  'Z85.820',   // Personal history of malignant melanoma of skin
  // Z80.8 — family history of other malignant neoplasm (e.g. paternal
  // melanoma in the DERM1 scenario).
  'Z80.8',     // Family history of malignant neoplasm of other organs/systems
  // Z12.83 — screening encounter for skin malignancy (annual full-skin
  // exam in a high-risk patient).
  'Z12.83',   // Encounter for screening for malignant neoplasm of skin
  // D48.5 — neoplasm of uncertain behavior of skin (pre-pathology
  // placeholder when biopsy is pending).
  'D48.5',    // Neoplasm of uncertain behavior of skin
  // Acne family — for the isotretinoin/dermatology scenarios.
  // (L70.0 already present above — not re-listed.)
  'L70.1',    // Acne conglobata
  'L70.8',    // Other acne
  'L70.9',    // Acne, unspecified

  // ── Orthopedics — joint pain + aftercare + acute injury ──────────
  // M25.x — joint pain by site. Starter set only had M25.50 + M25.51x.
  // The full family closes the ortho-encounter coverage.
  'M25.511',   // Pain in right shoulder
  'M25.512',   // Pain in left shoulder
  'M25.519',   // Pain in unspecified shoulder
  'M25.521',   // Pain in right elbow
  'M25.522',   // Pain in left elbow
  'M25.531',   // Pain in right wrist
  'M25.532',   // Pain in left wrist
  'M25.551',   // Pain in right hip
  'M25.552',   // Pain in left hip
  'M25.561',   // Pain in right knee
  'M25.562',   // Pain in left knee
  'M25.571',   // Pain in right ankle and joints of right foot
  'M25.572',   // Pain in left ankle and joints of left foot
  // S93.x — acute ankle/foot ligament sprains (ORT2 acute injury).
  'S93.401A',  // Sprain of unspecified ligament of right ankle, initial encounter
  'S93.402A',  // Sprain of unspecified ligament of left ankle, initial encounter
  'S93.409A',  // Sprain of unspecified ligament of unspecified ankle, initial encounter
  'S93.411A',  // Sprain of calcaneofibular ligament of right ankle, initial encounter
  'S93.412A',  // Sprain of calcaneofibular ligament of left ankle, initial encounter
  'S93.421A',  // Sprain of deltoid ligament of right ankle, initial encounter
  'S93.422A',  // Sprain of deltoid ligament of left ankle, initial encounter
  'S93.491A',  // Sprain of other specified ligament of right ankle, initial encounter
  'S93.492A',  // Sprain of other specified ligament of left ankle, initial encounter
  // S83.x — knee sprains.
  'S83.401A',  // Sprain of unspecified CL of right knee, initial encounter
  'S83.402A',  // Sprain of unspecified CL of left knee, initial encounter
  // S39.012A — strain of muscle of lower back (paired with UC2 mech-LBP).
  'S39.012A',  // Strain of muscle, fascia, tendon of lower back, initial encounter
  // Z47.x — aftercare following orthopedic surgery.
  'Z47.1',     // Aftercare following joint replacement surgery
  'Z47.2',     // Encounter for removal of internal fixation device
  'Z47.81',    // Encounter for orthopedic aftercare following surgical amputation
  'Z47.82',    // Encounter for orthopedic aftercare following scoliosis surgery
  'Z47.89',    // Encounter for other orthopedic aftercare
  // M79.6xx — limb pain by site (commonly used when joint-specific
  // M25 code doesn't fit).
  'M79.601',   // Pain in right arm
  'M79.602',   // Pain in left arm
  'M79.604',   // Pain in right leg
  'M79.605',   // Pain in left leg
  'M79.606',   // Pain in unspecified leg

  // ── General encounter Z-codes (procedure-dominant fallback) ──────
  // Z48.x — post-procedural surgical follow-up (general, not specific
  // to any system).
  'Z48.0',     // Encounter for attention to dressings + sutures
  'Z48.00',    // Encounter for change/removal of nonsurgical wound dressing
  'Z48.01',    // Encounter for change/removal of surgical wound dressing
  'Z48.02',    // Encounter for removal of sutures
  'Z48.03',    // Encounter for change/removal of drains
  'Z48.298',   // Encounter for aftercare following other organ transplant (catch-all)
  // Z09 — follow-up after completed treatment for conditions other
  // than malignancy (often the right code when the doctor is just
  // checking on resolved problems).
  'Z09',
  // Z71.x — counseling + medical advice (often the right encounter
  // code for "lifestyle" or "weight-management" check-ins where the
  // chief complaint is already coded elsewhere).
  'Z71.3',     // Dietary counseling and surveillance
  'Z71.4',     // Alcohol abuse counseling and surveillance
  'Z71.5',     // Drug abuse counseling and surveillance
  'Z71.82',    // Exercise counseling
  'Z71.89',    // Other specified counseling
  // Z76.89 — last-resort "other specified reason for encounter" code
  // that the L7a prompt instructs the model to emit when literally no
  // other diagnosis code applies, rather than returning an empty
  // codes array. The L7a post-validation layer will pick up the
  // Z76.89-only case + flag the visit for review.
  'Z76.89',    // Persons encountering health services in other specified circumstances
  // === Gastroenterology cohort (2026-08-14, GI pilot) ===
  // Sibling to the endoscopy CPT block in cpt-allowlist.ts. `07a-icd-coding.ts`
  // drops any code failing isValidIcd10 and emits a fire-and-forget
  // CODING_COACH_REJECTED_INVALID_ICD row the doctor never sees.
  //
  // ⚠️ THIS IS THE HALF THAT ACTUALLY DREW BLOOD. The first real GI visit in
  // production (2026-08-14, created 04:37:17Z, ~20 min after the specialty went
  // live) carries CODING_COACH_REJECTED_INVALID_ICD and ZERO CPT rejections.
  // The procedure-code gap was the one everybody predicted; the DIAGNOSIS gap
  // is the one that fired. Its rejected codes were NOT read — they are a real
  // patient's diagnoses. The list below comes from the domain, as the CPT block
  // did; the audit row is cited only as proof the gap is real.
  //
  // ⚠️ AND THE PRIOR COVERAGE WAS PARTIAL, WHICH IS WORSE THAN ABSENT, because
  // partial looks like coverage. Measured before this block:
  //     PRESENT Z12.11 (screening encounter)  ABSENT K63.5 (colonic polyp)
  //     PRESENT K21.9  (GERD w/o esophagitis) ABSENT K21.00/K21.01 (WITH it)
  //     PRESENT K58.0  (IBS-D)                ABSENT K58.1/.2/.3/.9
  //     PRESENT K57.30 (diverticulosis)       ABSENT K57.32 (diverticulitis)
  // It covered the encounter billed for SCREENING and not the finding screening
  // exists to detect, and in three families exactly one sibling. Every entry
  // below was measured absent, positive-controlled against E11.9 and I10.

  // -- Colonoscopy findings, and the codes that drive the surveillance interval
  'K63.5',     // Polyp of colon — the commonest colonoscopy finding there is
  'D12.0',     // Benign neoplasm of caecum
  'D12.1',     // Benign neoplasm of appendix
  'D12.2',     // Benign neoplasm of ascending colon
  'D12.3',     // Benign neoplasm of transverse colon
  'D12.4',     // Benign neoplasm of descending colon
  'D12.5',     // Benign neoplasm of sigmoid colon
  'D12.6',     // Benign neoplasm of colon, unspecified
  'D12.7',     // Benign neoplasm of rectosigmoid junction
  'D12.8',     // Benign neoplasm of rectum
  'Z86.010',   // Personal history of colonic polyps — sets the surveillance interval
  'Z80.0',     // Family history of malignant neoplasm of digestive organs — sets screening eligibility

  // -- Inflammatory bowel disease: was uncovered ENTIRELY
  'K50.90',    // Crohn disease, unspecified, without complications
  'K51.90',    // Ulcerative colitis, unspecified, without complications

  // -- GI bleeding and anorectal
  'K92.1',     // Melena
  'K92.2',     // Gastrointestinal haemorrhage, unspecified
  'K62.5',     // Haemorrhage of anus and rectum
  'K64.0',     // First degree haemorrhoids
  'K64.1',     // Second degree haemorrhoids
  'K64.8',     // Other haemorrhoids
  'K64.9',     // Unspecified haemorrhoids

  // -- Upper GI / EGD
  // ⚠️ K21.0 ITSELF IS NOT BILLABLE — FY2023 expanded it into these two and
  // left the 4-character code a subcategory HEADER. Admitting the header
  // would put a non-submittable code on the accepted side of the billing
  // floor while the codes a chart actually maps to stayed dropped.
  'K21.00',    // GERD with esophagitis, without bleeding
  'K21.01',    // GERD with esophagitis, with bleeding
  // ⚠️ K22.7 ITSELF IS NOT BILLABLE — a subcategory header since FY2017. The
  // comment originally written here ('without dysplasia') is the title of
  // K22.70, which is the code that was meant.
  'K22.70',    // Barrett esophagus without dysplasia
  'K22.710',   // Barrett esophagus with low grade dysplasia
  'K22.711',   // Barrett esophagus with high grade dysplasia
  'K22.719',   // Barrett esophagus with dysplasia, unspecified
  'K20.0',     // Eosinophilic oesophagitis
  'B96.81',    // Helicobacter pylori as the cause of diseases classified elsewhere
  'K29.70',    // Gastritis, unspecified, without bleeding
  'K31.89',    // Other diseases of stomach and duodenum

  // -- Functional, and the siblings of families already half-covered
  // ⚠️ K58.0 IS IBS-D AND K58.1 IS IBS-C. An earlier draft of this block had
  // them inverted in three places, while line 47 of this same file already
  // said 'K58.0 // IBS with diarrhea'. The file contradicted the comment.
  'K58.1',     // Irritable bowel syndrome with constipation (IBS-C)
  'K58.2',     // Mixed irritable bowel syndrome (IBS-M)
  'K58.3',     // Other irritable bowel syndrome
  'K58.9',     // Irritable bowel syndrome, unspecified
  'K57.32',    // Diverticulitis of large intestine without perforation or abscess without bleeding
  'R19.7',     // Diarrhoea, unspecified

  // -- Hepatology
  'K74.60',    // Unspecified cirrhosis of liver

];

/**
 * Allowlist set — case-insensitive lookup. Codes are stored uppercase
 * because the CMS canonical list is uppercase and Claude's outputs vary.
 */
export const ICD10_ALLOWLIST: ReadonlySet<string> = new Set(
  STARTER_ICD10_CODES.map((c) => c.trim().toUpperCase())
);

/**
 * Validates an ICD-10-CM code against the allowlist.
 * Round 3 PR-D — A06-P0-002 deterministic floor.
 *
 * Returns true if the code is in the canonical starter set, false
 * otherwise. The 07a-icd-coding layer's validator drops codes that
 * return false and emits a CODING_COACH_REJECTED_INVALID_ICD audit row.
 *
 * @param code The ICD-10-CM code to validate (e.g. "E11.9", "I10").
 *             Whitespace + case are normalized; null/undefined/empty
 *             input returns false.
 */
export function isValidIcd10(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;
  return ICD10_ALLOWLIST.has(trimmed);
}

/** Total size of the starter allowlist. Surfaced in admin diagnostics. */
export const ICD10_ALLOWLIST_SIZE = ICD10_ALLOWLIST.size;
