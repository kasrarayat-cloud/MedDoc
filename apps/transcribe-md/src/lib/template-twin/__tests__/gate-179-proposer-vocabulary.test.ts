/**
 * ⚠️ THE PROPOSER'S VOCABULARY MUST BE A SUBSET OF WHAT THE REGISTRY ACCEPTS.
 *
 * THREE VOCABULARIES HAVE TO AGREE and only two of the seams were gated: what
 * L3 can EMIT, what the registry ACCEPTS, and what the mapping proposer is
 * TAUGHT. Nothing bound the third, and it drifted.
 *
 * MEASURED on the branch before this arm existed: `ros.<system>` — the form the
 * proposer's own canonical guidance told the model to produce — instantiates to
 * 13 concepts, and the registry REFUSES ALL THIRTEEN.
 * `isRegisteredConcept('ros.gastrointestinal')` is FALSE, because #179(2)
 * narrowed the pattern to the three-part `ros.<system>.<symptom>` when the
 * projector moved to symptom granularity.
 *
 * ⚠️ THE CONSEQUENCE IS NOT COSMETIC AND IT IS WHY THE OWNER'S FORM COULD NOT
 * CERTIFY. The mapping proposer is the component that assigns a clinical
 * concept to a form field. Taught a form the registry refuses, every ROS field
 * landed `clinicalConcept: null` — so a per-clause ROS control had no concept,
 * could never be filled, and could never be certified. The feature was
 * unreachable end to end while every test was green.
 *
 * ⚠️ `exam.<system>` IS FINE AND IS NOT CHANGED. `isRegisteredConcept('exam.abdomen')`
 * is true. Only ros went three-part, so this was a one-line asymmetry — which
 * is exactly the kind a human eye slides over and an arm does not.
 */
import { describe, it, expect } from 'vitest';
import { TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE } from '../semantic-mapping';
import { isRegisteredConcept } from '../concept-registry';
import { ROS_SYSTEMS, symptomsFor } from '../ros-lexicon';

/**
 * A guidance entry may carry a `<placeholder>`. Instantiate it with REAL values
 * drawn from the shipped vocabularies — never with an invented string, or the
 * arm measures the invention.
 */
function instantiate(entry: string): string[] {
  if (!entry.includes('<')) return [entry];
  switch (entry) {
    case 'ros.<system>.<symptom>':
      return ROS_SYSTEMS.flatMap((s) => symptomsFor(s).map((sym) => `ros.${s}.${sym}`));
    case 'exam.<system>':
      return ROS_SYSTEMS.map((s) => `exam.${s}`);
    case 'test.<test_name>.result':
      return ['test.venous_duplex.result'];
    default:
      return [];
  }
}

describe('the mapping proposer is taught only concepts the registry accepts', () => {
  it('NON-VACUITY: the guidance is a real, populated list with placeholders in it', () => {
    // Without this, "no entry is refused" is satisfied by an empty list, and
    // the placeholder arm is satisfied by a list with no placeholders.
    expect(TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE.length).toBeGreaterThan(20);
    const withPlaceholders = TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE.filter((e) => e.includes('<'));
    expect(withPlaceholders.length).toBeGreaterThan(0);
    // And every placeholder entry must be one this arm knows how to expand —
    // otherwise a new one is silently skipped and never checked at all.
    for (const entry of withPlaceholders) {
      expect(instantiate(entry).length, `no instantiation known for "${entry}"`).toBeGreaterThan(0);
    }
  });

  it('⚠️ every guidance entry instantiates to a REGISTERED concept', () => {
    const refused: string[] = [];
    for (const entry of TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE) {
      for (const concept of instantiate(entry)) {
        if (!isRegisteredConcept(concept)) refused.push(`${entry} -> ${concept}`);
      }
    }
    expect(
      refused,
      `the proposer teaches concepts the registry refuses: ${refused.slice(0, 5).join('; ')}`,
    ).toEqual([]);
  });

  it('DISCRIMINATION: the registry really does refuse the two-part ros form', () => {
    // The arm above passes trivially against a registry that accepts
    // everything. This is what says it does not — and it is the exact string
    // the guidance used to carry.
    expect(isRegisteredConcept('ros.gastrointestinal')).toBe(false);
    expect(isRegisteredConcept('ros.gastrointestinal.heartburn')).toBe(true);
    // ...and the sibling family that legitimately IS two-part still is, so the
    // refusal is about ros and not about arity.
    expect(isRegisteredConcept('exam.abdomen')).toBe(true);
  });
});
