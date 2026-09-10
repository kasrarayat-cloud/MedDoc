// ============================================================================
// RULING #194 — THE KEEP HALF IS DELETED. THE MACHINE NEVER PRINTS AN
// UNDICTATED DEFAULT.
// ----------------------------------------------------------------------------
// This gate replaces `gate-191-scaffolded-field-policy` and
// `gate-191-kept-default-survives-render`, both of which armed a feature that
// no longer exists. What survives is arm-worthy for the same reasons it always
// was; what was deleted is pinned as DELETED, because the cheapest way for this
// to come back is for somebody to reintroduce a `'keep'` string.
//
// ⚠️ WHY IT WAS DELETED — THE PREMISE, NOT THE MECHANISM. Six formulations of
// the mechanism were falsified in three adversarial rounds (a text heuristic;
// `w:showingPlcHdr`; the guard below the kind branches; the guard below the
// binding dispatch; "skipping a write is itself a write", a pre-ticked box
// staying TICKED; and `narrative_text`, which `inferTextKind` assigns by a
// LABEL REGEX). Then the premise itself: the keep branch fired when
// `conceptCandidates.length === 0` -- when NO fact carried the field's concept
// -- and concept equality is the only test performed anywhere, so "nothing
// dictated contradicted this" was always a claim about the EMPTY SET.
//
// MEASURED: a scaffold reading "no varicosities, no oedema and no ulceration"
// was KEPT on a visit dictated as a large weeping ulcer with gross bilateral
// oedema and prominent varicosities, because that fact carried
// `chief_complaint` rather than `exam.vascular`. Before the slice, that field
// rendered BLANK and the banner said "1 still blank" -- which was TRUE.
// ============================================================================

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
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  SemanticMappingSchema,
  templateTwinCounts,
  TEMPLATE_TWIN_RESOLVER_VERSION,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';

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


describe('#194 — there is no `keep`, anywhere', () => {
  it('(1) ⚠️ THE SCHEMA REFUSES `keep` — the cheapest way for this to return is a string', () => {
    const { unmentionedPolicy: _drop, ...rest } = mapping(
      field('1', { fieldId: `ttf_${'1'.repeat(24)}` }),
      'ros.cardiovascular',
    ) as SemanticMapping & { unmentionedPolicy?: unknown };
    const withKeep = { ...rest, unmentionedPolicy: 'keep' };
    const withOmit = { ...rest, unmentionedPolicy: 'omit' };
    expect(SemanticMappingSchema.safeParse(withKeep).success).toBe(false);
    expect(SemanticMappingSchema.safeParse(withOmit).success).toBe(true);
    expect(SemanticMappingSchema.safeParse(rest).success).toBe(true);
  });

  it('(2) ⚠️ `default_kept` IS RETIRED FROM THE STATUS UNION', () => {
    const base = {
      fieldId: `ttf_${'1'.repeat(24)}`,
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'fact_not_mentioned',
      clinicianReviewed: false,
    };
    expect(FieldResolutionSchema.safeParse({ ...base, status: 'default_kept' }).success)
      .toBe(false);
    expect(FieldResolutionSchema.safeParse({ ...base, status: 'not_mentioned' }).success)
      .toBe(true);
  });

  it('(3) ⚠️ NO PRODUCER EMITS IT, AND NO CONSUMER ADMITS IT', () => {
    const files = [
      ['resolver', '../resolver/index.ts'],
      ['renderer', '../../note-template-docx/renderer.ts'],
      ['roundtrip-verify', '../../note-template-docx/roundtrip-verify.ts'],
      ['blank-proof-count', '../blank-proof-count.ts'],
      ['proposer', '../semantic-mapping/index.ts'],
    ] as const;
    for (const [name, rel] of files) {
      const src = readFileSync(join(__dirname, rel), 'utf-8');
      // strip comments — the historical record of WHY names it deliberately
      const code = src
        .split('\n')
        .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
        .join('\n');
      expect(`${name}:default_kept`).toBe(`${name}:${code.includes("'default_kept'") ? 'PRESENT' : 'default_kept'}`);
      expect(`${name}:kept_default`).toBe(`${name}:${code.includes("'kept_default'") ? 'PRESENT' : 'kept_default'}`);
    }
  });

  it('(4) an unmentioned field with NO policy is BLANK, and the doctor is told', () => {
    const { resolution, resolutions } = scenario();
    expect(resolution.status).toBe('not_mentioned');
    expect(resolution.reasonCode).toBe('fact_not_mentioned');
    const c = templateTwinCounts(resolutions, [field('1', { fieldId: `ttf_${'1'.repeat(24)}` })]);
    expect(c.notMentioned).toBe(1);
  });
});

describe('#194 — `omit` survives, and is NOT counted as an undictated blank', () => {
  const defs = () => [field('1', { fieldId: `ttf_${'1'.repeat(24)}` })];

  it('(5) a RULED omit clears with its own reason token', () => {
    const { resolution } = scenario({ unmentionedPolicy: 'omit' });
    expect(resolution.status).toBe('not_mentioned');
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
    expect(resolution.value).toBeNull();
  });

  it('(6) ⚠️ AND IT IS COUNTED SEPARATELY — neither reported as undictated nor silently lost', () => {
    // Both take the bounded clear so the PAGE is identical; the difference is
    // what the doctor is told. A ruled-blank telehealth line must not appear in
    // "N still blank — nothing dictated for those yet" every visit, and must
    // not vanish either: a status that fell into no bucket once collapsed a
    // form's blank count 11 -> 0 with the document byte-identical.
    const omitted = scenario({ unmentionedPolicy: 'omit' }).resolutions;
    const plain = scenario().resolutions;
    const co = templateTwinCounts(omitted, defs());
    const cp = templateTwinCounts(plain, defs());
    expect(co.notMentioned).toBe(0);
    expect(co.omitted).toBe(1);
    expect(cp.notMentioned).toBe(1);
    expect(cp.omitted).toBe(0);
  });

  it('(7) ⚠️ THE BUCKETS RECONCILE — nothing lands nowhere', () => {
    for (const rs of [scenario().resolutions, scenario({ unmentionedPolicy: 'omit' }).resolutions]) {
      const c = templateTwinCounts(rs, defs());
      expect(c.filled + c.needsReview + c.notMentioned + (c.omitted ?? 0)).toBe(rs.length);
    }
  });

  it('(8) a DEFERRAL keeps its named reason even under omit', () => {
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

  it('(9) a clearing nothing evaluated is not deliberate', () => {
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const [r] = resolveTemplateFields({
      fields: [scaffold],
      mappings: [mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'omit' })],
      facts: [], allowUncertifiedForSyntheticTest: true,
    });
    expect(r!.reasonCode).toBe('fact_not_mentioned');
  });
});

describe('#194 — the column, the hash, and the projections still hold', () => {
  it('(10) every mapping projection carries every scalar column — derived from the SCHEMA', () => {
    const schema = readFileSync(
      join(__dirname, '../../../../../../packages/db/prisma/schema.prisma'), 'utf-8');
    const model = schema.slice(schema.indexOf('model TemplateTwinSemanticMapping'));
    const body = model.slice(0, model.indexOf('\n}'));
    const scalars = [...body.matchAll(/^\s{2}(\w+)\s+(String|Boolean|Json|DateTime|TemplateTwinDetectionStatus)\b/gm)]
      .map((m) => m[1]!)
      .filter((n) => !['id','fieldDefinitionId','approvedById','approvedAt','createdAt','updatedAt','proposedByModel'].includes(n));
    expect(scalars).toContain('unmentionedPolicy');
    expect(scalars).toContain('conceptScope');
    expect(scalars.length).toBeGreaterThan(8);

    // ⚠️ #217 — THIS LOOP USED TO CHECK ONE COLUMN AND ITS TITLE CLAIMED ALL OF
    // THEM. It derived every scalar from the schema and then asserted only
    // `unmentionedPolicy`, so `conceptScope` could be added to the model, the
    // writer and the read-back and still be missing from all five projections —
    // which is precisely how that field ended up with four readers and no
    // writer. Deriving the inputs closes the CLASS; asserting one name closes an
    // instance and reads identically.
    //
    // `practiceId` is excluded because it is the tenancy column and is never
    // projected into a SemanticMapping.
    const projected = scalars.filter((n) => n !== 'practiceId');
    for (const rel of ['fill-engine.ts','certification-lifecycle.ts','workspace-read.ts','synthetic-test.ts']) {
      const src = readFileSync(join(__dirname, '..', rel), 'utf-8');
      const selects = src.split('blankPolicy: true,').length - 1;
      expect(selects, `${rel} has no mapping projection at all`).toBeGreaterThan(0);
      for (const col of projected) {
        expect(
          src.split(`${col}: true,`).length - 1,
          `${rel} projects ${selects} mapping(s) but does not select "${col}" in all of them`,
        ).toBe(selects);
      }
    }
  });

  it('(11) ⚠️ ONLY AN UNSET POLICY IS ELIDED FROM THE ATTESTATION — `omit` MOVES THE SHA', () => {
    // A doctor's declared `omit` changes what the document says, so removing it
    // from a certified mapping must move the attestation. NULL is elided so no
    // pre-existing certification moved when the column arrived.
    const scaffold = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    const absent = mapping(scaffold, 'ros.cardiovascular');
    delete (absent as { unmentionedPolicy?: string }).unmentionedPolicy;
    const omit = mapping(scaffold, 'ros.cardiovascular', { unmentionedPolicy: 'omit' });
    expect(templateTwinMappingsSha256([omit])).not.toBe(templateTwinMappingsSha256([absent]));
  });

  it('(12) the derived metadata stays OUT of structural identity — certified twins depend on it', async () => {
    // `scaffolded`/`scaffoldText` survive the deletion because REVIEW-DEFAULTS
    // needs exactly them: which controls carry a default, and what it says.
    // They inform a human's choice and never a render.
    const { fieldForStructuralIdentity } = await import('../../note-template-docx/compiler');
    const f = field('1', { fieldId: `ttf_${'1'.repeat(24)}` });
    (f as { scaffoldText?: string }).scaffoldText = 'The patient denies chest pain.';
    const stripped = fieldForStructuralIdentity(f);
    expect((stripped as { scaffolded?: boolean }).scaffolded).toBeUndefined();
    expect((stripped as { scaffoldText?: string }).scaffoldText).toBeUndefined();
    expect(Object.keys(stripped).sort()).toEqual(
      Object.keys(f).filter((k) => k !== 'scaffolded' && k !== 'scaffoldText').sort(),
    );
  });

  it('(13) the resolver VERSION moved — its output changed for identical input', () => {
    // ⚠️ #313 moved it again (2.0.0 -> 3.0.0): the fill's resolutions changed
    // for identical input once a bullet group distributes one item per bullet.
    // The pin stays a pin — a version nobody moves is how a stale manifest is
    // accepted as current.
    expect(TEMPLATE_TWIN_RESOLVER_VERSION).toBe('template-field-resolver/3.0.0');
  });
});

// ============================================================================
// ⚠️ ARMS THE DELETION TOOK WITH IT. They were written for the keep half and
// they guard code that SURVIVED — the deletion removed the feature and its
// watchers together, and each of the three mutations below redded 0 of 5934
// until these were restored. A deletion is as capable of partial application as
// an edit; this is that rule one level up, applied to the ARMS rather than the
// code.
// ============================================================================

describe('#194 — guards the deletion nearly took', () => {
  it('(14) ⚠️ A POPULATED FIELD CITING FOREIGN EVIDENCE IS STILL BLOCKED', () => {
    // The `default_kept` exemption to `SOURCE_FACT_CONCEPT_MISMATCH` went with
    // the status, correctly. Its arm went too — and what that arm actually
    // asserted was the SURVIVING half: that every OTHER status still refuses a
    // fact about a different concept. Disabling the check now reds nothing.
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
      fields: [scaffold], mappings: [mapped], facts: [foreign],
      resolutions: [supported], allowUncertifiedForSyntheticTest: true,
    });
    expect(
      result.issues.some(
        (i) => i.code === 'SOURCE_FACT_CONCEPT_MISMATCH' && i.severity === 'blocking',
      ),
    ).toBe(true);
  });

  it('(15) ⚠️ AN IR COMPILED BEFORE `scaffolded` EXISTED STILL RENDERS', async () => {
    // `assertSourceMatchesIr` recompiles the source on EVERY fill and compares
    // it against the STORED IR. Stripping the derived fields from
    // `structureSha256` was correct and INSUFFICIENT — that function also does
    // an INDEPENDENT raw comparison over the field arrays. Restoring the raw
    // form throws SOURCE_IR_MISMATCH, which `native-export` swallows into the
    // generic styled export: the doctor silently loses their own form. Measured
    // once at 10 of 10 twins.
    //
    // ⚠️ AND THIS WATCHES THE OUTCOME, NOT THE STRIP. Arm (12) tests
    // `fieldForStructuralIdentity` in isolation — which is precisely the
    // "watched the wrong set" mistake the compiler's own headstone records.
    const { buildSyntheticDocx } = await import(
      '../../note-template-docx/__tests__/synthetic-docx');
    const { compileTemplateDocx } = await import('../../note-template-docx/compiler');
    const { renderTemplateDocx } = await import('../../note-template-docx/renderer');
    const source = await buildSyntheticDocx();
    const head = compileTemplateDocx(source);
    const stored = JSON.parse(JSON.stringify(head)) as typeof head;
    (stored as { fields: unknown[] }).fields = head.fields.map((f) => {
      const { scaffolded: _a, scaffoldText: _b, ...rest } = f;
      return rest;
    });
    // non-vacuity: HEAD really does emit them, and the stored shape really lacks them
    expect(head.fields.some((f) => f.scaffolded !== undefined)).toBe(true);
    await expect(
      renderTemplateDocx({
        source, ir: stored,
        resolutions: stored.fields.map((f) =>
          FieldResolutionSchema.parse({
            fieldId: f.fieldId, status: 'not_mentioned', value: null,
            sourceFactIds: [], evidenceAnchorIds: [], selectedOptionOrdinal: null,
            reasonCode: 'fact_not_mentioned', clinicianReviewed: false,
          }),
        ),
        validation: {
          valid: true, issues: [], checkedAt: '2026-01-01T00:00:00.000Z',
          validatorVersion: 'template-field-validator/1.0.0',
        },
      }),
    ).resolves.toBeDefined();
  });

  it('(16) ⚠️ THE SURVIVING METADATA IS EMITTED, AND ITS DISCRIMINATOR IS THE DECLARED SIGNAL', async () => {
    // `scaffolded`/`scaffoldText` were preserved ON PURPOSE for REVIEW-DEFAULTS
    // and were left completely unarmed: `scaffolded: false` and never emitting
    // `scaffoldText` both redded 0 of 5934.
    const { buildSyntheticDocx } = await import(
      '../../note-template-docx/__tests__/synthetic-docx');
    const { compileTemplateDocx } = await import('../../note-template-docx/compiler');
    const SENT = 'The patient denies chest pain.';
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:sdt><w:sdtPr><w:alias w:val="ROS"/><w:id w:val="901"/><w:text/></w:sdtPr>
<w:sdtContent><w:r><w:t>${SENT}</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:alias w:val="Pick"/><w:id w:val="902"/><w:showingPlcHdr/>
<w:dropDownList><w:listItem w:displayText="Left" w:value="L"/></w:dropDownList></w:sdtPr>
<w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
</w:body></w:document>`,
      }),
    );
    const ros = ir.fields.find((f) => f.originalLabel === 'ROS');
    const pick = ir.fields.find((f) => f.originalLabel === 'Pick');
    expect(ros?.scaffolded).toBe(true);
    expect(ros?.scaffoldText).toBe(SENT);
    // ⚠️ THE DISCRIMINATOR IS `w:showingPlcHdr`, WHICH THE DOCUMENT DECLARES —
    // never the placeholder TEXT. Canon 83: a rule matching "Choose an item."
    // blocked 28 of 28 dropdowns of the real customer form, and its English-only
    // repair blocked all 28 again in fr/de/es. This control carries BOTH the
    // flag and that exact string, so a text-matching predicate would score
    // identically and only the declared signal separates them.
    expect(pick?.scaffolded).toBe(false);
    expect(pick?.scaffoldText).toBeUndefined();

    // ⚠️ AND A CASE ONLY THE DECLARED SIGNAL CAN GET RIGHT. The control above
    // carries BOTH the flag and the literal "Choose an item.", so a text-matching
    // predicate scores identically on it — a control aimed where the answer is
    // predetermined proves nothing about the instrument. This one declares the
    // flag with LOCALISED prompt text, which is exactly canon 83's reference
    // defect: the English-only repair blocked all 28 real dropdowns again in
    // fr/de/es. A text matcher calls it a scaffold; the declared signal does not.
    const fr = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:sdt><w:sdtPr><w:alias w:val="Cote"/><w:id w:val="903"/><w:showingPlcHdr/>
<w:dropDownList><w:listItem w:displayText="Gauche" w:value="G"/></w:dropDownList></w:sdtPr>
<w:sdtContent><w:r><w:t>Choisissez un élément.</w:t></w:r></w:sdtContent></w:sdt></w:p>
</w:body></w:document>`,
      }),
    );
    const localised = fr.fields.find((f) => f.originalLabel === 'Cote');
    expect(localised, 'the localised control must compile').toBeDefined();
    expect(localised!.scaffolded).toBe(false);
  });
});
