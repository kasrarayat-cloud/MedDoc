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
  /**
   * ⚠️ ROS WAS EMITTED AND UNREGISTERED, AND THAT ASYMMETRY WAS THE DEFECT.
   *
   * `projectEncounterFacts` has emitted `ros.${system}` since §02.9, with
   * polarity STATED by L3 rather than inferred. Measured end-to-end on a
   * GI-shaped dictation before this line was added:
   *
   *   ros.gastrointestinal  polarity=affirmed  registered=FALSE
   *   ros.gastrointestinal  polarity=denied    registered=FALSE
   *   exam.abdomen          polarity=affirmed  registered=true
   *
   * `isRegisteredConcept` gates which concept a MAPPING may be assigned
   * (`semantic-mapping/index.ts:243,495`), so a review-of-systems field was
   * given `clinicalConcept: null` — and `factMatchesMapping` returns false on
   * a null concept. The doctor saying "the patient reports heartburn" produced
   * a well-formed, correctly-polarised fact that nothing could ever match,
   * one step before it could contradict a template's printed denial.
   *
   * The sibling patterns above are the precedent: `exam.*` and `hpi.*` are
   * composed the same way by the same projector and have always been admitted.
   */
  // ⚠️ #179(2) — THREE PARTS, NOT TWO. The first version of this line was
  // `/^ros\.[a-z0-9_.]+$/`, which admitted the bare `ros.<system>` the
  // projector then emitted — and a system-level concept cannot address a
  // clause. The refutation pass demonstrated both consequences: one affirmed
  // symptom ticked every checkbox in the system, and two affirmed symptoms
  // refused the whole document. Requiring the symptom segment makes the
  // system-level shape unrepresentable rather than merely discouraged.
  /^ros\.[a-z0-9_]+\.[a-z0-9_]+$/,
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

/**
 * SUB-CONCEPT MEMBERS — ruling #159(b).
 *
 * ⚠️ THESE ARE NOT `REGISTRY_SYNONYMS`, AND THE SEPARATION IS THE WHOLE POINT.
 * A SYNONYM is another SPELLING of the same concept: `impression` IS
 * `assessment`, so it folds through `canonicalConcept` and inherits everything
 * the canonical concept has — including whether it accumulates.
 *
 * A SUB-CONCEPT is a FINER GRANULARITY of a family: `medication.dose` is not
 * another word for `medication`, it is one field of one medication. It must
 * MATCH a mapping that cites the family, and it must NOT inherit the family's
 * accumulating behaviour.
 *
 * ⚠️ AND THAT DISTINCTION WAS FOUND BY A FULL-SUITE FAILURE, NOT BY REASONING.
 * The first version of #159(b) put these in `REGISTRY_SYNONYMS`. Because
 * `isListValuedNarrative` canonicalises FIRST, `medication.dose` folded to
 * `medication` — which IS on the accumulating allowlist — and
 * `gate-list-valued-narrative-sections` went red on the arm named "refuses to
 * join medication.dose". That arm exists because four refutation lenses
 * demonstrated the harm with concrete inputs: a dose field printing
 * "10 mg; 20 mg" onto a doctor's form with nothing blocking. Folding these
 * would have RE-OPENED a defect a previous adversarial pass had closed.
 *
 * `social_history.smoking` is the same shape and the same risk: on the owner's
 * live consult form, "Tobacco" is one status, not a section.
 *
 * So: they satisfy `isRegisteredConcept`, they are seeded into a mapping's
 * `approvedSynonyms` so `factSatisfiesMapping` accepts them, and
 * `canonicalConcept` DOES NOT fold them. Accumulation is decided by the
 * allowlist alone, exactly as it was.
 */
export const REGISTRY_SUBCONCEPTS: Readonly<Record<string, readonly string[]>> = {
  allergy: ['allergy.substance', 'allergy.reaction'],
  medication: [
    'medication.name',
    'medication.dose',
    'medication.route',
    'medication.frequency',
  ],
  family_history: ['family_history.relation', 'family_history.condition'],
  social_history: [
    'social_history.smoking',
    'social_history.alcohol',
    'social_history.drugs',
    'social_history.occupation',
  ],
};

/** Flat set of every sub-concept, for the registry predicate. */
const ALL_SUBCONCEPTS: ReadonlySet<string> = new Set(
  Object.values(REGISTRY_SUBCONCEPTS).flat(),
);

/**
 * Is this string a registered SUB-CONCEPT rather than a spelling?
 *
 * ⚠️ EXPORTED BECAUSE `approvedSynonyms` HAS A SECOND AUTHOR AND THE FIRST
 * VERSION OF #159(b) FORGOT IT. `synonymsFor` returns spellings only, which
 * made "no bare family offers its members" true of THIS module and false of the
 * SYSTEM: the proposer unions the MODEL's own `approvedSynonyms` into the
 * mapping, so a model answering `{clinicalConcept:'medication', approvedSynonyms:
 * ['medication.name','medication.dose', …]}` re-creates the destruction the
 * redesign exists to prevent — measured, `"Lisinopril; 10 mg; by mouth; daily;
 * Amlodipine"`, supported, zero blocking, a drug printed with no dose.
 *
 * A SYNONYM IS ANOTHER SPELLING OF THE SAME THING. A sub-concept is a finer
 * granularity, so it is never a legitimate synonym of its family — whoever
 * proposes it.
 */
export function isSubConcept(concept: string): boolean {
  return ALL_SUBCONCEPTS.has(concept.trim().toLowerCase());
}

export function isRegisteredConcept(concept: string): boolean {
  const c = concept.trim().toLowerCase();
  if (REGISTRY_CONCEPTS.includes(c)) return true;
  if (REGISTRY_PATTERNS.some((p) => p.test(c))) return true;
  if (ALL_SUBCONCEPTS.has(c)) return true;
  return Object.values(REGISTRY_SYNONYMS).some((list) => list.includes(c));
}

/** Every concept a mapping for this registry entry may legitimately cite. */
export function synonymsFor(concept: string): readonly string[] {
  // ⚠️ SPELLINGS ONLY — SUB-CONCEPTS ARE DELIBERATELY **NOT** RETURNED HERE, AND
  // THAT IS THE WHOLE SAFETY PROPERTY OF #159(b).
  //
  // The second version of this ruling returned sub-concepts too, so a mapping
  // citing the bare family had all four members seeded into its
  // `approvedSynonyms` and `factSatisfiesMapping` accepted every one. The
  // mandatory adversarial pass measured what that does, and every case below
  // was an honest BLANK before and `supported` with ZERO BLOCKING after — i.e.
  // it renders onto a document the clinician signs:
  //
  //   "Current Medications" -> `medication`, 8 facts in
  //        "Lisinopril; 10 mg; by mouth; daily; Amlodipine"
  //        Amlodipine's dose, route and frequency are DESTROYED, because the
  //        join de-duplicates exact repeats and every drug shares "by mouth"
  //        and "daily". The form states a drug with NO DOSE.
  //   "Allergies" -> `allergy`, 4 facts in
  //        "Penicillin; anaphylaxis; Cephalexin"
  //        anaphylaxis reads as an ALLERGEN, and cephalexin reads as having no
  //        recorded reaction.
  //   "Tobacco" -> `social_history`, 4 facts in
  //        "Occasional; Accountant"
  //        a TOBACCO field asserting the alcohol status and the occupation.
  //
  // The de-dup (`field-value-derivation.ts`) is CORRECT for what it was written
  // for: one fact per section ITEM, so a section never reads
  // "Hypertension; Hypertension". Seeding sub-concepts changes the population
  // to FOUR facts per item, and a legitimately repeating ATTRIBUTE value
  // becomes indistinguishable from a duplicate item. That is canon 74: the
  // assertion constrains manufacturing, and nothing was measuring destruction.
  //
  // ⚠️ AND THE SEEDING WAS NEVER NEEDED. What #159(b) must fix is that the
  // PROPOSER could not assign `social_history.smoking` to a "Tobacco" field at
  // all — it was off-registry, so it was silently nulled. Registering the
  // sub-concepts fixes that. A field then cites the sub-concept it actually
  // means, and matches facts DIRECTLY. Nothing needs the bare family to stand
  // in for its members, and letting it do so is what fabricates.
  return REGISTRY_SYNONYMS[concept.trim().toLowerCase()] ?? [];
}

/**
 * Synonym -> canonical. Built once from `REGISTRY_SYNONYMS` rather than written
 * out, so the two directions cannot disagree.
 */
const CANONICAL_BY_SYNONYM: ReadonlyMap<string, string> = new Map(
  Object.entries(REGISTRY_SYNONYMS).flatMap(([canonical, syns]) =>
    syns.map((s) => [s.trim().toLowerCase(), canonical] as const),
  ),
);

/**
 * THE CONCEPT A MAPPING REALLY MEANS.
 *
 * ⚠️ ADDED BY F5-i-2's ADVERSARIAL PASS, WHICH FOUND TWO DEFECTS SHARING THIS
 * ROOT — one of them a CLINICAL FABRICATION the change had just introduced.
 *
 * `REGISTRY_SYNONYMS` exists because a physician may legitimately approve an
 * alternative spelling, and `resolveTemplateFields` already honours it when
 * matching facts. Anything that CLASSIFIES a concept by reading its raw string
 * therefore sees a different vocabulary from the one that matches it.
 *
 * The two measured consequences, both with concrete inputs:
 *
 *   · `exam.vascular.diameter` is a synonym of `measurement.diameter` — it IS a
 *     measurement. A `startsWith('measurement.')` test says it is not, so it
 *     was classified as narrative and dictated as *"Examination of the vascular
 *     diameter: documented and unremarkable"* — invented prose about a
 *     measurement field, in an artifact the certification stores. Same for
 *     `exam.vascular.reflux_time`.
 *   · `impression` is a synonym of `assessment` and is an ordinary mapping on a
 *     consult form. A lookup keyed on the raw string finds no sentence for it,
 *     so the field is silently skipped and the form can be refused as
 *     unaddressable when it is nothing of the kind.
 *
 * Canonicalising first fixes both, and fixes them by GROUND rather than by hit:
 * every present and future synonym is covered, not the four that happen to
 * exist today.
 */
export function canonicalConcept(concept: string): string {
  const c = concept.trim().toLowerCase();
  return CANONICAL_BY_SYNONYM.get(c) ?? c;
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
