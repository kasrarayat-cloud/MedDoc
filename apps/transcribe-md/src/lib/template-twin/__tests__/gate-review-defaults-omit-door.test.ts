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
//   · ANY AUDIT ROW. Mapping edits are not audited today and this change adds no
//     audit action — see the PR body, where that is raised rather than assumed.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { resolveTemplateFields } from '../resolver';
import { templateTwinCounts } from '../ir';
import {
  requiresClinicianInput,
  canOmitWhenUnmentioned,
  omitBranchUnreachable,
  OMIT_GUARD_TOKEN_PREFIXES,
  OMIT_CONTROL_LABEL,
  OMIT_CONTROL_HINT,
} from '../unmentioned-policy';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

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

    let offeredAndHonoured = 0;
    let refusedAndNotHonoured = 0;
    const disagreements: string[] = [];
    const tokenMismatches: string[] = [];

    for (const fReq of bools)
      for (const mReq of bools)
        for (const fUnknown of policies)
          for (const mBlank of policies)
            for (const sourceType of sourceTypes)
              for (const detectionStatus of detections)
                for (const clinicalConcept of concepts)
                  for (const practiceDefault of defaults) {
                    const fieldOverrides = { required: fReq, unknownPolicy: fUnknown, detectionStatus };
                    const mappingOverrides = {
                      required: mReq,
                      blankPolicy: mBlank,
                      sourceType,
                      clinicalConcept,
                      practiceDefault,
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
                      `default=${practiceDefault === null ? 'null' : 'set'}`;

                    if (offered !== honoured) {
                      disagreements.push(
                        `${shape} -> offered=${offered} honoured=${honoured} ` +
                          `(resolver said ${resolution.reasonCode})`,
                      );
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
    for (const policy of unique) {
      expect(script).toContain(`${policy}:`);
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
