// ============================================================================
// THE CLOSED ROS LEXICON — RULING #179(1).
// ----------------------------------------------------------------------------
// ⚠️ WHY A CLOSED SET RATHER THAN FREE TEXT, AND WHY IT IS SHARED. The projector
// used to slug L3's free-text `finding` into a concept, which meant the concept
// space was whatever the model happened to say. Two consequences, both
// measured on the shipped code before this file existed:
//
//   · ONE SYMPTOM TICKED EVERY BOX. Every ROS field carried the same
//     `ros.<system>` concept, and `field-value-derivation`'s checkbox arm reads
//     ONLY `fact.polarity` — the finding is discarded. A doctor saying "reports
//     heartburn" affirmed heartburn, nausea, dysphagia and every other clause
//     in the system alike.
//   · TWO SYMPTOMS REFUSED THE DOCUMENT. `ros` is not in
//     ACCUMULATING_NARRATIVE_CONCEPTS, so a second affirmed finding became
//     `multiple_distinct_supported_values` and the export conflicted.
//
// Both are the same root: the concept could not ADDRESS the clause. #179 fixes
// it at the source — the model picks from a list, the schema enforces the list,
// and the concept becomes `ros.<system>.<symptom>`.
//
// ⚠️ ONE DEFINITION, TWO CONSUMERS. L3's structured-output schema and the
// projector both read this file. A second copy would drift the day either is
// edited, and a drifted lexicon is a concept the schema admits and the registry
// refuses — which is exactly the defect #179 exists to end.
//
// ⚠️ `other` IS ADMITTED AND DELIBERATELY UNADDRESSABLE. A symptom outside the
// list must not be silently dropped (that loses a doctor's finding) and must
// not match a specific clause (that asserts something the clause does not
// cover). `ros.<system>.other` therefore exists, carries its evidence, and is
// excluded from every declared scope by construction — see `isAddressable`.
// ============================================================================

/** The standard review-of-systems list, per system. */
export const ROS_LEXICON: Readonly<Record<string, readonly string[]>> = Object.freeze({
  constitutional: ['fever', 'chills', 'fatigue', 'weight_loss', 'weight_gain', 'appetite_change', 'night_sweats'],
  heent: ['headache', 'vision_change', 'hearing_loss', 'tinnitus', 'sore_throat', 'nasal_congestion'],
  cardiovascular: ['chest_pain', 'palpitations', 'orthopnea', 'edema', 'claudication', 'syncope'],
  respiratory: ['dyspnea', 'cough', 'wheezing', 'hemoptysis', 'pleuritic_pain'],
  gastrointestinal: [
    'heartburn', 'dysphagia', 'odynophagia', 'nausea', 'vomiting', 'abdominal_pain',
    'diarrhea', 'constipation', 'hematemesis', 'melena', 'hematochezia',
    'bloating', 'early_satiety', 'jaundice',
  ],
  genitourinary: ['dysuria', 'frequency', 'urgency', 'hematuria', 'incontinence', 'flank_pain'],
  musculoskeletal: ['joint_pain', 'joint_swelling', 'myalgia', 'back_pain', 'stiffness'],
  skin: ['rash', 'pruritus', 'lesion', 'hair_loss'],
  neurologic: ['dizziness', 'numbness', 'weakness', 'seizure', 'tremor', 'gait_change'],
  psychiatric: ['depressed_mood', 'anxiety', 'insomnia', 'suicidal_ideation'],
  endocrine: ['polyuria', 'polydipsia', 'heat_intolerance', 'cold_intolerance'],
  hematologic: ['easy_bruising', 'bleeding', 'lymphadenopathy'],
  allergic_immunologic: ['seasonal_allergies', 'frequent_infections'],
});

/** The catch-all every system admits. Never addressable by a specific clause. */
export const ROS_OTHER = 'other';

export const ROS_SYSTEMS: readonly string[] = Object.freeze(Object.keys(ROS_LEXICON));

/** Every symptom token a system admits, including `other`. */
export function symptomsFor(system: string): readonly string[] {
  const list = ROS_LEXICON[system];
  return list ? [...list, ROS_OTHER] : [ROS_OTHER];
}

/** `ros.<system>.<symptom>` — the only shape the projector emits. */
export function rosConcept(system: string, symptom: string): string {
  return `ros.${system}.${symptom}`;
}

/**
 * Is this concept allowed to satisfy a SPECIFIC scaffolded clause?
 *
 * ⚠️ `other` IS NOT, AND THAT IS THE POINT. It carries a real finding the
 * doctor stated, so it must reach the note somewhere — but it names a symptom
 * outside the lexicon, so no clause can claim to cover it. Letting it match
 * would assert that "the patient denies heartburn, dysphagia, odynophagia"
 * had been contradicted by a symptom none of those three words name.
 */
export function isAddressable(concept: string): boolean {
  const parts = concept.split('.');
  if (parts.length !== 3 || parts[0] !== 'ros') return false;
  if (parts[2] === ROS_OTHER) return false;
  return (ROS_LEXICON[parts[1]!] ?? []).includes(parts[2]!);
}

/** Total addressable symptoms — used to keep guards tied to the real corpus. */
export function lexiconSize(): number {
  return Object.values(ROS_LEXICON).reduce((n, list) => n + list.length, 0);
}
