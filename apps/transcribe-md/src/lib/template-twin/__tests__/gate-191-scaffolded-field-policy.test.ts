// ============================================================================
// RULING #191 — THE SCAFFOLDED-FIELD POLICY, AND ITS EMITTER.
// ----------------------------------------------------------------------------
// A doctor's form carries PRE-PRINTED CLINICAL PROSE inside its content
// controls — "The patient denies chest pain", an exam line with a static label.
// Those sentences are the template's own content, and when an encounter says
// nothing about them the correct outcome is that they STAY. `unmentionedPolicy`
// makes that a decision the mapping records rather than a behaviour nobody
// declared: `keep` (the default) leaves the scaffold alone, `omit` clears it
// with a reason token that says the clearing was deliberate.
//
// ⚠️ WHY THIS GATE EXISTS AT ALL: `default_kept` SHIPPED WITH NO EMITTER.
// Its status, its schema rules, its validator arm and its renderer proof kind
// all landed together and NOTHING IN THE CODEBASE PRODUCED IT. That is #170's
// exact shape — the ruling that exists because a third state was added to
// `blank` without its emitter and the owner's form went from 35 counted blanks
// to ZERO. A sentinel whose absence means "no" must be written on every path
// that earns a yes, and until this commit no path did.
//
// ⚠️ AND IT WAS UNEMITTABLE, NOT MERELY UNEMITTED — WHICH IS WHY NOBODY
// NOTICED. Two shipped validators contradicted each other: `ir.ts` REQUIRES a
// kept default to cite the facts that were evaluated, while the validator
// refused ANY citation whose facts fall outside the mapping's concept. At the
// only site that can emit the status, no cited fact CAN match the concept —
// having no concept match is the entire reason the field is unfilled. Every
// attempt to emit it failed one rule or the other. Measured: 39 arms of the
// denial contract failed blocking on the first attempt.
//
// ⚠️ WHAT THIS GATE DELIBERATELY DOES NOT CLAIM: that the DOCUMENT changes.
// It does not, and that is the point. `createFieldPatches` runs BEFORE any
// status is consulted, so a `default_kept` field and a `not_mentioned` field
// reach the same zero-patch branch and the rendered bytes are identical. The
// render-side proof of that already lives in `gate-157b-denial-contract`
// (the affirmed baseline asserts BLANK on a control that is now `default_kept`)
// and is NOT duplicated here. What moved is the CLAIM the proof makes about a
// field, not the doctor's page.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { FieldResolutionSchema } from '../ir';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

const SHA = 'b'.repeat(64);

function field(idSeed: string, overrides: Partial<TemplateField> = {}): TemplateField {
  return {
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind: 'narrative_text',
    originalLabel: 'Synthetic narrative_text',
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${idSeed}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown' as const,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
    ...overrides,
  };
}

function mapping(
  definition: TemplateField,
  concept: string,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  return {
    fieldId: definition.fieldId,
    sourceType: 'extraction' as const,
    clinicalConcept: concept,
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  };
}

function factFor(seed: string, concept: string, sentence: string): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value: sentence,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 10 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: sentence,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  };
}

/** One scaffold field the encounter never speaks to, plus one it does. */
function scenario(mappingOverrides: Partial<SemanticMapping> = {}) {
  const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
  const fields = [scaffold];
  const mappings = [mapping(scaffold, 'ros.cardiovascular', mappingOverrides)];
  // The encounter said something REAL — about a different concept. This is the
  // ordinary case: a form has more fields than any one visit discusses.
  const facts = [factFor('2', 'chief_complaint', 'Patient here for a rash.')];
  const resolutions = resolveTemplateFields({
    fields,
    mappings,
    facts,
    allowUncertifiedForSyntheticTest: true,
  });
  return { fields, mappings, facts, resolutions, resolution: resolutions[0]! };
}

describe('#191 — the scaffolded-field policy has an EMITTER', () => {
  it('(1) ⚠️ THE EMITTER EXISTS — an unmentioned keep-policy field resolves `default_kept`', () => {
    // The whole point. Before this commit the status was unreachable and this
    // field resolved `not_mentioned`, indistinguishable from a field nobody
    // examined.
    const { resolution } = scenario();
    expect(resolution.status).toBe('default_kept');
    expect(resolution.reasonCode).toBe('default_kept_uncontradicted');
  });

  it('(2) it CITES the facts it evaluated — the claim is "examined", not "supported"', () => {
    // `ir.ts` refuses an uncited kept default outright, because a kept default
    // citing nothing IS a field nobody examined. The citation is what separates
    // the two states.
    const { resolution, facts } = scenario();
    expect(resolution.sourceFactIds).toEqual(facts.map((f) => f.factId));
    expect(resolution.sourceFactIds.length).toBeGreaterThan(0);
  });

  it('(3) it WRITES NOTHING — no value, no selected option', () => {
    const { resolution } = scenario();
    expect(resolution.value).toBeNull();
    expect(resolution.selectedOptionOrdinal).toBeNull();
  });

  it('(4) KEEP IS THE DEFAULT — a mapping that never mentions the policy keeps', () => {
    // The owner's inversion: keep is the urgent half, so absence of a policy
    // must not clear a doctor's prose. `scenario()` sets no policy at all.
    const { mappings, resolution } = scenario();
    expect(mappings[0]!.unmentionedPolicy).toBeUndefined();
    expect(resolution.status).toBe('default_kept');
  });

  it('(5) OMIT clears, and says the clearing was DELIBERATE', () => {
    // `fact_not_mentioned` would read as "nobody looked". The distinct token is
    // the difference between an absence and a decision.
    const { resolution } = scenario({ unmentionedPolicy: 'omit' });
    expect(resolution.status).toBe('not_mentioned');
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
    expect(resolution.value).toBeNull();
  });

  it('(6) A REQUIRED FIELD STILL ASKS — a kept default never answers for a clinician', () => {
    const { resolution } = scenario({ required: true });
    expect(resolution.status).toBe('needs_clinician_input');
    expect(resolution.status).not.toBe('default_kept');
  });

  it('(7) ⚠️ AN ENCOUNTER THAT SAID NOTHING EARNS NOTHING', () => {
    // The non-vacuity guard, and it is not decoration: with zero facts there is
    // no evaluated set to cite, so the field genuinely WAS unexamined and the
    // weaker word is the honest one. This is also what makes `keep` safe as a
    // default — a mapping that evaluated nothing cannot reach the branch, so no
    // existing template's output moves.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const [resolution] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [mapping(scaffold, 'ros.cardiovascular')],
      facts: [],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(resolution!.status).toBe('not_mentioned');
    expect(resolution!.reasonCode).toBe('fact_not_mentioned');
  });

  it('(8) ⚠️ A DEFERRAL IS NOT AN ABSENCE — a named reason survives', () => {
    // Four call sites reach the same helper and only ONE of them means "the
    // encounter said nothing about this concept". The others hold facts and
    // defer: a grid row the resolver cannot address, a temporality the mapping
    // did not approve. A kept default there would answer a question that WAS
    // asked. Here the concept matches and only the temporality is wrong.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const [resolution] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [mapping(scaffold, 'ros.cardiovascular', { temporality: 'historical' })],
      facts: [factFor('2', 'ros.cardiovascular', 'Denies chest pain today.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(resolution!.status).not.toBe('default_kept');
    expect(resolution!.reasonCode).toBe('temporality_not_approved');
  });

  it('(9) the resolution VALIDATES — the two rules that made it unemittable now agree', () => {
    const { fields, mappings, facts, resolutions } = scenario();
    const result = validateTemplateTwin({
      fields,
      mappings,
      facts,
      resolutions,
      allowUncertifiedForSyntheticTest: true,
    });
    expect(result.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
    expect(result.valid).toBe(true);
  });

  it('(10) ⚠️ THE VALIDATOR EXEMPTION IS NARROW — every OTHER status still refuses foreign evidence', () => {
    // The exemption turns off ONE check for ONE valueless status. If it ever
    // widens, a POPULATED field could cite evidence about a different concept
    // entirely and ship — which is the defect the check exists for. This arm is
    // the control on my own fix.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const mapped = mapping(scaffold, 'ros.cardiovascular');
    const foreign = factFor('2', 'chief_complaint', 'Patient here for a rash.');
    const supported = FieldResolutionSchema.parse({
      fieldId: scaffold.fieldId,
      status: 'supported',
      value: 'Patient here for a rash.',
      sourceFactIds: [foreign.factId],
      evidenceAnchorIds: foreign.evidenceAnchorIds,
      selectedOptionOrdinal: null,
      reasonCode: 'direct_evidence_supported',
      clinicianReviewed: false,
    });
    const result = validateTemplateTwin({
      fields: [scaffold],
      mappings: [mapped],
      facts: [foreign],
      resolutions: [supported],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(
      result.issues.some(
        (i) => i.code === 'SOURCE_FACT_CONCEPT_MISMATCH' && i.severity === 'blocking',
      ),
    ).toBe(true);
  });

  it('(11) the SCHEMA still refuses a kept default that cites nothing, or that writes', () => {
    // Both rules predate this commit and neither is relaxed by the emitter.
    const base = {
      fieldId: `ttf_${'1'.repeat(24)}`,
      status: 'default_kept' as const,
      value: null,
      sourceFactIds: [] as string[],
      evidenceAnchorIds: [] as string[],
      selectedOptionOrdinal: null,
      reasonCode: 'default_kept_uncontradicted',
      clinicianReviewed: false,
    };
    expect(() => FieldResolutionSchema.parse(base)).toThrow(/cite the facts/i);
    expect(() =>
      FieldResolutionSchema.parse({
        ...base,
        sourceFactIds: [`ttfact_${'2'.repeat(24)}`],
        value: 'something',
      }),
    ).toThrow(/writes nothing/i);
  });
});
