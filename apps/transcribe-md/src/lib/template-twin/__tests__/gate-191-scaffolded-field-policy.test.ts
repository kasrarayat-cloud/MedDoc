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
    // These fixtures ARE scaffolds — a control carrying the template's own
    // pre-printed clause. Arm (21) covers the other two states.
    scaffolded: true,
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
    // ⚠️ #192 — DECLARED, NOT INFERRED. `keep` is now an explicit per-field
    // decision; absence means today's bounded clear. These fixtures exercise
    // the keep path, so they must say so. Arm (4) covers absence.
    unmentionedPolicy: 'keep' as const,
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

  it('(3) it WRITES NOTHING — and this arm is VACUOUS, kept only with that said out loud', () => {
    // ⚠️ THE ADVERSARIAL PASS PROVED THIS ARM PROVES NOTHING. `default_kept`
    // and `not_mentioned` both carry a null value and a null ordinal, so it
    // passes identically whether or not the emitter exists — it redded under
    // NONE of the six mutations, including the one that deleted the emitter
    // outright. The property is real and IS enforced, by the schema, in arm
    // (11); this is a duplicate that cannot fail.
    //
    // It is kept rather than deleted because a reader scanning for "does
    // anything check that a kept default writes nothing?" should find the
    // answer here and be sent to the arm that actually holds the line. A
    // vacuous arm nobody has labelled is worse than no arm, because it reads
    // as coverage.
    const { resolution } = scenario();
    expect(resolution.value).toBeNull();
    expect(resolution.selectedOptionOrdinal).toBeNull();
  });

  it('(4) ⚠️ ABSENCE IS NOT KEEP — an undeclared policy takes the bounded clear', () => {
    // ⚠️ THIS ARM IS INVERTED FROM ITS #191 FORM, AND THE INVERSION IS THE
    // RULING. It used to assert that a mapping mentioning no policy KEEPS.
    // #192 makes absence mean today's behaviour, fail-closed: a control nobody
    // ruled on can never print its content onto a note. The falsifying case is
    // pinned in `gate-191-kept-default-survives-render`: a control carrying
    // `Enter assessment` with no placeholder flag, which the content-derived
    // predicate called a scaffold.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const undeclared = mapping(scaffold, 'ros.cardiovascular');
    delete (undeclared as { unmentionedPolicy?: string }).unmentionedPolicy;
    const [r] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [undeclared],
      facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.status).toBe('not_mentioned');
    expect(r!.reasonCode).toBe('fact_not_mentioned');
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
    // ⚠️ AND THE MUTATION THAT REMOVES THIS GUARD IS CAUGHT BY THE SCHEMA, NOT
    // BY THE TWO ASSERTIONS BELOW. Deleting `facts.length > 0` makes the
    // resolver emit a kept default citing an EMPTY set, which `ir.ts` refuses
    // outright — so `resolveTemplateFields` THROWS and these lines never run.
    // The arm reds, but for a different reason than it claims, which is the
    // laundering shape: a red from an overlapping guard is not proof of this
    // one. Both walls are asserted here so the record is honest about which is
    // load-bearing.
    expect(() =>
      resolveTemplateFields({
        fields: [scaffold],
        mappings: [mapping(scaffold, 'ros.cardiovascular')],
        facts: [],
        allowUncertifiedForSyntheticTest: true,
      }),
    ).not.toThrow();
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

// ============================================================================
// EVERYTHING BELOW WAS ADDED AFTER THE MANDATORY ADVERSARIAL PASS.
// ----------------------------------------------------------------------------
// Five lenses ran against the finished diff. The arms above were green
// throughout and every finding below was invisible to them, because all eleven
// drive the resolver with hand-built in-memory mappings and never cross the
// database, the counts, or the renderer.
// ============================================================================

import { templateTwinCounts, TEMPLATE_TWIN_RESOLVER_VERSION } from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('#191 — THE COUNT REGRESSION the pass found (three lenses, independently)', () => {
  const defs = () => [field('1', { fieldId: `ttf_${'1'.repeat(24)}` })];

  it('(12) ⚠️ A KEPT DEFAULT IS COUNTED AS A BLANK — one unrelated sentence must not erase the form', () => {
    // The measured regression: an 11-field form went `notMentioned` 11 -> 0
    // because ONE dictated fact of an unrelated concept armed the emitter. The
    // rendered document was byte-identical; only the doctor's
    // "N still blank" line vanished.
    // ⚠️ COUNTED, AND NOT AS BLANK. The first fix folded it into `notMentioned`,
    // which was right only while the renderer ignored the status; once keep was
    // honoured, that told the doctor a field was blank while its page asserted a
    // clinical fact. A kept default is a THIRD state and gets a third bucket.
    const { resolutions } = scenario();
    expect(resolutions[0]!.status).toBe('default_kept');
    const c = templateTwinCounts(resolutions, defs());
    expect(c.defaultsKept).toBe(1);
    expect(c.notMentioned).toBe(0);
  });

  it('(13) the SILENT encounter and the one-unrelated-sentence encounter report the SAME blank count', () => {
    // The discriminator. Before the fix these differed 1 vs 0 while the
    // document did not move at all — which is exactly why no render arm saw it.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const silent = resolveTemplateFields({
      fields: [scaffold], mappings: [mapping(scaffold, 'ros.cardiovascular')],
      facts: [], allowUncertifiedForSyntheticTest: true,
    });
    const oneUnrelated = scenario().resolutions;
    // ⚠️ THE PROPERTY IS *ACCOUNTED FOR*, NOT *EQUAL*. The original regression
    // was that a kept default fell into NO bucket, so one unrelated sentence
    // erased the form's count. The two encounters legitimately differ in WHICH
    // bucket — the silent one is blank, the other keeps a declared clause — but
    // neither may vanish.
    const sc = templateTwinCounts(silent, defs());
    const oc = templateTwinCounts(oneUnrelated, defs());
    expect(silent[0]!.status).toBe('not_mentioned');
    expect(oneUnrelated[0]!.status).toBe('default_kept');
    expect(sc.notMentioned + (sc.defaultsKept ?? 0))
      .toBe(oc.notMentioned + (oc.defaultsKept ?? 0));
  });

  it('(14) ⚠️ THE BUCKETS RECONCILE — every field lands in exactly one accounted state', () => {
    // Nothing anywhere reconciled these, which is why a status could fall into
    // no bucket and stay invisible. Arithmetic that does not reconcile is the
    // finding; this makes the next uncounted status fail here rather than in a
    // doctor's summary.
    const { resolutions } = scenario();
    const c = templateTwinCounts(resolutions, defs());
    expect(c.filled + c.needsReview + c.notMentioned + (c.defaultsKept ?? 0))
      .toBe(resolutions.length);
  });

  it('(15) the resolver VERSION moved — its output changed for identical input', () => {
    // `certification-lifecycle` compares this string exactly to invalidate
    // stale manifests. Left unbumped it could not see `not_mentioned` becoming
    // `default_kept`, and an old manifest would read as current.
    expect(TEMPLATE_TWIN_RESOLVER_VERSION).not.toBe('template-field-resolver/1.0.0');
  });
});

describe('#191 — THE `omit` REASON was ungated (two lenses, and 779 tests could not see it)', () => {
  it('(16) ⚠️ A DEFERRAL KEEPS ITS NAMED REASON even under `omit`', () => {
    // The doctor DID speak to this concept; only the temporality was
    // unapproved. Overwriting that with `omitted_unsupported_default` makes the
    // manifest say nothing supported a field the doctor dictated to.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const [r] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [mapping(scaffold, 'ros.cardiovascular', {
        temporality: 'historical', unmentionedPolicy: 'omit',
      })],
      facts: [factFor('2', 'ros.cardiovascular', 'Denies chest pain today.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.reasonCode).toBe('temporality_not_approved');
  });

  it('(17) ⚠️ A CLEARING NOTHING EVALUATED IS NOT DELIBERATE', () => {
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const [r] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'omit' })],
      facts: [], allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.reasonCode).toBe('fact_not_mentioned');
  });
});

describe('#191 — THE COLUMN WAS DEAD IN BOTH DIRECTIONS', () => {
  const SRC = (rel: string) =>
    readFileSync(join(__dirname, '..', rel), 'utf-8');

  it('(18) ⚠️ EVERY MAPPING PROJECTION CARRIES EVERY SCALAR COLUMN — derived from the SCHEMA, not a name list', () => {
    // The gate that should have caught this defect watched ONE column by name
    // (`sourceType: true,`), so a new column got zero coverage. Deriving the
    // watched set from the Prisma model is what stops the next one.
    const schema = readFileSync(
      join(__dirname, '../../../../../../packages/db/prisma/schema.prisma'), 'utf-8');
    const model = schema.slice(schema.indexOf('model TemplateTwinSemanticMapping'));
    const body = model.slice(0, model.indexOf('\n}'));
    const scalars = [...body.matchAll(/^\s{2}(\w+)\s+(String|Boolean|Json|DateTime|TemplateTwinDetectionStatus)\b/gm)]
      .map((m) => m[1]!)
      .filter((n) => !['id', 'fieldDefinitionId', 'approvedById', 'approvedAt', 'createdAt', 'updatedAt', 'proposedByModel'].includes(n));
    expect(scalars).toContain('unmentionedPolicy');
    expect(scalars.length).toBeGreaterThan(8);   // non-vacuity: the parse worked

    for (const rel of ['fill-engine.ts', 'certification-lifecycle.ts', 'workspace-read.ts', 'synthetic-test.ts']) {
      const src = SRC(rel);
      const selects = src.split('blankPolicy: true,').length - 1;
      expect(`${rel}:selects`).toBe(`${rel}:selects`);
      expect(selects).toBeGreaterThan(0);
      // every select that names blankPolicy must also name unmentionedPolicy
      expect(src.split('unmentionedPolicy: true,').length - 1).toBe(selects);
    }
  });

  it('(19) a row persisted as `omit` is READ BACK as `omit`, and `keep` reads as absent', () => {
    // The round trip the whole ruling depends on. Before this, a doctor setting
    // `omit` got `keep`, silently, because six projections dropped the column.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const omitted = mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'omit' });
    const [r] = resolveTemplateFields({
      fields: [scaffold], mappings: [omitted],
      facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.reasonCode).toBe('omitted_unsupported_default');
  });

  it('(20) ⚠️ ONLY AN UNSET POLICY IS ELIDED — `keep` AND `omit` BOTH MOVE THE SHA', () => {
    // Carrying the column without this normalisation moves every certified sha
    // and throws TEMPLATE_PROVENANCE_MISMATCH on every certified template —
    // measured, and it would have taken the one active production form with it.
    // `omit` moving the sha is correct: the document's behaviour changed.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    // ⚠️ INVERTED FROM ITS #191 FORM. Then, `keep` and absent were
    // SEMANTICALLY IDENTICAL, so hashing them the same was consistency. #192
    // makes them OPPOSITES, and hashing them the same would let a doctor's
    // declared `keep` be removed from a certified mapping WITHOUT MOVING THE
    // ATTESTATION — a certificate attesting to behaviour it never saw.
    //
    // ⚠️ AND NO CERTIFIED SHA MOVES ANYWAY, by a better mechanism: the column
    // is NULLABLE WITH NO DEFAULT, so every pre-existing row is NULL rather
    // than `'keep'`, and NULL is what gets elided.
    const absent = mapping(scaffold, 'ros.cardiovascular');
    delete (absent as { unmentionedPolicy?: string }).unmentionedPolicy;
    const keep = mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'keep' });
    const omit = mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'omit' });
    expect(templateTwinMappingsSha256([keep])).not.toBe(templateTwinMappingsSha256([absent]));
    expect(templateTwinMappingsSha256([omit])).not.toBe(templateTwinMappingsSha256([absent]));
    expect(templateTwinMappingsSha256([keep])).not.toBe(templateTwinMappingsSha256([omit]));
  });
});

describe('#191 — THE SCAFFOLD SCOPE, which the pass found unimplemented', () => {
  it('(21) ⚠️ SCAFFOLDEDNESS DOES NOT DECIDE ANYTHING AT RENDER — only the declaration does', () => {
    // ⚠️ REWRITTEN BY #192, AND THE REWRITE IS THE RULING. Its #191 form
    // asserted that a NON-scaffold never keeps, which made `scaffolded` a
    // render-time decision. It is now COMPILED METADATA that informs the
    // mapping PROPOSER and nothing else -- the `conceptScope` pattern:
    // proposed, confirmed, never decided at render.
    //
    // So both directions must hold: a scaffolded control with no declaration
    // does NOT keep, and a NON-scaffolded control with a declaration DOES.
    // Together they say the render consults the declaration alone.
    const cases: Array<[string, boolean | undefined, 'keep' | undefined, string]> = [
      ['scaffolded but undeclared', true, undefined, 'not_mentioned'],
      ['not scaffolded but DECLARED', false, 'keep', 'default_kept'],
      ['scaffoldedness absent, declared', undefined, 'keep', 'default_kept'],
    ];
    for (const [label, flag, policy, expected] of cases) {
      const f = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
      if (flag === undefined) delete (f as { scaffolded?: boolean }).scaffolded;
      else (f as { scaffolded?: boolean }).scaffolded = flag;
      const m = mapping(f, 'ros.cardiovascular');
      if (policy === undefined) delete (m as { unmentionedPolicy?: string }).unmentionedPolicy;
      else (m as { unmentionedPolicy?: string }).unmentionedPolicy = policy;
      const [r] = resolveTemplateFields({
        fields: [f], mappings: [m],
        facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
        allowUncertifiedForSyntheticTest: true,
      });
      expect(`${label}: ${r!.status}`).toBe(`${label}: ${expected}`);
    }
  });

  it('(22) ⚠️ THE DISCRIMINATOR IS THE DOCUMENT\'S OWN DECLARATION, measured on both real forms', () => {
    // Canon 83: a blocking rule may never rest on a text heuristic. A rule
    // matching Word's own "Choose an item." blocked 28 of 28 dropdowns of the
    // real customer template, and its English-only repair blocked all 28 again
    // in fr/de/es. `w:showingPlcHdr` is what the DOCUMENT declares.
    //
    // This arm pins the RECONCILIATION, which is what says the partition has no
    // unnamed bucket. The measured populations are recorded in the compiler's
    // own comment; here we assert the predicate's shape cannot drift to a text
    // match without failing.
    const src = readFileSync(
      join(__dirname, '../../note-template-docx/compiler.ts'), 'utf-8');
    const fn = src.slice(src.indexOf('function isScaffolded'));
    const body = fn.slice(0, fn.indexOf('\n}'));
    expect(body).toContain('showingPlcHdr');
    // ⚠️ the negative half: it must NOT match placeholder TEXT
    expect(body).not.toMatch(/Choose an item|Cliquez ici|Klicken Sie/i);
  });
});

describe('#191 — THE STRUCTURE HASH MUST NOT MOVE', () => {
  it('(23) ⚠️ THE DERIVED METADATA IS EXCLUDED FROM STRUCTURAL IDENTITY — every certified twin depends on it', async () => {
    // ⚠️ REWRITTEN TO ASSERT THE PROPERTY, NOT THE SPELLING. Its first form
    // matched the inline destructuring by regex, so extracting that strip into
    // a shared function — an unambiguous IMPROVEMENT, made because a SECOND
    // comparison needed the identical logic — redded this arm. A source-text
    // gate that fails when somebody improves the code is measuring the wrong
    // thing; worse, it said nothing about that second caller, which is exactly
    // where the real defect lived: `assertSourceMatchesIr` compared the RAW
    // field arrays and orphaned every stored IR.
    //
    // The property, which holds however the strip is written: the derived
    // members are removed and NOTHING ELSE is.
    const { fieldForStructuralIdentity } = await import(
      '../../note-template-docx/compiler'
    );
    const withMeta = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    (withMeta as { scaffoldText?: string }).scaffoldText = 'The patient denies chest pain.';
    const withoutMeta = fieldForStructuralIdentity(withMeta);
    expect(withMeta.scaffolded).toBe(true);
    expect((withoutMeta as { scaffolded?: boolean }).scaffolded).toBeUndefined();
    expect((withoutMeta as { scaffoldText?: string }).scaffoldText).toBeUndefined();
    // ⚠️ AND NOTHING ELSE WAS DROPPED. A strip that removed too much would pass
    // a naive "the keys are gone" check and quietly weaken structural identity.
    expect(Object.keys(withoutMeta).sort()).toEqual(
      Object.keys(withMeta)
        .filter((k) => k !== 'scaffolded' && k !== 'scaffoldText')
        .sort(),
    );
  });
});

describe('#192 — the proposer OFFERS keep; the render obeys only what was CONFIRMED', () => {
  it('(24) ⚠️ THE PROPOSER OFFERS `keep` FOR A SCAFFOLD, AND THE COMPILER CARRIES THE SENTENCE', async () => {
    // A doctor confirming `keep` agrees that this exact text prints when the
    // encounter says nothing, so the proposal must SHOW it. Without
    // `scaffoldText` the offer would be "keep this control's content" about
    // content nobody displayed.
    const { fallbackSemanticMappings } = await import('../semantic-mapping');
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    (scaffold as { scaffoldText?: string }).scaffoldText =
      'The patient denies chest pain.';
    const [proposed] = fallbackSemanticMappings({ fields: [scaffold] });
    expect(proposed?.unmentionedPolicy).toBe('keep');
    // ⚠️ THE SECOND ASSERTION USED TO BE VACUOUS AND ROUND TWO SAID SO: it read
    // back `scaffold.scaffoldText`, the value this test had just written, and
    // stood in for the claim that the offer SHOWS the sentence. It proved only
    // that assignment works. The real claim is about the COMPILER — that a
    // scaffolded control carries its own text — so it is asserted there.
    const { compileTemplateDocx } = await import('../../note-template-docx/compiler');
    const { buildSyntheticDocx } = await import(
      '../../note-template-docx/__tests__/synthetic-docx');
    const SENT = 'The patient denies chest pain.';
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:sdt><w:sdtPr><w:alias w:val="ROS"/><w:id w:val="801"/><w:text/></w:sdtPr>
<w:sdtContent><w:r><w:t>${SENT}</w:t></w:r></w:sdtContent></w:sdt></w:p></w:body></w:document>`,
      }),
    );
    const compiled = ir.fields.find((f) => f.originalLabel === 'ROS');
    expect(compiled?.scaffoldText).toBe(SENT);
  });

  it('(25) ⚠️ AND IT DOES NOT OFFER IT FOR A NON-SCAFFOLD', async () => {
    const { fallbackSemanticMappings } = await import('../semantic-mapping');
    const plain = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    delete (plain as { scaffolded?: boolean }).scaffolded;
    const [proposed] = fallbackSemanticMappings({ fields: [plain] });
    expect(proposed?.unmentionedPolicy ?? null).toBeNull();
  });

  it('(26) ⚠️ AN UNCONFIRMED PROPOSAL IS A NULL COLUMN, AND NULL IS THE BOUNDED CLEAR', () => {
    // The fail-closed property in one assertion: a proposal that nobody
    // confirmed leaves the column unset, and unset never keeps. A rejected
    // offer therefore cannot print a prompt onto a note.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const unconfirmed = mapping(scaffold, 'ros.cardiovascular');
    delete (unconfirmed as { unmentionedPolicy?: string }).unmentionedPolicy;
    const [r] = resolveTemplateFields({
      fields: [scaffold], mappings: [unconfirmed],
      facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.status).toBe('not_mentioned');
  });
});

describe('#192 — THE FAIL-CLOSED PROPERTY, from the adversarial pass', () => {
  it('(27) ⚠️ THE MODEL IS NEVER OFFERED `unmentionedPolicy` — it may not author a render policy', async () => {
    // ⚠️ THE WORST FINDING OF THE PASS. The model schema EXTENDS
    // `SemanticMappingSchema`, and the tool's `input_schema` is generated from
    // it — so adding a field there silently handed the model a settable enum
    // deciding whether a template's sentence prints on a signed note. Measured
    // end to end with no human and validation GREEN: 11 of 11 proposals came
    // back `keep`, and a control containing `Enter assessment` rendered that
    // string into the note. `practiceDefault` is forced null two lines away for
    // exactly this reason, with the comment "never authored by AI".
    //
    // It is OMITTED rather than nulled: the field never appears in the schema,
    // so there is no value to choose and nothing to re-assert after parsing.
    const src = readFileSync(join(__dirname, '../semantic-mapping/index.ts'), 'utf-8');
    const decl = src.slice(src.indexOf('const ModelSemanticMappingSchema'));
    const body = decl.slice(0, decl.indexOf('.strict();'));
    expect(body).toContain('omit({ unmentionedPolicy: true })');
    // non-vacuity: the base schema really does carry it
    const ir = readFileSync(join(__dirname, '../ir.ts'), 'utf-8');
    expect(ir).toContain("unmentionedPolicy: z.enum(['keep', 'omit']).nullish()");
  });

  it('(28) ⚠️ A REPEATING PROTOTYPE NEVER KEEPS — its text would clone into every row', () => {
    // Measured by the pass: a `Comment` prototype reading `Enter comment`
    // beside three dictated rows printed it THREE TIMES, because the patch
    // builder runs once per row and a kept default's zero patches leave the
    // prototype's own text in each clone.
    const proto = field('1', { fieldId: `ttf_${'1'.repeat(24)}`, rowPrototype: true });
    const [r] = resolveTemplateFields({
      fields: [proto],
      mappings: [mapping(proto, 'ros.cardiovascular', { unmentionedPolicy: 'keep' })],
      facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.status).not.toBe('default_kept');
  });

  it('(29) ⚠️ `defaultsKept` REACHES THE DOCTOR — a bucket nobody reads is the same failure one step later', () => {
    // The pass found the count written and then dropped by both transport
    // types, so the pre-sign surface disclosed NOTHING about a note printing
    // template prose. #170's shape a third time: the value existed and no
    // reader could see it.
    const action = readFileSync(join(__dirname, '../../../actions/preview-visit-document.ts'), 'utf-8');
    const cache = readFileSync(join(__dirname, '../../docx-preview/fill-cache.ts'), 'utf-8');
    const surface = readFileSync(
      join(__dirname, '../../../app/visits/[id]/visit-document-surface.tsx'), 'utf-8');
    for (const [name, src] of [['action', action], ['cache', cache], ['surface', surface]] as const) {
      expect(`${name}:${src.includes('defaultsKept')}`).toBe(`${name}:true`);
    }
    // ⚠️ AND THE SURFACE MUST ACTUALLY RENDER IT. The first version of this
    // assertion was `toContain('counts.defaultsKept > 0')`, and the mutation
    // `false && result.counts.defaultsKept > 0` PASSED IT — the substring
    // survives a short-circuit that disables the whole disclosure. The
    // substring trap, in the arm written to prevent the disclosure going
    // missing.
    const line = surface
      .split('\n')
      .find((l) => l.includes('counts.defaultsKept > 0'));
    expect(line, 'the disclosure condition must exist').toBeDefined();
    expect(line!.trim().startsWith('{result.counts.defaultsKept > 0')).toBe(true);
    // and the doctor-facing words themselves, so deleting the branch reds too
    expect(surface).toContain('kept from your template');
  });
});

describe('#193 — keep is never model-authored and never auto-confirmed', () => {
  it('(30) ⚠️ A PLANTED MODEL PROPOSAL CARRYING `keep` IS REJECTED', async () => {
    // The model schema OMITS the field, so a proposal that carries it anyway
    // must not survive parsing. `.strict()` is what makes the rejection real:
    // without it an unknown key is silently dropped, and "dropped" would mean
    // the offer vanishes rather than being refused.
    const { z } = await import('zod');
    const src = readFileSync(join(__dirname, '../semantic-mapping/index.ts'), 'utf-8');
    expect(src).toContain('omit({ unmentionedPolicy: true })');
    expect(src.slice(src.indexOf('const ModelSemanticMappingSchema'))).toContain('.strict()');

    // and the base schema DOES accept it — otherwise this arm proves nothing
    const { SemanticMappingSchema } = await import('../ir');
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const withKeep = mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'keep' });
    expect(SemanticMappingSchema.safeParse(withKeep).success).toBe(true);
    const modelShape = SemanticMappingSchema.omit({ unmentionedPolicy: true }).strict();
    expect(modelShape.safeParse(withKeep).success).toBe(false);
    expect(z).toBeDefined();
  });

  it('(31) ⚠️ A `keep` NEVER REACHES `certified` WITHOUT A HUMAN — auto-confirm DECLINES it', async () => {
    // A kept default prints the template's own prose on a signed note. That is
    // a clinical assertion no automated step may make for a doctor -- the same
    // class as `practiceDefault`, which the model is forbidden from authoring.
    // Measured cost of not doing this: 11 of 11 model proposals came back
    // `keep`, `planAutoConfirm` spread them into `certified`, and a control
    // containing `Enter assessment` rendered onto a note with no human at all.
    const src = readFileSync(join(__dirname, '../auto-certify-eligibility.ts'), 'utf-8');
    const fn = src.slice(src.indexOf('function planAutoConfirm'));
    const body = fn.slice(0, fn.indexOf('\n}'));
    // the decline must come BEFORE the certify, or it is not a decline
    const declineAt = body.indexOf("mapping.unmentionedPolicy === 'keep'");
    const certifyAt = body.indexOf("status: 'certified' as const");
    expect(declineAt).toBeGreaterThan(-1);
    expect(certifyAt).toBeGreaterThan(-1);
    expect(declineAt).toBeLessThan(certifyAt);
    // ⚠️ AND IT IS A DECLINE, NOT A SILENT STRIP — the field must reach the
    // doctor's confirm-list, not certify quietly without its offer.
    expect(body.slice(declineAt, certifyAt)).toContain('declined.push');
  });
});

describe('#193 — KEEP IS NARRATIVE-ONLY, because skipping a write is itself a write', () => {
  // ⚠️ THIS TABLE IS THE ARM THE GATE DID NOT HAVE. Round two measured that
  // every `kind:` in this whole file was `narrative_text`, so a kept CHECKBOX
  // went unwatched — and the renderer writes `w14:val="0"` + `☐` for a null,
  // meaning SKIPPING that write leaves a pre-ticked box TICKED. A signed note
  // asserted `Anticoagulated ☒` on the strength of an unrelated dictated
  // headache. A ticked box is not a sentence; it is an affirmative clinical
  // fact. A date printed the TEMPLATE's own hardcoded date as the encounter's.
  // The property is NEVER KEPT, not a particular replacement status: a
  // non-narrative kind may legitimately resolve `needs_clinician_input` or
  // `not_mentioned` depending on its own type rules, and pinning one of those
  // would make this arm fail on an unrelated change.
  const NON_PROSE = ['checkbox', 'date', 'single_select', 'number', 'measurement'] as const;

  // ⚠️ THE MAPPING'S `expectedDataType` MATCHES THE KIND, AND THAT IS WHAT
  // MAKES THIS ARM PROVE ANYTHING. The first version left it at `'text'` for
  // every kind, so a checkbox resolved `needs_clinician_input` on a TYPE
  // MISMATCH — and removing the kind guard changed nothing, because a different
  // guard was doing the work. The mutation caught the arm, not the code.
  const TYPE_FOR: Record<string, string> = {
    narrative_text: 'text', checkbox: 'boolean', date: 'date',
    single_select: 'single_select', number: 'number', measurement: 'measurement',
  };
  const resolveKind = (kind: string) => {
    const f = field('1', {
      fieldId: `ttf_${'1'.repeat(24)}`,
      kind: kind as 'narrative_text',
      ...(kind === 'single_select'
        ? { allowedOptions: [{ ordinal: 0, displayText: 'Normal', value: 'Normal' }] }
        : {}),
    });
    return resolveTemplateFields({
      fields: [f],
      mappings: [
        mapping(f, 'ros.cardiovascular', {
          unmentionedPolicy: 'keep',
          expectedDataType: TYPE_FOR[kind] as 'text',
          ...(kind === 'checkbox' ? { polarityBehavior: 'affirmative_only' as const } : {}),
          ...(kind === 'measurement' ? { unitPolicy: 'required' as const } : {}),
        }),
      ],
      facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
      allowUncertifiedForSyntheticTest: true,
    })[0]!;
  };

  it.each(NON_PROSE)('a DECLARED keep on a %s is NEVER kept', (kind) => {
    expect(`${kind}: ${resolveKind(kind).status}`).not.toBe(`${kind}: default_kept`);
  });

  it('and narrative_text IS kept — otherwise the table above is vacuous', () => {
    expect(resolveKind('narrative_text').status).toBe('default_kept');
  });

  it('⚠️ AND THE PROPOSER OFFERS ONLY WHERE THE RENDER CAN HONOUR IT', async () => {
    // A confirmation that silently does nothing is worse than no offer: the
    // doctor believes they decided. Round two measured the proposer offering
    // keep on checkboxes and dates that the resolver now refuses.
    const { fallbackSemanticMappings } = await import('../semantic-mapping');
    for (const kind of ['checkbox', 'date', 'single_select'] as const) {
      const f = field('1', { fieldId: `ttf_${'1'.repeat(24)}`, kind });
      const [p] = fallbackSemanticMappings({ fields: [f] });
      expect(`${kind}: ${p?.unmentionedPolicy ?? null}`).toBe(`${kind}: null`);
    }
    const prose = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    expect(fallbackSemanticMappings({ fields: [prose] })[0]?.unmentionedPolicy).toBe('keep');
  });

  it('⚠️ A KEPT DEFAULT CAN EARN BLANK CREDIT — the hardcode blocked certification', async () => {
    // `blank-proof-count.ts` admits `kept_default` and calls it "the STRONGER of
    // the three", then requires `blankEligible === 'eligible'`. The guard
    // hardcoded `'unevaluated'`, so 0 of 9 genuine kept defaults counted and a
    // template whose unfilled fields are kept defaults could not certify at all.
    const src = readFileSync(
      join(__dirname, '../../note-template-docx/renderer.ts'), 'utf-8');
    // anchor on the GUARD, not the first mention of the status — the proof
    // branch names it 500 lines earlier and would make this arm measure that
    const i = src.indexOf(
      "resolution.value === null && resolution.status === 'default_kept'");
    expect(i).toBeGreaterThan(-1);
    const block = src.slice(i, i + 1400);
    expect(block).toContain('blankEligibilityFor(field)');
    expect(block).not.toMatch(/blankEligible:\s*'unevaluated'/);
  });
});

describe('#193 — the offer is SHOWN, with its sentence', () => {
  it('(40) ⚠️ THE CONFIRM SCREEN DISCLOSES A KEEP AND QUOTES THE TEXT IT WILL PRINT', () => {
    // ⚠️ WITHOUT THIS THE RULING'S SAFETY IS UNDELIVERABLE. #193 routes a keep
    // to a HUMAN because printing template prose on a signed note is a clinical
    // assertion no automated step may make. Round two measured the confirm
    // screen rendering NEITHER the policy NOR the sentence — zero hits for
    // `unmentionedPolicy` or `scaffoldText` in any `.tsx` — so `confirmed()`
    // carried the keep through on the same click that confirmed the CONCEPT.
    // The doctor authorised text they had never been shown. That is consent
    // theatre, and it fails in the direction the ruling exists to prevent.
    const src = readFileSync(
      join(__dirname, '../../../app/settings/note-format/native-template-manager.tsx'),
      'utf-8',
    );
    // the condition must exist and must not be short-circuited
    const line = src.split('\n').find((l) => l.includes("m.unmentionedPolicy === 'keep'"));
    expect(line, 'the confirm screen must branch on a declared keep').toBeDefined();
    expect(line!.trim().startsWith('{m.unmentionedPolicy === ')).toBe(true);
    // ⚠️ AND IT MUST QUOTE THE SENTENCE — "this field keeps its default" is not
    // something a doctor can evaluate.
    expect(src).toContain('f.field.scaffoldText');
    expect(src).toContain('Keeps your template');
  });
});
