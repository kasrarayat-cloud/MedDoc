// ============================================================================
// EVALUATED AND KEPT IS NOT THE SAME AS NEVER LOOKED AT.
// ----------------------------------------------------------------------------
// A field nobody examined and a field whose template clause was examined and
// found uncontradicted both leave the doctor's scaffold untouched, and both
// used to earn the same `blank` proof. `blank` asserts exactly one thing —
// this field was not patched — which with the static-invariance check is a
// complete proof that the scaffold survived byte-identically.
//
// ⚠️ WHAT IT CANNOT SAY IS WHETHER ANYBODY LOOKED. On ROS and exam that is the
// clinical claim: "the patient denies chest pain" and "nobody asked about chest
// pain" must not produce the same proof.
//
// `default_kept` (resolution status) and `kept_default` (proof kind) separate
// them. The evidence is what earns the stronger word, so it is required in
// BOTH directions — by the schema when the resolution is built, and again at
// verification when the proof is read.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { countsAsBlankProof } from '../blank-proof-count';
import { FieldResolutionSchema } from '../ir';

const RESOLUTION = {
  fieldId: `ttf_${'a'.repeat(24)}`,
  status: 'default_kept' as const,
  value: null,
  sourceFactIds: [`ttfact_${'b'.repeat(24)}`],
  evidenceAnchorIds: ['anchor-1'],
  selectedOptionOrdinal: null,
  reasonCode: 'template_default_uncontradicted',
  clinicianReviewed: false,
};

describe('the default_kept resolution status', () => {
  it('⚠️ ACCEPTS a kept default that cites the facts it evaluated', () => {
    expect(FieldResolutionSchema.safeParse(RESOLUTION).success).toBe(true);
  });

  it('⚠️ REFUSES a kept default with no cited facts — that is just a blank', () => {
    // THE INVERSE CONSTRAINT. Everywhere else evidence is required BECAUSE
    // there is a value; here it is required because there is NOT one. Without
    // it the status is indistinguishable from a field nobody examined, which
    // is the exact conflation it exists to end.
    const r = FieldResolutionSchema.safeParse({ ...RESOLUTION, sourceFactIds: [] });
    expect(r.success).toBe(false);
    expect(JSON.stringify(r.error?.issues)).toMatch(/nobody examined/);
  });

  it('⚠️ REFUSES a kept default that carries a value — it writes NOTHING', () => {
    const withValue = FieldResolutionSchema.safeParse({ ...RESOLUTION, value: 'something' });
    expect(withValue.success).toBe(false);
    const withOption = FieldResolutionSchema.safeParse({
      ...RESOLUTION,
      selectedOptionOrdinal: 0,
    });
    expect(withOption.success).toBe(false);
  });

  it('a NON-kept-default resolution is unaffected by the new constraint', () => {
    // ⚠️ NON-VACUITY IN THE OTHER DIRECTION: the new rule must not have made
    // every value-less resolution require evidence. `not_mentioned` with no
    // facts is legal and must stay legal.
    const notMentioned = FieldResolutionSchema.safeParse({
      ...RESOLUTION,
      status: 'not_mentioned',
      sourceFactIds: [],
      evidenceAnchorIds: [],
    });
    expect(notMentioned.success).toBe(true);
  });
});

describe('the kept_default proof kind at the read path', () => {
  it('⚠️ COUNTS as a blank-class proof — it is the STRONGER of the two', () => {
    const ctx = {
      bindingOf: () => 'narrative_text',
      resolvedNull: () => true,
      kindOf: () => 'narrative_text',
    };
    expect(
      countsAsBlankProof({ kind: 'kept_default', fieldId: 'ttf_x', blankEligible: 'eligible' }, ctx),
      'a kept default was denied the credit a plain blank receives',
    ).toBe(true);
  });

  it('an UNKNOWN kind still fails closed', () => {
    // the admission is an allowlist, not a relaxation
    const ctx = {
      bindingOf: () => 'narrative_text',
      resolvedNull: () => true,
      kindOf: () => 'narrative_text',
    };
    expect(countsAsBlankProof({ kind: 'kept_defaultish', fieldId: 'ttf_x', blankEligible: 'eligible' }, ctx)).toBe(false);
    expect(countsAsBlankProof({ kind: 'filled', fieldId: 'ttf_x', blankEligible: 'eligible' }, ctx)).toBe(false);
  });
});

describe('the certification floor is not inflated by a kept default', () => {
  it('⚠️ a kept default writes NOTHING, so it must not count as fill coverage', () => {
    // MIN_CERTIFIED_FILLED_FIELDS filters on `value !== null`. A kept default
    // has a null value by construction (asserted above), so it cannot inflate
    // the floor. Asserted here because the property is load-bearing and lives
    // in a different file from the schema that guarantees it.
    const parsed = FieldResolutionSchema.parse(RESOLUTION);
    expect(parsed.value).toBeNull();
  });
});
