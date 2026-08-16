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


// ============================================================================
// FIELD CLASSIFICATION — where a field's value legitimately comes from.
// ----------------------------------------------------------------------------
// Derived from the recorded WM_IOV classification. Label-driven and enumerated:
// a field nobody dictates cannot be filled from evidence, and pretending
// otherwise is what left 4/80 mappings unconcepted and certification blocked.
//
// NOTE on context_default: referring physician / machine / location / address
// ARE deterministic practice context, and the live product fills that class
// today. They classify as 'manual' here — NOT because that is their nature, but
// because a deterministic fill puts content into a signed note the clinician
// never dictated, and the flagged review-before-sign lane for that does not
// exist yet. Until it does, honest blank beats silent fill. When the lane
// lands, these move to 'context_default' and start filling; that is a
// one-line change here plus re-certification.
// ============================================================================

const MANUAL_LABEL_PATTERNS: ReadonlyArray<RegExp> = [
  /ultrasound\s+technologist/i, // truly per-visit-human: who was on shift
  /referring\s+physician/i,      // context_default in waiting
  /^machine\b/i,                 // context_default in waiting
  /^location\b/i,                // context_default in waiting
  /^address\b/i,                 // context_default in waiting
];

/**
 * Labels whose CONCEPT the compiler decides rather than the model — the same
 * doctrine already applied to `expectedDataType` and `sourceType`: the
 * document's own label is stronger evidence than a guess, and a mapping that
 * does not depend on a sampling decision is what makes certification
 * reproducible.
 *
 * The one entry so far is the study-identity class. "SIDE OF EXAM" reads like
 * laterality but its options are PROTOCOL strings — "Bilateral Detailed",
 * "Unilateral - Right Leg Limited; Left Leg Screening". The extractor names the
 * study under `test.name` and nothing else can support those options, yet the
 * model proposed a fresh concept for it on every run, which nulled the field and
 * blocked certification. With the concept pinned, the field fills only when the
 * doctor actually states the protocol; a dictation that says merely "bilateral
 * lower extremity venous duplex" does not entail "Bilateral Detailed", so the
 * field stays honestly blank.
 */
export const CONCEPT_LABEL_OVERRIDES: ReadonlyArray<readonly [RegExp, string]> = [
  [/^\s*(side of exam|exam type|type of (exam|study)|study type)\b/i, 'test.name'],
];

/**
 * The concepts `veinGridCellConcept` can emit. Declared beside the function and
 * USED BY IT, so the enumeration cannot drift from the implementation the way a
 * hand-kept list would.
 */
export const VEIN_GRID_CONCEPTS = {
  reflux: 'measurement.reflux_time',
  diameter: 'measurement.diameter',
} as const;

/**
 * EVERY concept the compiler can decide from the document alone — the override
 * table's targets plus the vein-grid pair.
 *
 * ⚠️ WHY THIS IS EXPORTED. The fallback mapping path registry-checks the
 * compiler's answer, and a mutation proof showed that check is presently
 * UNREACHABLE: every value here is already registry-legal, so dropping the check
 * changed nothing observable. Rather than record that as a blind spot, the
 * invariant that makes it unreachable is asserted at AUTHOR time — add an
 * override naming a concept the extractor never emits and the guard reddens
 * immediately, instead of the field going permanently unfillable in production.
 */
export function compilerDecidableConcepts(): readonly string[] {
  return [
    ...new Set([
      ...CONCEPT_LABEL_OVERRIDES.map(([, concept]) => concept),
      ...Object.values(VEIN_GRID_CONCEPTS),
    ]),
  ];
}

/** The compiler's concept for this label, or null to let the model propose. */
export function conceptOverrideFor(originalLabel: string): string | null {
  for (const [pattern, concept] of CONCEPT_LABEL_OVERRIDES) {
    if (pattern.test(originalLabel)) return concept;
  }
  return null;
}

/**
 * A VEIN MEASUREMENT GRID DEFINES ITS OWN COLUMNS.
 *
 * In WM_IOV each grid row is [vein name + diameter, reflux time]. The reflux
 * cell says so in its own label; the diameter cell is labelled with the VEIN,
 * so it is not self-describing and the model chose its concept per field — 80
 * fields, one at a time. It chose `measurement.diameter` for the right leg and
 * `test.vascular_ultrasound.result` for the left, which the registry accepts by
 * pattern. The result: every right diameter filled and every left diameter came
 * back "no supporting fact", from an encounter that dictated both legs equally,
 * with nothing to show that the two halves of one grid had been read as
 * different kinds of thing.
 *
 * The structure decides it instead. A row that contains a REFLUX TIME cell is a
 * vein measurement row: that cell is reflux time, and the row's other data cell
 * — the one carrying the vein name — is the diameter. This is the same reading
 * of the grid the bridge already uses to pair note rows to IR rows, so the two
 * cannot drift apart.
 *
 * Returns null for anything that is not such a row, leaving the model's proposal
 * to stand.
 */
export function veinGridCellConcept(input: {
  originalLabel: string;
  isReflux: boolean;
  rowHasRefluxCell: boolean;
  isRowLabelCell: boolean;
}): string | null {
  if (!input.rowHasRefluxCell) return null;
  if (input.isReflux) return VEIN_GRID_CONCEPTS.reflux;
  return input.isRowLabelCell ? VEIN_GRID_CONCEPTS.diameter : null;
}

export type MappingSourceType =
  | 'extraction'
  | 'context_default'
  | 'visit_metadata'
  | 'manual'
  | 'verified_note_selection';

/**
 * Classify where a field's value legitimately comes from.
 *
 * MANUAL wins first: a per-visit human value stays manual even though it is
 * rendered as a dropdown, because nothing can select it from a dictation.
 *
 * Then VERIFIED_NOTE_SELECTION: a field with enumerated options is answered by
 * the live brain's constrained pick in the adopted note, not by matching an
 * extracted fact against option text. The options are protocol language
 * ("Bilateral Detailed", "Swelling, Heaviness") that no extractor emits, so
 * classifying these as `extraction` left fourteen of them permanently blank on
 * every real visit and blocked the native export — while the note had already
 * selected them correctly.
 */
export function classifyFieldSource(
  originalLabel: string,
  field?: { kind?: string; allowedOptions?: ReadonlyArray<unknown> },
): MappingSourceType {
  if (MANUAL_LABEL_PATTERNS.some((p) => p.test(originalLabel))) return 'manual';
  const enumerated =
    (field?.kind === 'single_select' || field?.kind === 'multi_select') &&
    (field?.allowedOptions?.length ?? 0) > 0;
  return enumerated ? 'verified_note_selection' : 'extraction';
}
