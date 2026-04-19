// ============================================================================
// TranscribeMD worker — specialty-specific SOAP guidance (T-M4 Layer 4)
// ----------------------------------------------------------------------------
// Appended to the SOAP-generation system prompt. Keys match the slug in
// ScribeSpecialtyTemplate so we don't need a second mapping table. Any
// unlisted slug falls back to empty string → the generic SOAP prompt.
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
};

/** Return specialty-specific guidance or an empty string if none
 *  matches. The empty string is a safe append to the generic prompt. */
export function specialtyGuidance(slug: string | null | undefined): string {
  if (!slug) return '';
  const key = slug.toLowerCase().trim();
  return SPECIALTY_GUIDANCE[key] ?? '';
}
