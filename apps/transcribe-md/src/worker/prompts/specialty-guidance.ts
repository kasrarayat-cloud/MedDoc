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
