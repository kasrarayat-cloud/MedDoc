// ============================================================================
// GATE — REVIEW-DEFAULTS item 2: `omit` gets a door, and the door does not lie.
// ----------------------------------------------------------------------------
// Ruling #194 left exactly one surviving policy — `'omit'` — and no way for a
// doctor to choose it. Measured before this change: `grep -c unmentionedPolicy`
// over every `.tsx` is ZERO, against a 12-file `.ts` positive control. The
// server has accepted it the whole time (`certification-lifecycle.ts:415` parses
// the doctor's payload with `SemanticMappingSchema`, which permits `'omit'`;
// `:521` persists it). Only the interface was missing.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · any ONE of the five requires-input clauses is
//     dropped from the shared predicate            -> the five-clause block
//   · the resolver grows a SECOND copy of that
//     predicate instead of importing it            -> the one-copy block
//   · the surface OFFERS omit where the resolver
//     would not honour it                          -> the BICONDITIONAL matrix
//   · a seventh guard is added to
//     `omitBranchUnreachable` without declaring
//     the resolver tokens it stands for            -> the completeness arm
//   · a guard names a token the resolver does
//     not actually return                          -> the token-family check
//   · `omit` starts changing the PAGE and not just
//     the prompt                                   -> the page-is-identical block
//   · an omitted field falls into NO bucket, or
//     into BOTH                                    -> the accounting block
//
// ⚠️ AND THE ARM THAT USED TO STAND WHERE THE MATRIX NOW STANDS WAS GREEN, AND
// PINNED THE BUG. It asserted `canOmitWhenUnmentioned` was "the exact negation
// of `requiresClinicianInput`" — over a table that varied only the five
// requires-input inputs. That was TRUE of the code and FALSE of the product:
// `requiresClinicianInput` is evaluated inside `missingResolution`, five guards
// further down than the offer needed to look, so the control was offered on
// `manual` fields, `verified_note_selection` fields, fields with no concept,
// unsupported fields, and fields already carrying an approved practice default.
// A doctor ticking it there pays a forced re-certification and is asked about
// the field on every visit forever.
//
// The arm was not merely blind to that — it would have RED-FLAGGED the fix. A
// green control over a table that never varies the deciding input is the
// vacuity failure wearing a control's clothes, and the replacement compares the
// predicate to the RESOLVER'S OWN BEHAVIOUR instead of to another predicate.
//
// ⚠️ AND THE FIVE-CLAUSE BLOCK EXISTS BECAUSE THE SUITE DID NOT COVER IT.
// Measured while extracting the predicate: dropping
// `mapping.blankPolicy === 'requires_input'` from it and running the FULL unit
// suite gave **434 files, 6071 tests, 0 failures** — with the mutation asserted
// present in the file at the end of the run. A clause that decides whether a
// field is put to the clinician or left silently blank was load-bearing and
// unguarded. That is not a gap this feature introduced; it is one the extraction
// exposed, and it is closed here because the extraction is what makes a single
// dropped clause a plausible edit.
//
// ⚠️ WHAT THIS FILE DOES *NOT* MEASURE, said plainly:
//   · THE RENDERED BYTES. The page-is-identical block asserts the RESOLUTION is
//     identical (status and value) and that only the reason token differs. That
//     the DOCX bytes are then identical is `gate-157b-denial-contract`'s
//     property, proved there, and is not re-proved here.
//   · WHETHER OMIT FIRES ON THE NEXT VISIT. The resolver also requires
//     `conceptUnmatched && reason === undefined && facts.length > 0` — all three
//     are properties of a PARTICULAR ENCOUNTER. This file proves the choice can
//     matter, never that it will.
//   · THE CLIENT CONTROL'S DOM. The panel arms live beside the panel, in
//     `app/settings/note-format/__tests__`. What is proved HERE is the predicate
//     the panel is required to call.
//   · ANY AUDIT ROW. Mapping edits ARE audited (93 production
//     `TEMPLATE_TWIN_MAPPING_UPDATED` rows — my first note here claimed the
//     opposite and was wrong). The row does not record WHICH policy was chosen.
//     This change adds no new audit action.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

import { resolveTemplateFields } from '../resolver';
import { templateTwinCounts } from '../ir';
import { scaffoldDefaultOfferable } from '../clinician-override';
import {
  requiresClinicianInput,
  canOmitWhenUnmentioned,
  omitBranchUnreachable,
  OMIT_GUARD_TOKEN_PREFIXES,
  OMIT_CONTROL_LABEL,
  OMIT_CONTROL_HINT,
  OMIT_INERT_LABEL,
} from '../unmentioned-policy';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';
import type { OmitMappingView } from '../unmentioned-policy';
import {
  OMIT_MAPPING_COLUMN,
  OMIT_MAPPING_SELECT,
  toOmitMappingView,
} from '../unmentioned-policy';

const SHA = 'a'.repeat(64);

function field(idSeed: string, overrides: Partial<TemplateField> = {}): TemplateField {
  return {
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind: 'narrative_text',
    scaffolded: true,
    scaffoldText: 'The patient consents to a telehealth consultation.',
    originalLabel: 'Telehealth consent',
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

/**
 * One field the encounter never speaks to, on a visit that said something REAL
 * about a DIFFERENT concept — which is the only shape where `conceptUnmatched`,
 * `reason === undefined` and `facts.length > 0` all hold.
 */
function resolveOne(
  fieldOverrides: Partial<TemplateField> = {},
  mappingOverrides: Partial<SemanticMapping> = {},
) {
  const f = field('1', fieldOverrides);
  const m = mapping(f, 'ros.cardiovascular', mappingOverrides);
  const resolutions = resolveTemplateFields({
    fields: [f],
    mappings: [m],
    facts: [factFor('2', 'chief_complaint', 'Patient here for a rash.')],
    allowUncertifiedForSyntheticTest: true,
  });
  return { field: f, mapping: m, resolution: resolutions[0]!, resolutions };
}

// ============================================================================
// THE FIVE CLAUSES ARE EACH LOAD-BEARING — one arm per clause, so dropping ANY
// ONE of them reds EXACTLY ONE arm and names it.
// ============================================================================
describe('item 2 — every requires-input clause is guarded', () => {
  it('CONTROL — with no requires-input signal at all, the field is left blank', () => {
    const { resolution } = resolveOne();
    expect(resolution.status).toBe('not_mentioned');
    expect(requiresClinicianInput(field('1'), mapping(field('1'), 'x'))).toBe(false);
  });

  const CLAUSES: ReadonlyArray<{
    name: string;
    fieldOver: Partial<TemplateField>;
    mappingOver: Partial<SemanticMapping>;
  }> = [
    { name: 'field.required', fieldOver: { required: true }, mappingOver: {} },
    { name: 'mapping.required', fieldOver: {}, mappingOver: { required: true } },
    {
      name: "field.unknownPolicy === 'requires_input'",
      fieldOver: { unknownPolicy: 'requires_input' },
      mappingOver: {},
    },
    {
      name: "mapping.unknownPolicy === 'requires_input'",
      fieldOver: {},
      mappingOver: { unknownPolicy: 'requires_input' },
    },
    {
      // ⚠️ THIS ONE WAS UNGUARDED BY ALL 6071 TESTS. See the header.
      name: "mapping.blankPolicy === 'requires_input'",
      fieldOver: {},
      mappingOver: { blankPolicy: 'requires_input' },
    },
  ];

  for (const clause of CLAUSES) {
    it(`${clause.name} alone puts the field to the clinician`, () => {
      const f = field('1', clause.fieldOver);
      const m = mapping(f, 'ros.cardiovascular', clause.mappingOver);

      // The predicate says so...
      expect(requiresClinicianInput(f, m)).toBe(true);

      // ...and the REAL resolver acts on it. Asserting only the predicate would
      // pass against a predicate nothing calls.
      const { resolution } = resolveOne(clause.fieldOver, clause.mappingOver);
      expect(resolution.status).toBe('needs_clinician_input');
      expect(resolution.status).not.toBe('not_mentioned');
    });

    it(`${clause.name} alone WITHDRAWS the omit offer`, () => {
      const f = field('1', clause.fieldOver);
      const m = mapping(f, 'ros.cardiovascular', clause.mappingOver);
      expect(canOmitWhenUnmentioned(f, m)).toBe(false);

      // And the resolver agrees: an `omit` set on such a field is NOT honoured,
      // so offering the control there would have been a lie.
      const { resolution } = resolveOne(clause.fieldOver, {
        ...clause.mappingOver,
        unmentionedPolicy: 'omit',
      });
      expect(resolution.reasonCode).not.toBe('omitted_unsupported_default');
    });
  }
});

// ============================================================================
// THE OFFER EQUALS THE HONOURING — item 1's rule, applied to item 2.
// "A surface must never offer an act its writer would refuse."
// ============================================================================
describe('item 2 — the offer and the honouring are one predicate', () => {
  it('⚠️ NON-VACUITY CONTROL — an OFFERABLE field DOES get the omit reason', () => {
    const f = field('1');
    const m = mapping(f, 'ros.cardiovascular');
    expect(canOmitWhenUnmentioned(f, m)).toBe(true);

    const { resolution } = resolveOne({}, { unmentionedPolicy: 'omit' });
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
  });

  // ==========================================================================
  // ⚠️ THE BICONDITIONAL. This is the instrument that makes the mirror in
  // `omitBranchUnreachable` safe, and it is the arm that would have caught the
  // shipped defect.
  //
  // The arm that used to stand here asserted `canOmitWhenUnmentioned` was the
  // exact negation of `requiresClinicianInput` — and it PASSED, because its
  // matrix varied only the five requires-input inputs. It was not merely
  // blind to the bug; it PINNED it, so the correct fix would have redded it.
  // A green arm over a table that never varies the deciding input is the
  // vacuity failure wearing a control's clothes.
  //
  // So this arm does not compare the predicate to another predicate. It
  // compares it to THE RESOLVER'S OWN BEHAVIOUR, over the cross-product of
  // every input that can reach the branch — and requires BOTH directions to
  // be witnessed, so neither half can pass by being empty.
  // ==========================================================================
  it('⚠️ OFFERED  ⟺  HONOURED — the predicate matches the REAL resolver, both ways', () => {
    const bools = [false, true];
    const policies = ['blank', 'not_documented', 'requires_input'] as const;
    const sourceTypes = ['extraction', 'manual', 'verified_note_selection'] as const;
    const detections = ['certified', 'unsupported'] as const;
    // ⚠️ `null`, NOT `''`. `ir.ts:372` is `z.string().min(1).max(160).nullable()`,
    // so an empty string is REFUSED by the schema and never reaches the resolver.
    // `null` is the value the confirm surface renders as '· no concept yet'.
    const concepts = ['ros.cardiovascular', null] as const;
    const defaults = [null, 'The patient consents.'] as const;
    // ⚠️ THE DIMENSION THIS MATRIX SHIPPED WITHOUT, AND ITS ABSENCE HID A REAL
    // GUARD. `isMappingTypeCompatible` is the resolver's FIRST exit; holding
    // `expectedDataType` constant at the compatible value made every row of the
    // cross-product type-compatible, so the biconditional could not witness the
    // one case where the offer outruns the honouring. The base field kind is
    // `narrative_text`, whose compatible type is `text`; `number` is the
    // incompatible partner. Measured before the fix: offered=true while the
    // resolver returned `semantic_mapping_type_mismatch`.
    const dataTypes = ['text', 'number'] as const;
    // ⚠️ THE SEVENTH GUARD'S INPUTS. Added after a peer session found that the
    // fixed-grid `table_cell` call site was unmirrored — the third time this
    // matrix has been widened because it held constant the very input a guard
    // reads. The arm below now DERIVES the required dimensions from the mirror's
    // own source, so a fourth time reds instead of passing.
    const bindings = ['content_control', 'table_cell'] as const;
    // ⚠️ CAUGHT BY THE DERIVED-DIMENSION ARM, ON ITS FIRST RUN. The mirror
    // reads `mapping.status` and this matrix had never varied it — a FOURTH
    // instance of the same blindness, found by the arm written to close the
    // class rather than by another pass.
    const statuses = ['certified', 'unsupported'] as const;

    // The ONLY guards permitted to withhold an offer the resolver would honour.
    // Adding to this set is a product decision, not a test fix.
    const CONSERVATIVE_GUARDS = new Set(['fixed_grid_cell_deferred']);
    let offeredAndHonoured = 0;
    let refusedAndNotHonoured = 0;
    let conservativeWithholds = 0;
    const disagreements: string[] = [];
    const tokenMismatches: string[] = [];

    for (const fReq of bools)
      for (const mReq of bools)
        for (const fUnknown of policies)
          for (const mBlank of policies)
            for (const sourceType of sourceTypes)
              for (const detectionStatus of detections)
                for (const clinicalConcept of concepts)
                  for (const practiceDefault of defaults)
                    for (const expectedDataType of dataTypes)
                    for (const bindingType of bindings)
                    for (const status of statuses) {
                    const fieldOverrides = {
                      required: fReq,
                      unknownPolicy: fUnknown,
                      detectionStatus,
                      rendererBinding: { ...field('1').rendererBinding, bindingType },
                      // a fixed grid cell is table_cell AND not a prototype
                      rowPrototype: false,
                    };
                    const mappingOverrides = {
                      required: mReq,
                      blankPolicy: mBlank,
                      sourceType,
                      clinicalConcept,
                      practiceDefault,
                      expectedDataType,
                      status,
                      unmentionedPolicy: 'omit' as const,
                    };

                    const f = field('1', fieldOverrides);
                    const m = mapping(f, clinicalConcept ?? 'unused', mappingOverrides);
                    const offered = canOmitWhenUnmentioned(f, m);

                    // Drive the ACTUAL resolver on the one encounter shape where
                    // `conceptUnmatched && reason === undefined && facts.length > 0`
                    // all hold, with the policy set to `omit`.
                    const { resolution } = resolveOne(fieldOverrides, mappingOverrides);
                    const honoured = resolution.reasonCode === 'omitted_unsupported_default';

                    const shape =
                      `fReq=${fReq} mReq=${mReq} fUnknown=${fUnknown} mBlank=${mBlank} ` +
                      `src=${sourceType} det=${detectionStatus} concept=${clinicalConcept ?? 'NONE'} ` +
                      `default=${practiceDefault === null ? 'null' : 'set'} type=${expectedDataType} bind=${bindingType} status=${status}`;

                    // ⚠️ THE TWO DIRECTIONS ARE NOT SYMMETRIC, AND CONFLATING
                    // THEM WOULD FORCE THE WRONG FIX.
                    //
                    // `offered && !honoured` is THE LIE — the control promises
                    // something the resolver will not do. Never acceptable.
                    //
                    // `!offered && honoured` is CONSERVATIVE — withheld where it
                    // would have worked. That is a real cost, taken deliberately
                    // in exactly one place: a fixed-grid cell on a visit where
                    // NOTHING in the grid was dictated does reach the omit
                    // branch, but any visit dictating one measurement sends all
                    // 52 cells (one shared concept) down a route that cannot
                    // honour it. Better no control than one false on the
                    // ordinary visit. Every such case must be attributable to a
                    // NAMED guard, or it is an accident wearing a policy.
                    if (offered && !honoured) {
                      disagreements.push(
                        `${shape} -> OFFERED BUT NOT HONOURED ` +
                          `(resolver said ${resolution.reasonCode})`,
                      );
                    } else if (!offered && honoured) {
                      const guard = omitBranchUnreachable(f, m);
                      if (guard === null || !CONSERVATIVE_GUARDS.has(guard)) {
                        disagreements.push(
                          `${shape} -> withheld but HONOURABLE, and guard ` +
                            `'${guard}' is not a declared conservative narrowing`,
                        );
                      } else {
                        conservativeWithholds += 1;
                      }
                    }
                    if (offered && honoured) offeredAndHonoured += 1;
                    if (!offered && !honoured) refusedAndNotHonoured += 1;

                    // ⚠️ AND THE STATED REASON MUST BE THE RESOLVER'S OWN. A
                    // mirror that refuses for the RIGHT field on the WRONG
                    // grounds is one refactor away from refusing the wrong
                    // field — so the token is compared, not just the boolean.
                    const stated = omitBranchUnreachable(f, m);
                    if (stated !== null && !honoured) {
                      const prefixes = OMIT_GUARD_TOKEN_PREFIXES[stated];
                      // A guard the module names but never declares tokens for
                      // is itself the defect — fail loudly rather than skip.
                      if (!prefixes) {
                        tokenMismatches.push(`${shape} -> guard '${stated}' declares NO tokens`);
                      } else if (!prefixes.some((prefix) => resolution.reasonCode.startsWith(prefix))) {
                        tokenMismatches.push(
                          `${shape} -> guard '${stated}' declares [${prefixes.join(', ')}], ` +
                            `resolver returned '${resolution.reasonCode}'`,
                        );
                      }
                    }
                  }

    expect(disagreements).toEqual([]);
    expect(tokenMismatches).toEqual([]);

    // ⚠️ NON-VACUITY, BOTH DIRECTIONS. A biconditional over a table that is
    // all-refused passes trivially and proves nothing.
    expect(offeredAndHonoured).toBeGreaterThan(0);
    expect(refusedAndNotHonoured).toBeGreaterThan(0);
    // ⚠️ AND THE CONSERVATIVE SET IS NOT A LOOPHOLE. If it stops witnessing
    // anything, the exemption is dead weight and should be deleted rather than
    // left standing as a permission nobody uses.
    expect(
      conservativeWithholds,
      'no conservative withhold witnessed — CONSERVATIVE_GUARDS is dead weight',
    ).toBeGreaterThan(0);
  });

  // ==========================================================================
  // The named short-circuits get one arm each, so a dropped clause reds a test
  // that says WHICH clause — the matrix above says only "they disagree".
  // ==========================================================================
  it.each([
    ['a MANUAL source', {}, { sourceType: 'manual' as const }, 'manual_source_not_filled'],
    [
      'a VERIFIED NOTE SELECTION',
      {},
      { sourceType: 'verified_note_selection' as const },
      'awaiting_note_selection',
    ],
    ['an UNSUPPORTED field', { detectionStatus: 'unsupported' as const }, {}, 'field_or_mapping_unsupported'],
    ['an UNSUPPORTED mapping', {}, { status: 'unsupported' as const }, 'field_or_mapping_unsupported'],
    ['NO clinical concept', {}, { clinicalConcept: null }, 'clinical_concept_unmapped'],
    [
      'an approved PRACTICE DEFAULT',
      {},
      { practiceDefault: 'The patient consents.' },
      'approved_practice_default',
    ],
  ])('⚠️ %s WITHDRAWS the offer, and names the resolver\'s own reason', (_name, fo, mo, token) => {
    const f = field('1', fo as Partial<TemplateField>);
    const m = mapping(f, 'ros.cardiovascular', mo as Partial<SemanticMapping>);

    expect(canOmitWhenUnmentioned(f, m)).toBe(false);
    expect(omitBranchUnreachable(f, m)).toBe(token);
    expect(OMIT_GUARD_TOKEN_PREFIXES[token]).toBeDefined();

    // …and the resolver genuinely does NOT honour an `omit` set on it.
    const { resolution } = resolveOne(fo as Partial<TemplateField>, {
      ...(mo as Partial<SemanticMapping>),
      unmentionedPolicy: 'omit',
    });
    expect(resolution.reasonCode).not.toBe('omitted_unsupported_default');
  });

  it('⚠️ THE MATRIX VARIES EVERY INPUT THE MIRROR READS — the class, not the instance', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE SAME FAILURE HAPPENED THREE TIMES.
    // The biconditional is only as good as its cross-product, and three separate
    // guards were invisible to it because it held their input constant:
    //   · `requiresClinicianInput` — the original arm varied only its five inputs
    //   · `isMappingTypeCompatible` — `expectedDataType` was constant (I found it)
    //   · the fixed-grid `table_cell` route — `bindingType` was constant (a peer found it)
    //
    // Widening the matrix a fourth time by hand would fix the instance and leave
    // the class open. So the REQUIRED DIMENSIONS ARE DERIVED FROM THE MIRROR'S
    // OWN SOURCE: every `field.X` / `mapping.X` the guard ladder reads must
    // appear as a varied dimension in this file. A guard added without its
    // dimension reds HERE, naming the property, instead of passing silently.
    const src = readFileSync(join(__dirname, '..', 'unmentioned-policy.ts'), 'utf-8');
    const body = src.slice(
      src.indexOf('export function omitBranchUnreachable'),
      src.indexOf('export const OMIT_GUARD_TOKEN_PREFIXES'),
    );
    // strip comments — the prose names properties it does not read
    const code = body
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
      .join('\n');
    const reads = new Set(
      [...code.matchAll(/\b(?:field|mapping)\.([A-Za-z][A-Za-z0-9]*)/g)].map((m) => m[1]!),
    );
    // `requiresClinicianInput` is called from the ladder, so its reads count too.
    const helper = src.slice(
      src.indexOf('export function requiresClinicianInput'),
      src.indexOf('export const RESOLVER_SHORT_CIRCUIT_SOURCE_TYPES') > 0
        ? src.indexOf('export const RESOLVER_SHORT_CIRCUIT_SOURCE_TYPES')
        : src.indexOf('export function omitBranchUnreachable'),
    );
    for (const m of helper.matchAll(/\b(?:field|mapping)\.([A-Za-z][A-Za-z0-9]*)/g)) reads.add(m[1]!);

    // NON-VACUITY: an empty or tiny set would make the loop below prove nothing.
    expect(reads.size, `parsed only ${reads.size} reads from the mirror`).toBeGreaterThanOrEqual(8);

    // The matrix's own source is the authority on what it varies.
    const thisFile = readFileSync(__filename, 'utf-8');
    const matrix = thisFile.slice(thisFile.indexOf('OFFERED  ⟺  HONOURED'));
    const varied = matrix.slice(0, matrix.indexOf('expect(disagreements)'));
    const missing = [...reads].filter((r) => !varied.includes(r));
    expect(
      missing,
      `the mirror reads [${missing.join(', ')}] and the biconditional never varies ` +
        `${missing.length === 1 ? 'it' : 'them'} — so a guard keyed on ` +
        `${missing.length === 1 ? 'that input' : 'those inputs'} is invisible to this matrix, ` +
        `which is exactly how the last three were missed.`,
    ).toEqual([]);
  });

  it('⚠️ EVERY guard the module can return DECLARES its tokens — no silent skips', () => {
    // Read the guard names out of the SOURCE, so a seventh guard added without
    // a token declaration reds here instead of being skipped by the matrix.
    const src = readFileSync(join(__dirname, '..', 'unmentioned-policy.ts'), 'utf-8');
    const body = src.slice(
      src.indexOf('export function omitBranchUnreachable'),
      src.indexOf('export const OMIT_GUARD_TOKEN_PREFIXES'),
    );
    const returned = [...body.matchAll(/return '([a-z_]+)'/g)].map((match) => match[1]!);

    expect(returned.length).toBeGreaterThanOrEqual(6);
    for (const guard of returned) {
      expect(OMIT_GUARD_TOKEN_PREFIXES[guard], `guard '${guard}' declares no tokens`).toBeDefined();
    }
    // …and nothing is declared that the function cannot return.
    for (const declared of Object.keys(OMIT_GUARD_TOKEN_PREFIXES)) {
      expect(returned, `'${declared}' is declared but unreachable`).toContain(declared);
    }
  });

  it('⚠️ THERE IS EXACTLY ONE COPY — the resolver IMPORTS the predicate', () => {
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src).toContain("from '../unmentioned-policy'");
    expect(src).toContain('requiresClinicianInput(field, mapping)');
    // The inline chain that used to live here must not come back. Matching the
    // SPELLING is deliberate: a second copy is only dangerous if it is a copy.
    expect(src).not.toMatch(/field\.required\s*\|\|\s*\n?\s*mapping\.required/);
  });
});

// ============================================================================
// THE PAGE IS IDENTICAL — which is the claim the doctor-facing copy makes, so
// it is the claim that has to be pinned.
// ============================================================================
describe('item 2 — omit changes the PROMPT, never the PAGE', () => {
  it('⚠️ status and value are IDENTICAL to a null policy — only the reason moves', () => {
    const nullPolicy = resolveOne().resolution;
    const omitted = resolveOne({}, { unmentionedPolicy: 'omit' }).resolution;

    expect(omitted.status).toBe(nullPolicy.status);
    expect(omitted.value).toBe(nullPolicy.value);
    expect(omitted.value).toBeNull();
    expect(omitted.sourceFactIds).toEqual(nullPolicy.sourceFactIds);

    // The ONE difference, and it is a label rather than content.
    expect(nullPolicy.reasonCode).not.toBe('omitted_unsupported_default');
    expect(omitted.reasonCode).toBe('omitted_unsupported_default');
  });

  it('⚠️ THE COPY SAYS SO — it governs the prompt and disclaims the document', () => {
    // The board filing names this control "omit this line when not dictated",
    // which would tell a doctor the line is REMOVED. It is not. If somebody
    // re-adopts that phrasing, this arm is what stops it.
    expect(OMIT_CONTROL_LABEL.toLowerCase()).not.toContain('omit this line');
    expect(OMIT_CONTROL_HINT.toLowerCase()).toContain('still clears');
    expect(OMIT_CONTROL_HINT.toLowerCase()).toContain('blank');
  });
});

// ============================================================================
// THE RULED-MUTATION SCRIPT MUST CARRY EVERY POLICY THE WRITER PERSISTS.
// ============================================================================
describe('item 2 — a payload that omits a policy ERASES it', () => {
  it('⚠️ every `*Policy` the writer persists is listed by the confirm script', () => {
    const writer = readFileSync(join(__dirname, '..', 'certification-lifecycle.ts'), 'utf-8');
    const script = readFileSync(
      join(__dirname, '..', '..', '..', '..', 'scripts', 'confirm-live-template-mappings.ts'),
      'utf-8',
    );

    // Derived from the WRITER, not typed out here — a hand-written list is the
    // second copy that goes stale the day a fourth policy is added.
    const persisted = [...writer.matchAll(/(\w+Policy): mapping\./g)].map((m) => m[1]!);
    const unique = [...new Set(persisted)];

    // Non-vacuity: an empty or one-element set would satisfy the loop below
    // while checking nothing.
    expect(unique.length).toBeGreaterThanOrEqual(3);
    expect(unique).toContain('unmentionedPolicy');

    // ⚠️ THE WRITER COERCES `?? null`, SO SILENCE IS A WRITE. A payload that
    // does not mention a policy does not leave it alone — it nulls it. And
    // `as unknown as SemanticMapping` in that script makes the omission
    // invisible to `tsc`, which is why this arm reads the SOURCE.
    // ⚠️ SCOPED TO EACH BUILDER, BECAUSE A WHOLE-FILE `toContain` IS BLIND —
    // AND ITS BLINDNESS HID A REAL DEFECT. The script has TWO projections of a
    // mapping: the PAYLOAD it sends, and the `expectedSha` it computes to prove
    // it read the current state. The first pass patched only the payload, and
    // this arm still passed, because one occurrence anywhere in the file
    // satisfies it. The consequence was a script that refuses with CONFLICT —
    // naming a concurrent editor that does not exist — on exactly the
    // population the field was carried for.
    //
    // So each builder is located and asserted SEPARATELY, and the split itself
    // is asserted non-empty: a slice that silently came back empty would make
    // every assertion below it vacuous, which is the failure this whole arm is
    // about.
    const shaAt = script.indexOf('templateTwinMappingsSha256(');
    expect(shaAt, 'the expectedSha builder was not located').toBeGreaterThan(0);
    const payloadBuilder = script.slice(0, shaAt);
    const shaBuilder = script.slice(shaAt);
    expect(payloadBuilder.length).toBeGreaterThan(500);
    expect(shaBuilder.length).toBeGreaterThan(500);

    for (const policy of unique) {
      expect(payloadBuilder, `${policy} missing from the PAYLOAD builder`).toContain(
        `${policy}: m.${policy}`,
      );
      expect(shaBuilder, `${policy} missing from the expectedSha builder`).toContain(
        `${policy}: m.${policy}`,
      );
    }
  });
});

// ============================================================================
// ACCOUNTING — nothing may fall into no bucket, or into both.
// ============================================================================
describe('item 2 — the omitted field is counted exactly once', () => {
  it('an omit is in `omitted` and NOT in `notMentioned`; a null policy is the reverse', () => {
    const omitRun = resolveOne({}, { unmentionedPolicy: 'omit' });
    const plainRun = resolveOne();
    const omitted = templateTwinCounts(omitRun.resolutions, [omitRun.field]);
    const plain = templateTwinCounts(plainRun.resolutions, [plainRun.field]);

    // ⚠️ ASSERTED PRESENT, NOT COALESCED. `omitted` is optional on the counts
    // type, so `?? 0` here would turn "the bucket does not exist" into a
    // passing zero — the precise shape of the `default_kept` accident this arm
    // is named after.
    expect(omitted.omitted).toBeDefined();
    expect(plain.omitted).toBeDefined();

    expect(omitted.omitted).toBe(1);
    expect(omitted.notMentioned).toBe(0);

    expect(plain.omitted).toBe(0);
    expect(plain.notMentioned).toBe(1);

    // ⚠️ AND THE TOTAL IS CONSERVED. `default_kept` once fell into NO bucket and
    // one unrelated dictated sentence collapsed a form's blank count 11 -> 0.
    expect(omitted.omitted! + omitted.notMentioned).toBe(plain.omitted! + plain.notMentioned);
  });
});

// ============================================================================
// THE PROMPT THE CONTROL ACTUALLY GOVERNS — "Your blanks".
// ----------------------------------------------------------------------------
// ⚠️ THIS BLOCK EXISTS BECAUSE THE CONTROL'S LABEL WAS FALSE AND EVERY OTHER
// ARM WAS GREEN. `omit` moves the field out of `notMentioned` and into
// `omitted`, which the counts arm proves — but the "Your blanks" panel does not
// read the counts. It reads `scaffoldDefaultOfferable`, which tests
// `value === null`, and an `omit` resolution is `not_mentioned` with a null
// value. So the field kept its row under the heading "Nothing was dictated for
// these", and a doctor who ticked "do not ask me about this" was asked again on
// the very next visit — the exact sentence the module header warns about,
// shipped.
//
// The counts and the panel are two different questions, and only one of them
// was being asked.
// ============================================================================
describe('item 2 — an omitted field is not put back in front of the doctor', () => {
  // ⚠️ A FULL MAPPING, NOT A TWO-KEY STUB. `scaffoldDefaultOfferable` now
  // consults `canOmitWhenUnmentioned`, which reads six more properties — a thin
  // fixture makes the predicate false for the WRONG reason (a missing
  // `expectedDataType` trips the type-compat guard) and the arm then passes
  // while proving nothing. Built from the same `mapping()` helper the rest of
  // this file uses, so it cannot drift from the real shape.
  // ⚠️ TYPED AS THE REAL VIEW, NOT `Record<string, unknown>`. The loose cast
  // was the fixture-side twin of the `as never` at the production call site:
  // it let a fixture of any shape stand in for the predicate's inputs. With
  // the real type, a fixture that stops matching the view fails to compile.
  const base = mapping(field('1'), 'ros.cardiovascular') as unknown as OmitMappingView;
  const blankNow = { status: 'not_mentioned', value: null };

  it('⚠️ scaffoldDefaultOfferable WITHDRAWS the offer for an omit field', () => {
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({
        field: f,
        mapping: { ...base, unmentionedPolicy: 'omit' },
        current: blankNow,
      }),
    ).toBe(false);
  });

  it('⚠️ AN OMIT THE RESOLVER WOULD NOT HONOUR DOES NOT TAKE THE REMEDY AWAY', () => {
    // Found by a peer session and reproduced here before fixing. On a field the
    // resolver refuses the omit for, the count does NOT move — the blank stays
    // in `notMentioned` and the doctor is still prompted — so withdrawing their
    // "Insert my default" button as well leaves them strictly worse off than not
    // ticking at all. The first cut of that clause tested `=== 'omit'` alone.
    const f = field('1');
    const refused = { ...base, unmentionedPolicy: 'omit', sourceType: 'manual' as const };
    // the resolver would NOT honour it...
    expect(canOmitWhenUnmentioned(f, refused)).toBe(false);
    // ...so the remedy stays.
    expect(scaffoldDefaultOfferable({ field: f, mapping: refused, current: blankNow })).toBe(true);
  });

  it('⚠️ NON-VACUITY — the identical field with a NULL policy IS offered', () => {
    // Without this, the arm above passes against a predicate that refuses
    // everything, which is a different bug wearing the same green.
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({
        field: f,
        mapping: { ...base, unmentionedPolicy: null },
        current: blankNow,
      }),
    ).toBe(true);
  });

  it('an UNSET policy is treated as null, not as omit', () => {
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: base, current: blankNow }),
    ).toBe(true);
  });

  // ⚠️ THIS ARM REPLACES ONE THAT ASSERTED A SINGLE COLUMN BY REGEX, AND THE
  // REPLACEMENT IS THE POINT. The old form matched `unmentionedPolicy: true`
  // inside a literal select. The predicate reads EIGHT mapping properties, so
  // that arm was green while the guard it protects was dead code — and worse,
  // it PINNED the broken shape: fixing the select made the old arm RED. An arm
  // that must be deleted to fix a bug was testing the bug.
  //
  // Widening it to eight hard-coded names would close this instance. Deriving
  // it closes the class: the map below is the SAME OBJECT production selects
  // from, so a ninth property cannot appear in the view without appearing here.
  it('⚠️ THE SELECT IS DERIVED FROM THE PREDICATE, not hand-listed beside it', () => {
    const src = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'preview-visit-document.ts'),
      'utf-8',
    );
    // the call site names the derived constant...
    expect(src).toMatch(/mapping:\s*\{\s*select:\s*OMIT_MAPPING_SELECT\s*\}/);
    // ...and does NOT hand-list columns beside it, which is how it drifted.
    expect(src).not.toMatch(/mapping:\s*\{\s*select:\s*\{/);
  });

  it('⚠️ THE MAP COVERS EVERY PROPERTY THE VIEW DECLARES — read from source', () => {
    // The view's own `Pick<>` list is the authority. Parsing it means adding a
    // property to `OmitMappingView` reds this arm until its column is named,
    // WITHOUT this test having its own copy of the list to fall out of step.
    const policySrc = readFileSync(join(__dirname, '..', 'unmentioned-policy.ts'), 'utf-8');
    const pick = policySrc.match(
      /export type OmitMappingView = Pick<\s*SemanticMapping,([\s\S]*?)>;/,
    );
    expect(pick, 'the OmitMappingView Pick<> block did not parse').not.toBeNull();
    const declared = [...(pick as RegExpMatchArray)[1].matchAll(/'([a-zA-Z]+)'/g)].map((m) => m[1]);
    // NON-VACUITY: an empty parse would satisfy every assertion below.
    expect(declared.length).toBeGreaterThanOrEqual(8);
    expect([...declared].sort()).toEqual(Object.keys(OMIT_MAPPING_COLUMN).sort());
    // and every declared column reaches the select
    for (const k of declared) {
      expect(
        OMIT_MAPPING_SELECT[OMIT_MAPPING_COLUMN[k as keyof typeof OMIT_MAPPING_COLUMN]],
        `${k} is declared on the view but its column is not selected`,
      ).toBe(true);
    }
  });

  it('⚠️ THE PROJECTION SURVIVES THE RENAME AND THE CASE — both, or a guard dies', () => {
    // Three things differ between a Prisma row and this view, and each one
    // alone silently disables a guard. This drives the real projection.
    const row = {
      required: false,
      unknownPolicy: 'blank',
      blankPolicy: 'blank',
      mappingStatus: 'UNSUPPORTED', // ⚠️ renamed AND upper-cased
      sourceType: 'extraction',
      clinicalConcept: 'ros.cardiovascular',
      practiceDefault: null,
      expectedDataType: 'text',
    };
    const view = toOmitMappingView(row);
    expect(view.status, 'the column is mappingStatus and the vocabulary is lower snake').toBe(
      'unsupported',
    );
    expect(view.expectedDataType).toBe('text');
    // NEGATIVE CONTROL — the raw row is NOT the view, which is why the cast hurt.
    expect((row as Record<string, unknown>).status).toBeUndefined();
  });

  it('⚠️ THE PREDICATE IS REACHABLE ON A ROW SHAPED LIKE PRODUCTION FETCHES IT', () => {
    // THE ARM THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT. Every other arm in
    // this describe builds its mapping from a fixture; production builds it
    // from a Prisma select. Those were different shapes, so the fixtures were
    // green while the production path never reached the omit clause at all.
    //
    // The row below carries EXACTLY the keys `OMIT_MAPPING_SELECT` fetches —
    // derived, so it cannot drift from what production asks Prisma for.
    const value: Record<string, unknown> = {
      required: false,
      unknownPolicy: 'blank',
      blankPolicy: 'blank',
      mappingStatus: 'CERTIFIED',
      sourceType: 'extraction',
      clinicalConcept: 'ros.cardiovascular',
      practiceDefault: null,
      expectedDataType: 'text',
      unmentionedPolicy: 'omit',
    };
    const row = Object.fromEntries(
      Object.keys(OMIT_MAPPING_SELECT).map((k) => [k, value[k]]),
    );
    // the fetched key set IS the selected key set — no more, no less
    expect(Object.keys(row).sort()).toEqual(Object.keys(OMIT_MAPPING_SELECT).sort());

    const asProduction = {
      ...toOmitMappingView(row),
      unmentionedPolicy: (row.unmentionedPolicy ?? null) as string | null,
    };
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: asProduction, current: blankNow }),
      'an omitted field is put back in front of the doctor',
    ).toBe(false);

    // NON-VACUITY — the identical production-shaped row with a null policy IS
    // offered, so the arm above cannot pass against a predicate refusing all.
    expect(
      scaffoldDefaultOfferable({
        field: f,
        mapping: { ...asProduction, unmentionedPolicy: null },
        current: blankNow,
      }),
    ).toBe(true);
  });

  it('⚠️ THE WRITER REFUSES TOO — the offer and the door agree', () => {
    // `insertScaffoldDefaultAction` is a server action wrapped in auth and
    // prisma; driving it here would test the mocks. What is asserted is that
    // the refusal EXISTS and that it reads the column it refuses on — the same
    // source-level check, for the same reason, as the arm above.
    const src = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'set-template-control.ts'),
      'utf-8',
    );
    expect(src).toContain("unmentionedPolicy: true");
    expect(src).toMatch(/unmentionedPolicy === 'omit'/);
  });
});

// ============================================================================
// THE WRITER REFUSES AN `omit` THE RESOLVER COULD NEVER READ.
// ============================================================================
describe('item 2 — an unreachable omit cannot be persisted', () => {
  it('certification-lifecycle refuses it, using the SHARED predicate', () => {
    const src = readFileSync(join(__dirname, '..', 'certification-lifecycle.ts'), 'utf-8');
    // The rule, and that it is the imported one rather than a fourth copy.
    expect(src).toContain("from './unmentioned-policy'");
    expect(src).toMatch(/unmentionedPolicy === 'omit'\s*&&\s*\n?\s*!canOmitWhenUnmentioned\(field, mapping\)/);
  });

  it('the surface names the INERT variant rather than repeating the promise', () => {
    const src = readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'settings', 'note-format', 'native-template-manager.tsx'),
      'utf-8',
    );
    expect(src).toContain('OMIT_INERT_LABEL');
    expect(src).toContain('twin-omit-readonly-inert-');
    // and the two labels must not be the same sentence, or the distinction is
    // decorative.
    expect(OMIT_INERT_LABEL).not.toBe(OMIT_CONTROL_LABEL);
    expect(OMIT_INERT_LABEL.toLowerCase()).toContain('no effect');
  });
});

// ============================================================================
// THE CLIENT BUNDLE — MEASURED, BECAUSE THE COMMENT THAT PROMISED IT WAS FALSE.
// ----------------------------------------------------------------------------
// ⚠️ FOUND BY A PEER SESSION'S INDEPENDENT PASS, AND IT WAS MY OWN FIX THAT
// CAUSED IT. `unmentioned-policy.ts` is value-imported by a `'use client'`
// component, so its transitive VALUE imports land in the browser. Moving
// `expectedDataTypeForFieldKind` out of `semantic-mapping/index.ts` (which
// pulls `@meddoc/ai`) into `ir.ts` looked like the safe home — and `ir.ts`
// value-imports zod and builds ~105 schemas at module scope.
//
//     746 bytes  ->  320,991 bytes, zod present     (429x)
//
// while the module header three lines above the import still read
// "NO RUNTIME IMPORTS — TYPES ONLY". A reader checks the comment, not the
// bundler.
//
// ⚠️ SO THIS ARM BUNDLES THE MODULE FOR REAL. A source-level assertion ("no
// import from ir") would have passed at 320KB the day somebody added a value
// import to the leaf instead. The property is the BYTES, so the bytes are what
// is measured — and the threshold is generous, because the failure it guards is
// three orders of magnitude, not a few hundred bytes.
// ============================================================================
describe('item 2 — the confirm surface does not pay for the engine', () => {
  it('⚠️ the client-imported module bundles small, with NO zod runtime', () => {
    // ⚠️ IN A CHILD PROCESS, DELIBERATELY. esbuild refuses to run inside
    // vitest's DOM-ish environment ("new TextEncoder().encode('') instanceof
    // Uint8Array is incorrectly false"), so an in-process attempt fails for a
    // reason that has nothing to do with the bundle. Driving the real bundler
    // out-of-process is the same shape this repo already uses for shell gates.
    const appRoot = join(__dirname, '..', '..', '..', '..');
    const modulePath = join(__dirname, '..', 'unmentioned-policy.ts');
    const script = `
      const { buildSync } = require('esbuild');
      const r = buildSync({
        stdin: {
          contents: ${JSON.stringify(
            'import { canOmitWhenUnmentioned, OMIT_CONTROL_LABEL, OMIT_CONTROL_HINT, OMIT_INERT_LABEL } from ',
          )} + ${JSON.stringify(JSON.stringify(modulePath))} + ';console.log(canOmitWhenUnmentioned,OMIT_CONTROL_LABEL,OMIT_CONTROL_HINT,OMIT_INERT_LABEL);',
          resolveDir: ${JSON.stringify(appRoot)},
          loader: 'ts',
        },
        bundle: true, platform: 'browser', format: 'esm', minify: true, write: false, logLevel: 'silent',
      });
      process.stdout.write(r.outputFiles[0].text);
    `;
    const out = execFileSync('node', ['-e', script], {
      encoding: 'utf8',
      cwd: appRoot,
      maxBuffer: 64 * 1024 * 1024,
    });

    // ⚠️ POSITIVE CONTROL FIRST. A bundle that resolved nothing would be tiny
    // and zod-free, and would satisfy both assertions below while proving
    // nothing at all.
    expect(out, 'the bundle does not contain the predicate').toContain('expectedDataType');
    expect(out.length, 'implausibly small — did it resolve?').toBeGreaterThan(300);

    expect(out.length, `client bundle is ${out.length} bytes — the engine leaked in`).toBeLessThan(
      20_000,
    );
    expect(/\bzod\b|ZodType|\$ZodError/i.test(out), 'zod reached the client bundle').toBe(false);
  });
});
