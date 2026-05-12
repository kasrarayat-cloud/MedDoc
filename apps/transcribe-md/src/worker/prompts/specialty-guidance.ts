// ============================================================================
// TranscribeMD worker — specialty-specific SOAP guidance (T-M4 Layer 4)
// ----------------------------------------------------------------------------
// Appended to the SOAP-generation system prompt. Keys MUST be the
// SpecialtyId values from packages/shared/src/specialties.ts (templateId
// field). Any unlisted slug falls back to empty string → the generic
// SOAP prompt. The pair (catalog row, guidance entry) is what the
// generators-test.ts coverage check enforces — adding a specialty to
// the catalog without adding guidance here is a soft regression but
// not a build failure (the SOAP just falls back to generic).
// ============================================================================

export const SPECIALTY_GUIDANCE: Record<string, string> = {
  cardiology:
    "Document NYHA class if heart failure is discussed. Note " +
    "cardiovascular risk factors explicitly (HTN, DM, dyslipidemia, " +
    "smoking, family history). Document any cardiac exam findings " +
    "(S1/S2, murmurs, JVD, edema) precisely. If acute coronary " +
    "syndrome is in the differential, capture TIMI/HEART score " +
    "components that were discussed.",

  psychiatry:
    "Include a Mental Status Exam section (appearance, behavior, " +
    "speech, mood, affect, thought process, thought content, cognition, " +
    "insight, judgment). Document risk assessment (suicidal/homicidal " +
    "ideation) explicitly even if negative — absence of risk is a " +
    "documented clinical finding. Use neutral, non-stigmatizing " +
    "language. Do NOT infer psychiatric diagnoses that weren't " +
    "explicitly discussed.",

  pediatrics:
    "Document growth parameters (weight, height, head circumference, " +
    "percentiles) if given. Document developmental milestones or " +
    "concerns. Capture caregiver concerns alongside patient " +
    "statements — distinguish who said what. Note immunization status " +
    "if discussed. Use age-appropriate language in patient education.",

  'internal-medicine':
    "Use standard internal medicine formatting. Ensure comprehensive " +
    "ROS documentation. Document chronic disease management status " +
    "for known conditions (e.g., 'DM type 2, well-controlled, A1c " +
    "6.8%'). Note medication reconciliation if the doctor reviewed " +
    "medications.",

  'primary-care':
    "Emphasize prevention and chronic disease management. Document " +
    "screening status (cancer screening, immunizations) if discussed. " +
    "Note lifestyle counseling. Capture shared decision-making " +
    "conversations explicitly when they occur.",

  dermatology:
    "Describe lesions with morphology (macule, papule, plaque, " +
    "vesicle, nodule), distribution, color, size, border, symmetry. " +
    "Note duration and any changes over time. Document dermoscopy or " +
    "biopsy if performed. If ABCDE criteria were applied, capture " +
    "each dimension.",

  orthopedics:
    "Document ROM (active and passive) with degrees, strength grading " +
    "(0-5), special tests performed (e.g., McMurray's, Lachman's, " +
    "anterior drawer), and imaging findings if discussed. Note " +
    "mechanism of injury precisely for acute presentations.",

  'ob-gyn':
    "Document LMP (last menstrual period), gravida/para (G_P_), cycle " +
    "regularity, contraception, and any pregnancy-related symptoms. " +
    "Note Pap/HPV screening status if discussed. For prenatal visits, " +
    "document fundal height and fetal heart tones when stated.",

  'obstetrics-gynecology':
    "Document LMP (last menstrual period), gravida/para (G_P_), cycle " +
    "regularity, contraception, and any pregnancy-related symptoms. " +
    "Note Pap/HPV screening status if discussed. For prenatal visits, " +
    "document fundal height and fetal heart tones when stated.",

  'urgent-care':
    "Document chief complaint precisely with duration and severity. " +
    "Capture vital signs and red-flag symptoms explicitly (chest pain, " +
    "shortness of breath, neuro deficits, severe headache, syncope). " +
    "Note disposition decision (discharge home, referral to ED, " +
    "follow-up timing) and the rationale. Capture return precautions " +
    "if discussed.",

  'pain-management':
    "Document pain location, character (sharp / dull / burning / " +
    "radiating), 0-10 severity, duration, exacerbating + alleviating " +
    "factors. Note functional impact (sleep, work, ADLs). Capture " +
    "medication history including doses, frequency, prior trials and " +
    "outcomes. Document non-pharmacologic modalities tried (PT, " +
    "injections, behavioral). Note any controlled-substance prescribing " +
    "decisions and the documented rationale. Be cautious about " +
    "diagnostic specificity unless the doctor stated a clear diagnosis.",

  // Vascular Surgery — full-scope (venous + arterial + aortic + carotid +
  // endovascular + dialysis access + vascular trauma). Like Bariatric
  // Surgery, the SOAP structure varies sharply by visit type. The model
  // MUST identify which of the five visit types applies before drafting,
  // then apply that type's required structure. Office consultations are
  // further sub-branched by chief-complaint domain (venous / arterial /
  // aortic / carotid / dialysis access).
  'vascular-surgery':
    "Vascular Surgery visits fall into FIVE types with different " +
    "documentation requirements. Identify which type applies from the " +
    "transcript before drafting:\n" +
    "\n" +
    "  VISIT TYPE = OFFICE CONSULTATION:\n" +
    "Identify the chief complaint domain (venous / arterial / aortic / " +
    "carotid / dialysis access / vascular wound), then apply the " +
    "matching sub-structure below.\n" +
    "\n" +
    "    VENOUS (varicose veins, chronic venous insufficiency, ulcers):\n" +
    "    Document the CEAP classification explicitly with all four " +
    "axes (C0-C6 Clinical / Ec-Ep-Es Etiology / As-Ad-Ap Anatomic / " +
    "Pr-Po Pathophysiology). VCSS (Venous Clinical Severity Score) " +
    "where calculable. Conservative-therapy documentation is " +
    "REQUIRED for insurance pre-authorization: compression class " +
    "(20-30 vs 30-40 mmHg), duration of compliant use, exercise / " +
    "elevation history. Duplex findings: reflux duration in ms at " +
    "GSV / SSV / perforators, vein diameter at the saphenofemoral " +
    "or saphenopopliteal junction, perforator competence, deep " +
    "system patency.\n" +
    "\n" +
    "    ARTERIAL (peripheral arterial disease, claudication, " +
    "critical limb ischemia):\n" +
    "    Rutherford classification (0-6) is REQUIRED on every PAD " +
    "consult. Fontaine classification (I / IIa / IIb / III / IV) " +
    "as secondary if discussed. Pulse exam: femoral, popliteal, " +
    "dorsalis pedis (DP), posterior tibial (PT) bilaterally, with " +
    "0 / 1+ / 2+ / 3+ scoring. Ankle-Brachial Index (ABI) — normal " +
    "> 1.0, claudication 0.5-0.9, rest pain / CLI < 0.5. If vessels " +
    "are non-compressible (heavily calcified — diabetes / ESRD), " +
    "use Toe-Brachial Index (TBI). Segmental pressures + waveforms " +
    "if obtained. Walking distance to claudication onset (block " +
    "distance). Imaging findings if CTA / MRA / angiogram done. " +
    "Cardiovascular risk-factor status: smoking (the BIGGEST PAD " +
    "modifier), BP, A1c, LDL goal < 70 mg/dL for ASCVD. " +
    "Cardiovascular risk-factor counseling is a required " +
    "documented finding on every PAD visit, even on follow-up.\n" +
    "\n" +
    "    AORTIC (AAA, TAA, dissection):\n" +
    "    Aneurysm location + maximum diameter in cm. Growth rate " +
    "from prior imaging (> 0.5 cm in 6 months is urgent). Repair " +
    "threshold: 5.5 cm men / 5.0 cm women for AAA — document " +
    "whether the patient meets threshold + why surveillance vs " +
    "repair was chosen. Anatomic suitability for EVAR: neck length " +
    "(target ≥ 10-15 mm), neck angle, iliac caliber, tortuosity. " +
    "Comorbidity burden for repair-risk stratification (cardiac, " +
    "pulmonary, renal-for-contrast). For dissection: type A vs B, " +
    "stable vs malperfusion, end-organ ischemia screen (renal, " +
    "mesenteric, spinal, peripheral) — document each axis even " +
    "when negative.\n" +
    "\n" +
    "    CAROTID (asymptomatic stenosis, post-TIA / stroke):\n" +
    "    Degree of stenosis (NASCET % from duplex peak systolic + " +
    "end-diastolic velocities). Symptom status: asymptomatic vs " +
    "symptomatic (TIA, stroke, amaurosis fugax) — symptom timing " +
    "(within 6 months affects urgency tier per CEA / CAS " +
    "guidelines). Contralateral carotid status (patent / stenosed " +
    "/ occluded). Plaque morphology (echolucent, ulcerated) when " +
    "reported on duplex.\n" +
    "\n" +
    "    DIALYSIS ACCESS (pre-dialysis or established):\n" +
    "    Renal disease stage (CKD 4 / 5 / ESRD) + current modality " +
    "(HD, PD, pre-dialysis). Hand preference + dominant arm — the " +
    "non-dominant arm is the default fistula site. Prior access " +
    "history with locations, dates, and failure modes (thrombosis, " +
    "infection, steal). Vein mapping ultrasound: cephalic / " +
    "basilic vein diameter at the wrist + cubital fossa, depth " +
    "from skin, radial / brachial artery patency. Recommended " +
    "access type with rationale: radiocephalic AVF / " +
    "brachiocephalic AVF / brachiobasilic transposition / " +
    "AV graft / tunneled catheter — fistula-first per KDOQI when " +
    "anatomy supports it.\n" +
    "\n" +
    "  VISIT TYPE = ENDOVASCULAR PROCEDURE (catheter-lab / suite):\n" +
    "Document the procedure (angioplasty / stenting / embolization / " +
    "EVAR / TEVAR / thrombectomy / atherectomy / ablation) and the " +
    "indication corresponding to the consult workup. Access site " +
    "(common femoral / brachial / radial, antegrade vs retrograde). " +
    "Sheath size + length. Contrast type + total volume in mL. " +
    "Fluoroscopy time + radiation dose (DAP / mGy where captured). " +
    "Devices: catheters, wires, balloons (size + length), stents " +
    "(type + size + length, DES vs BMS for coronary, covered vs " +
    "uncovered for peripheral). Lesion characterization with " +
    "pre / post stenosis %. Final result: residual stenosis, run-" +
    "off, hemodynamic improvement. Closure (manual hold, Angioseal, " +
    "Perclose, FemoStop). Heparinization with ACT goal documented.\n" +
    "\n" +
    "  VISIT TYPE = OPEN VASCULAR PROCEDURE (OR):\n" +
    "Procedure (carotid endarterectomy / open AAA repair / bypass / " +
    "AV fistula creation / embolectomy). Position + approach. " +
    "Anesthesia type (general, regional, MAC). Surgical findings. " +
    "Repair technique + materials (graft type — PTFE / Dacron / " +
    "vein, suture). Cross-clamp time (REQUIRED for AAA repair and " +
    "for carotid endarterectomy — drives spinal-cord / cerebral " +
    "ischemia risk stratification). Heparin administration. " +
    "Complications (bleeding, neurologic, ischemic). Disposition " +
    "(ICU vs floor, drains, planned imaging).\n" +
    "\n" +
    "  VISIT TYPE = POST-PROCEDURE / SURVEILLANCE:\n" +
    "First line MUST be 'POD #N or month-N, status post [procedure " +
    "on date]'. Apply the surveillance protocol matching the " +
    "procedure:\n" +
    "    Post-EVAR: CT at 1 mo / 6 mo / 12 mo / annually. " +
    "Endoleak screen with Type I-V classification documented even " +
    "when negative. Sac size trend with absolute mm change. Limb " +
    "patency on the index endograft.\n" +
    "    Post-CEA / post-carotid stent: duplex at 1 mo / 6 mo / " +
    "annually. Restenosis assessment (peak systolic velocity > " +
    "300 cm/s suggests > 70% restenosis).\n" +
    "    Post-bypass (fem-pop / fem-tib / ax-fem): duplex with " +
    "velocity criteria. ABI trend vs pre-op. Symptom recurrence — " +
    "documented even when negative.\n" +
    "    Post-AV fistula: 4-6 week maturation assessment using the " +
    "Rule of 6s — diameter > 6 mm at planned cannulation site, " +
    "depth < 6 mm from skin, flow > 600 mL/min, length > 6 cm of " +
    "straight cannulation segment. Cannulation readiness must be " +
    "documented explicitly before the dialysis nurse can use the " +
    "access.\n" +
    "\n" +
    "ACROSS ALL VISIT TYPES — cardiovascular risk-factor " +
    "optimization is required on every encounter even when the " +
    "primary problem is not arterial: smoking cessation (the " +
    "largest single modifier for PAD outcomes), BP target, " +
    "LDL < 70 mg/dL for ASCVD patients, diabetes control. " +
    "Antiplatelet status (nearly all PAD / coronary patients on " +
    "aspirin or clopidogrel; dual-antiplatelet duration post-stent " +
    "must be documented). Anticoagulation status if applicable. " +
    "Absence of these is a documented clinical finding.",

  // Bariatric Surgery — onboarded alongside Weight Management for the
  // weight-loss-clinic pilots that perform both medical + surgical
  // intervention. Three lifecycle phases must be branched in the SOAP
  // because the required sections, complication screens, and Rx
  // recommendations differ sharply: pre-op (work-up + clearance), early
  // post-op (first 30 days, leak / bleed / DVT / dehydration watch),
  // and late post-op (>30 days, nutritional + comorbidity tracking).
  // The guidance below instructs the model to FIRST infer which phase
  // applies, then apply that phase's required structure.
  'bariatric-surgery':
    "Bariatric visits fall into three lifecycle phases with different " +
    "documentation requirements. Identify which phase applies from the " +
    "transcript before drafting:\n" +
    "\n" +
    "  PHASE = PRE-OP (work-up before surgery):\n" +
    "Document the anticipated procedure (RYGB / sleeve gastrectomy / " +
    "adjustable gastric band / BPD-DS / revision). Surgical-risk " +
    "assessment with BMI, key comorbidities (T2DM, HTN, OSA, NAFLD, " +
    "cardiac), and cardiopulmonary tolerance findings. Psychological " +
    "clearance status (cleared / pending / needs further evaluation) — " +
    "absence of clearance is a documented finding. Nutritional " +
    "clearance + RD evaluation summary. Pre-op weight loss target " +
    "and progress when stipulated. Patient motivation, support " +
    "system, and adherence indicators.\n" +
    "\n" +
    "  PHASE = EARLY POST-OP (first 30 days after surgery):\n" +
    "First line of HPI MUST be 'POD #N, status post [procedure on " +
    "date]'. Hospital course summary (LOS, complications, discharge " +
    "criteria). Diet phase: clear liquids / full liquids / pureed / " +
    "soft / regular — explicit, never assumed. Complication screen, " +
    "each item documented even when negative: anastomotic leak signs " +
    "(tachycardia, fever, abdominal pain, leukocytosis), GI bleeding, " +
    "DVT / PE symptoms, dehydration / unable to tolerate PO, wound " +
    "infection or dehiscence. Pain control regimen. Activity " +
    "progression. Anticoagulation status if on prophylaxis.\n" +
    "\n" +
    "  PHASE = LATE POST-OP (>30 days after surgery):\n" +
    "First line MUST be 'POD #N or month-N, status post [procedure on " +
    "date]'. Weight + BMI trend with % EWL (excess weight loss). " +
    "Nutritional status: B12, vitamin D, iron, calcium, thiamine, " +
    "folate values with trend direction. Dumping syndrome screen for " +
    "post-bypass patients (early vs late dumping symptoms). Dietary " +
    "adherence + daily protein intake (target 60-80 g/d typical). " +
    "Hydration status. Comorbidity resolution: T2DM (off insulin / " +
    "off all meds / partial), HTN improvement, OSA CPAP re-titration " +
    "needed, GERD course. Adherence to lifelong supplementation " +
    "(bariatric multivitamin, calcium citrate NOT carbonate for " +
    "bypass patients, B12 sublingual or IM, iron, ursodiol gallstone " +
    "prophylaxis during rapid-loss window).\n" +
    "\n" +
    "Across all phases: explicitly document calcium citrate vs " +
    "carbonate distinction in the medication list — post-bypass " +
    "patients lose the acidic gastric environment that dissolves " +
    "carbonate, so citrate is non-substitutable. The L7c Rx layer " +
    "treats this as a hard safety bullet.",

  // Weight Management — onboarded for weight-loss clinic pilots. Adds two
  // section requirements (Body Composition, Behavioral Counseling) on top
  // of the standard SOAP shell, plus GLP-1 safety screening that the L5
  // critique downstream uses to flag missing items.
  'weight-management':
    "Include a 'Body Composition' subsection in Objective documenting: " +
    "current weight, BMI (calculate if height available), waist " +
    "circumference if measured, and percent change since the prior visit " +
    "when stated. Include a 'Behavioral Counseling' subsection in Plan " +
    "documenting: dietary pattern discussed (e.g. caloric deficit, " +
    "Mediterranean, low-carb), physical-activity prescription " +
    "(type / minutes / frequency), behavior-change strategies (sleep, " +
    "stress, alcohol, eating triggers), and any referrals (RD, " +
    "behavioral therapy, bariatric eval). Document GLP-1 safety screen " +
    "explicitly when prescribed or refilled: personal/family history of " +
    "medullary thyroid carcinoma or MEN-2, history of pancreatitis, " +
    "active gallbladder disease, severe gastroparesis, and pregnancy " +
    "status — absence is a documented clinical finding. For diabetic " +
    "patients note A1c trend (current vs prior). For GLP-1 / GIP " +
    "agonist (semaglutide, tirzepatide, liraglutide), capture the " +
    "current dose AND the planned titration step (e.g. " +
    "'semaglutide 0.5 mg weekly, escalate to 1.0 mg at week 4 if " +
    "tolerated'); never document a maintenance dose without the " +
    "titration plan that produced it.",
};

/** Return specialty-specific guidance or an empty string if none
 *  matches. The empty string is a safe append to the generic prompt. */
export function specialtyGuidance(slug: string | null | undefined): string {
  if (!slug) return '';
  const key = slug.toLowerCase().trim();
  return SPECIALTY_GUIDANCE[key] ?? '';
}
