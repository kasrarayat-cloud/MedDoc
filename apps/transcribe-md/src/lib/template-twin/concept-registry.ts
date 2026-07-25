// ============================================================================
// CONCEPT REGISTRY — one vocabulary, both sides.
// ----------------------------------------------------------------------------
// The mapping proposer used to invent a concept per field:
//   test.venous_duplex.gsv_sfj_diameter
//   test.venous_duplex.gsv_sfj.reflux_time_ms
// L3 never emits strings like those, and factSatisfiesMapping requires the
// fact's concept to BE the mapping's concept or an approved synonym. So no fact
// could ever match any cell — permanently, regardless of dictation. That was
// the root of `filledCount=0`.
//
// The fix is not to loosen the matcher. It is to make intersection true BY
// CONSTRUCTION: the proposer may only select concepts the extractor actually
// emits. This file is that list, built from a real extraction run, not from
// imagination:
//
//   [vocab] measurement.diameter    n=4 numeric=4 lat={right,left}
//   [vocab] measurement.reflux_time n=4 numeric=4 lat={right,left}
//   [vocab] assessment              n=2 numeric=0 lat={bilateral}
//   [vocab] exam.vascular           n=2 numeric=0 lat={unknown}
//   [vocab] test.name               n=1 numeric=0 lat={bilateral}
//   [vocab] test.<study>.result     n=1 numeric=0 lat={bilateral}
//
// ANATOMY IS NEVER IN A CONCEPT. A measurement's concept is its KIND; which
// vein, which side and which segment travel as structured fact data
// (laterality, evidence quote, span). That is what lets one concept serve
// twenty-six template rows.
// ============================================================================

/** Concepts the extractor emits verbatim. */
export const REGISTRY_CONCEPTS: readonly string[] = [
  // Measurements — the metric enum from L3's schema, one concept per KIND.
  'measurement.diameter',
  'measurement.reflux_time',
  'measurement.velocity',
  'measurement.length',
  'measurement.depth',
  // Clinical narrative concepts.
  'assessment',
  'chief_complaint',
  'past_medical_history',
  'family_history',
  'social_history',
  'exam.vascular',
  'test.name',
  // Plan/medication/allergy concepts the SOAP path emits.
  'plan',
  'medication',
  'allergy',
];

/**
 * Patterned concepts. The extractor slugs the study name into the concept for
 * test results (`test.bilateral_lower_extremity_venous_duplex_reflux_study.result`),
 * so these cannot be enumerated — but they are still a closed SHAPE, not free
 * text.
 */
export const REGISTRY_PATTERNS: readonly RegExp[] = [
  /^test\.[a-z0-9_]+\.result$/,
  /^exam\.[a-z0-9_.]+$/,
  /^hpi\.[a-z0-9_]+$/,
];

/**
 * Synonyms a physician may legitimately approve, mapping the registry concept
 * to alternative spellings a fact might carry. Explicit and small on purpose —
 * this is the ONE place the two vocabularies are allowed to differ.
 */
export const REGISTRY_SYNONYMS: Readonly<Record<string, readonly string[]>> = {
  'measurement.diameter': ['measurement.vein_diameter', 'exam.vascular.diameter'],
  'measurement.reflux_time': [
    'measurement.reflux',
    'measurement.reflux_duration',
    'exam.vascular.reflux_time',
  ],
  assessment: ['assessment_discussed', 'impression'],
  'exam.vascular': ['exam_findings.vascular'],
};

export function isRegisteredConcept(concept: string): boolean {
  const c = concept.trim().toLowerCase();
  if (REGISTRY_CONCEPTS.includes(c)) return true;
  if (REGISTRY_PATTERNS.some((p) => p.test(c))) return true;
  return Object.values(REGISTRY_SYNONYMS).some((list) => list.includes(c));
}

/** Every concept a mapping for this registry entry may legitimately cite. */
export function synonymsFor(concept: string): readonly string[] {
  return REGISTRY_SYNONYMS[concept.trim().toLowerCase()] ?? [];
}

export class OffRegistryConceptError extends Error {
  readonly code = 'OFF_REGISTRY_CONCEPT';
  readonly concepts: readonly string[];

  constructor(concepts: readonly string[]) {
    super(
      `Proposed mapping concepts are not in the extractor's vocabulary: ` +
        `${concepts.slice(0, 8).join(', ')}${concepts.length > 8 ? ', …' : ''}. ` +
        'A concept the extractor never emits can never be matched by any fact, ' +
        'so the field would be permanently unfillable. Anatomy belongs in the ' +
        'fact (laterality, segment), never in the concept string.',
    );
    this.name = 'OffRegistryConceptError';
    this.concepts = concepts;
  }
}
