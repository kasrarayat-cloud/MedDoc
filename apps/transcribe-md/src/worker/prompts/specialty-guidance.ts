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
