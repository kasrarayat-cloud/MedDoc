// ============================================================================
// Template Twin safe-alpha clinical concept registry
// ----------------------------------------------------------------------------
// The current runtime can populate only concepts deterministically projected
// from the fixed Layer-3 SOAP entity schema. Certification must not promise
// arbitrary specialty extraction. Later template-aware extractors can extend
// this boundary by implementing TemplateTwinConceptProvider under a new,
// explicitly certified registry version.
// ============================================================================

export const TEMPLATE_TWIN_CONCEPT_REGISTRY_VERSION =
  'template-twin-soap-concepts/1.0.0' as const;
export const TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE =
  'TT_CONCEPT_UNSUPPORTED_V1' as const;
export const TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON =
  'This clinical detail is not produced and independently validated by the current Template Twin extractor. Choose a supported detail or wait for a later extraction version.';

export interface SupportedTemplateTwinConcept {
  readonly concept: string;
  readonly sourceEntityPath: string;
  readonly physicianLabel: string;
}
/** Extension seam for the later Template-Aware Extraction Agent. Safe-alpha
 * runtime does not register a dynamic provider. Any future provider must have
 * its own version and return an exact descriptor, never a fuzzy match. */
export interface TemplateTwinConceptProvider {
  readonly providerVersion: string;
  resolveExact(concept: string): SupportedTemplateTwinConcept | null;
}

const CORE_CONCEPTS: readonly SupportedTemplateTwinConcept[] = [
  { concept: 'chief_complaint', sourceEntityPath: 'chief_complaint.statement', physicianLabel: 'Chief concern' },
  { concept: 'hpi.onset', sourceEntityPath: 'hpi.onset', physicianLabel: 'Symptom onset' },
  { concept: 'hpi.duration', sourceEntityPath: 'hpi.duration', physicianLabel: 'Symptom duration' },
  { concept: 'hpi.quality', sourceEntityPath: 'hpi.quality', physicianLabel: 'Symptom quality' },
  { concept: 'hpi.severity', sourceEntityPath: 'hpi.severity', physicianLabel: 'Symptom severity' },
  { concept: 'hpi.location', sourceEntityPath: 'hpi.location', physicianLabel: 'Symptom location' },
  { concept: 'hpi.timing', sourceEntityPath: 'hpi.timing', physicianLabel: 'Symptom timing' },
  { concept: 'hpi.context', sourceEntityPath: 'hpi.context', physicianLabel: 'Symptom context' },
  { concept: 'hpi.modifying_factors', sourceEntityPath: 'hpi.modifying_factors', physicianLabel: 'Modifying factors' },
  { concept: 'hpi.associated_symptoms', sourceEntityPath: 'hpi.associated_symptoms', physicianLabel: 'Associated symptoms' },
  { concept: 'past_medical_history', sourceEntityPath: 'past_medical_history[].condition', physicianLabel: 'Past medical history' },
  { concept: 'medication.name', sourceEntityPath: 'medications[].name', physicianLabel: 'Medication name' },
  { concept: 'medication.dose', sourceEntityPath: 'medications[].dose', physicianLabel: 'Medication dose' },
  { concept: 'medication.route', sourceEntityPath: 'medications[].route', physicianLabel: 'Medication route' },
  { concept: 'medication.frequency', sourceEntityPath: 'medications[].frequency', physicianLabel: 'Medication frequency' },
  { concept: 'allergy.substance', sourceEntityPath: 'allergies[].substance', physicianLabel: 'Allergy or intolerance' },
  { concept: 'allergy.reaction', sourceEntityPath: 'allergies[].reaction', physicianLabel: 'Allergy reaction' },
  { concept: 'family_history.relation', sourceEntityPath: 'family_history[].relation', physicianLabel: 'Family relationship' },
  { concept: 'family_history.condition', sourceEntityPath: 'family_history[].condition', physicianLabel: 'Family history condition' },
  { concept: 'social_history.smoking', sourceEntityPath: 'social_history.smoking.status', physicianLabel: 'Smoking status' },
  { concept: 'social_history.alcohol', sourceEntityPath: 'social_history.alcohol.status', physicianLabel: 'Alcohol use' },
  { concept: 'social_history.drugs', sourceEntityPath: 'social_history.drugs.status', physicianLabel: 'Other substance use' },
  { concept: 'social_history.occupation', sourceEntityPath: 'social_history.occupation.value', physicianLabel: 'Occupation' },
  { concept: 'test.name', sourceEntityPath: 'tests_mentioned[].test', physicianLabel: 'Test mentioned' },
  { concept: 'assessment', sourceEntityPath: 'assessment_discussed[].finding', physicianLabel: 'Assessment discussed' },
  { concept: 'plan', sourceEntityPath: 'plan_discussed[].item', physicianLabel: 'Plan discussed' },
] as const;

const ROS_SYSTEMS = [
  'constitutional',
  'eyes',
  'ent',
  'cardiovascular',
  'respiratory',
  'gastrointestinal',
  'genitourinary',
  'musculoskeletal',
  'skin',
  'neurological',
  'psychiatric',
  'endocrine',
  'hematologic',
  'allergic_immunologic',
] as const;

const EXAM_SYSTEMS = [
  'general',
  'head',
  'eyes',
  'ent',
  'neck',
  'cardiovascular',
  'respiratory',
  'abdomen',
  'musculoskeletal',
  'skin',
  'neurological',
  'psychiatric',
] as const;

const SYSTEM_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  general: 'general',
  constitutional: 'constitutional',
  constitution: 'constitutional',
  eye: 'eyes',
  eyes: 'eyes',
  heent: 'ent',
  ent: 'ent',
  ears_nose_throat: 'ent',
  cardiac: 'cardiovascular',
  cardiovascular: 'cardiovascular',
  cv: 'cardiovascular',
  pulmonary: 'respiratory',
  respiratory: 'respiratory',
  lungs: 'respiratory',
  gi: 'gastrointestinal',
  gastrointestinal: 'gastrointestinal',
  abdominal: 'abdomen',
  abdomen: 'abdomen',
  gu: 'genitourinary',
  genitourinary: 'genitourinary',
  musculoskeletal: 'musculoskeletal',
  msk: 'musculoskeletal',
  skin: 'skin',
  dermatologic: 'skin',
  neuro: 'neurological',
  neurologic: 'neurological',
  neurological: 'neurological',
  psych: 'psychiatric',
  psychiatric: 'psychiatric',
  endocrine: 'endocrine',
  hematologic: 'hematologic',
  hematology: 'hematologic',
  allergic_immunologic: 'allergic_immunologic',
  allergy_immunology: 'allergic_immunologic',
  head: 'head',
  neck: 'neck',
});

export const TEMPLATE_TWIN_SUPPORTED_CONCEPTS: readonly SupportedTemplateTwinConcept[] =
  Object.freeze([
    ...CORE_CONCEPTS,
    ...ROS_SYSTEMS.map((system) => ({
      concept: `ros.${system}`,
      sourceEntityPath: 'ros[].finding',
      physicianLabel: `Review of systems — ${system.replaceAll('_', ' ')}`,
    })),
    ...EXAM_SYSTEMS.map((system) => ({
      concept: `exam.${system}`,
      sourceEntityPath: 'exam_findings[].finding',
      physicianLabel: `Exam — ${system.replaceAll('_', ' ')}`,
    })),
  ]);

const BY_CONCEPT = new Map(
  TEMPLATE_TWIN_SUPPORTED_CONCEPTS.map((entry) => [entry.concept, entry]),
);

export function normalizeTemplateTwinConcept(value: string): string {
  return value.normalize('NFKC').trim().toLocaleLowerCase('en-US');
}

export function resolveSupportedTemplateTwinConcept(
  concept: string,
  extensions: readonly TemplateTwinConceptProvider[] = [],
): SupportedTemplateTwinConcept | null {
  const normalized = normalizeTemplateTwinConcept(concept);
  const builtIn = BY_CONCEPT.get(normalized);
  if (builtIn) return builtIn;
  for (const extension of extensions) {
    const resolved = extension.resolveExact(normalized);
    if (resolved && normalizeTemplateTwinConcept(resolved.concept) === normalized) {
      return resolved;
    }
  }
  return null;
}

export function isSupportedTemplateTwinConcept(concept: string): boolean {
  return resolveSupportedTemplateTwinConcept(concept) !== null;
}

/** Maps free-text L3 system labels only to the bounded safe-alpha taxonomy. */
export function supportedProjectedSystemConcept(
  family: 'ros' | 'exam',
  sourceSystem: string,
): string | null {
  const segment = sourceSystem
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase('en-US')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  const canonicalSystem = SYSTEM_ALIASES[segment];
  if (!canonicalSystem) return null;
  const concept = `${family}.${canonicalSystem}`;
  return BY_CONCEPT.has(concept) ? concept : null;
}
