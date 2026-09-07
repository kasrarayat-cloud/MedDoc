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
/**
 * ⚠️ EVERY SPELLING THE EXTRACTOR CAN NAME — RULING #234.
 *
 * The previous form was a single regex with TWO alternatives (`field.p` and
 * `(field as X).p`) capturing only the PROPERTY. Round five demonstrated three
 * consequences, and all three were false greens:
 *
 *   · **destructuring**, **bracket access** and a **nested binding read** were
 *     invisible, so *"a guard added without its dimension reds HERE"* was false
 *     for four shapes;
 *   · the property alone is not an identity — `mapping.unknownPolicy` was
 *     constant in all rows and reported VARIED because `field.unknownPolicy`
 *     shares its name;
 *   · a helper whose parameters are not literally named `field`/`mapping` read
 *     as nothing at all.
 *
 * So this returns `"field.prop"` / `"mapping.prop"` PAIRS, and takes an alias
 * map so a helper's own parameter names resolve to the right role.
 */
type Role = 'field' | 'mapping';
const IDENT = '[A-Za-z_$][\\w$]*';

function readsIn(
  code: string,
  alias: Readonly<Record<string, Role>> = { field: 'field', mapping: 'mapping' },
): Set<string> {
  const names = Object.keys(alias);
  const out = new Set<string>();
  if (names.length === 0) return out;
  const N = names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const add = (obj: string, path: string) => out.add(`${alias[obj]}.${path}`);

  // 1 · dotted, with optional chaining and the cast form:
  //     field.p   field?.p   (field as X).p
  for (const m of code.matchAll(
    new RegExp(`(?:\\(\\s*(${N})\\s+as\\s+[^)]*\\)|\\b(${N})\\b)\\s*\\??\\.\\s*(${IDENT})`, 'g'),
  )) add((m[1] ?? m[2])!, m[3]!);

  // 2 · NESTED — `field.rendererBinding?.bindingType`. Recorded as the full
  //     path as well as its head, because the matrix varies the LEAF.
  for (const m of code.matchAll(
    new RegExp(`\\b(${N})\\b\\s*\\??\\.\\s*(${IDENT})\\s*\\??\\.\\s*(${IDENT})`, 'g'),
  )) add(m[1]!, `${m[2]}.${m[3]}`);

  // 3 · bracket access — `field['p']`, `mapping["p"]`.
  for (const m of code.matchAll(
    new RegExp(`\\b(${N})\\b\\s*\\??\\[\\s*['"]([^'"]+)['"]\\s*\\]`, 'g'),
  )) add(m[1]!, m[2]!);

  // 4 · destructuring — `const { a, b: c, d = e, ...rest } = field`.
  for (const m of code.matchAll(new RegExp(`\\{([^{}]*)\\}\\s*=\\s*(${N})\\b`, 'g'))) {
    for (const part of m[1]!.split(',')) {
      const key = part.split(':')[0]!.split('=')[0]!.trim();
      if (new RegExp(`^${IDENT}$`).test(key)) add(m[2]!, key);
    }
  }
  return out;
}

/** The parameter names a module-local helper binds to `field` / `mapping`. */
function aliasesOf(signature: string): Record<string, Role> {
  const out: Record<string, Role> = {};
  const params = signature.slice(signature.indexOf('(') + 1).split(')')[0] ?? '';
  for (const part of params.split(',')) {
    const name = part.split(':')[0]!.trim();
    const type = (part.split(':')[1] ?? '').trim();
    if (!new RegExp(`^${IDENT}$`).test(name)) continue;
    if (/Field/i.test(type) || name === 'field') out[name] = 'field';
    else if (/Mapping/i.test(type) || name === 'mapping') out[name] = 'mapping';
  }
  return out;
}

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
/**
 * ⚠️ OWNER RULING #227 — THE MATRIX'S INTENTIONAL CONSTANTS, DECLARED.
 *
 * Every property the mirror reads must be either VARIED across the
 * cross-product or named here with the reason it is held constant. The
 * derived-dimension arm reds on anything that is neither.
 *
 * This exists because the arm previously checked *mentioned in code* rather
 * than *varied*, so a property written once at a constant satisfied it —
 * measured, with a guard keyed on `field.rowPrototype` passing while the matrix
 * never varied it. Deciding which constants are deliberate is a product
 * judgement; a declaration is how a product judgement gets written down instead
 * of inferred.
 *
 * ⚠️ ADDING A LINE HERE IS A CLAIM, NOT A TEST FIX. It says: this input cannot
 * change the answer, and here is why. If you cannot write the reason in one
 * line, the honest move is to vary it.
 *
 * ⚠️ BOTH HALVES OF THE ARM FIRED ON THIS TABLE'S OWN FIRST DRAFT, which is the
 * best evidence it discriminates. It contained a second entry —
 * `unmentionedPolicy`, "the policy is pinned to 'omit'" — and the stale-
 * declaration arm rejected it: the mirror does not read that property, so the
 * exemption covered nothing and would have sat here looking load-bearing. A
 * declaration that has outlived its constant exempts nothing and hides the next
 * one.
 */
/**
 * Every property of `field` / `mapping` the mirror READS — including through a
 * TYPE CAST.
 *
 * ⚠️ THE CAST ARM EXISTS BECAUSE A PROBE OF MINE WALKED PAST THE PLAIN ONE.
 * Testing the new RED state, I injected a guard written
 * `(field as { criticality?: string }).criticality === 'high'` — and the arm
 * stayed 37/37 green, because `field.` never appears literally in that text so
 * the property was never counted as read. Not a defect in the guard; a defect
 * in the instrument watching it, and it is the SAME SHAPE as the six admin
 * doors this programme found written `(prisma.user as any).update` and
 * invisible to the obvious grep.
 *
 * Two alternatives, because a cast is how the first form is spelled when the
 * property is not on the declared type — which is exactly when a new,
 * unwatched input arrives.
 */
// ⚠️ EMPTY, AND DELIBERATELY KEPT — RULING #234.
//
// Its only entry was `rowPrototype: 'prototypes never offer …'`, and that claim
// was FALSE: measured, a prototype was offered under both binding types and
// resolved through the very branch the entry said it did not. The false
// declaration bought a 37/37 green over a planted offered-but-not-honoured lie,
// and deleting only the entry would have left the next author the same trap.
//
// ⚠️ THE MECHANISM IS NOT AT FAULT AND IS NOT WEAKENED. #227's three states —
// varied, declared, or RED — are right. What failed is that a declaration is
// only as good as the claim inside it, and this house measures claims. The
// allowlist stays so a genuinely intentional constant has somewhere to go; it
// simply must never again carry a claim nobody checked.
const INTENTIONAL_CONSTANTS: Record<string, string> = {};

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
    // ⚠️ THE FIFTH INSTANCE OF THE SAME BLINDNESS, AND THE FIRST FOUND BY THE
    // ARM ITSELF RATHER THAN BY A PASS. The mirror reads `field.kind`, and this
    // matrix held it constant at `narrative_text` — so a guard keyed on the
    // kind was invisible here. It had been "satisfied" only because the word
    // `kind` appeared in a COMMENT inside the matrix region and the derived-
    // dimension arm read the region as raw source. Comments are now stripped
    // there, which turned a passing arm into the failing one that produced this
    // line. Canon 117 names this exact instance as an open example.
    //
    // `date` is the partner: a real kind the compiler emits, whose compatible
    // `expectedDataType` differs from `narrative_text`'s, so the cross-product
    // now contains rows where the kind alone decides type-compatibility.
    const kinds = ['narrative_text', 'date'] as const;

    // The ONLY guards permitted to withhold an offer the resolver would honour.
    // Adding to this set is a product decision, not a test fix.
    // ⚠️ `row_prototype_not_offerable` JOINS IT UNDER RULING #234, and it is a
    // real accepted cost: a prototype DOES reach the omit branch and IS
    // honoured. It is withheld anyway, because a judgement recorded against a
    // prototype binds every row stamped from it — including rows that do not
    // exist yet and that the doctor has never seen. #192's rule, one surface on.
    const CONSERVATIVE_GUARDS = new Set([
      'fixed_grid_cell_deferred',
      'row_prototype_not_offerable',
    ]);
    let offeredAndHonoured = 0;
    let refusedAndNotHonoured = 0;
    let conservativeWithholds = 0;
    const disagreements: string[] = [];
    const tokenMismatches: string[] = [];

    for (const fReq of bools)
      for (const mReq of bools)
        for (const fUnknown of policies)
          // ⚠️ `mUnknown` IS NOT DECORATION — RULING #234 UNCOVERED IT.
          // `requiresClinicianInput` reads BOTH `field.unknownPolicy` and
          // `mapping.unknownPolicy` (unmentioned-policy.ts:67-68). The matrix
          // varied only the field's, and the old name-keyed `isVaried` reported
          // the mapping's as varied because the two share a name. A guard keyed
          // on the mapping's copy was invisible. A property name is not an
          // identity.
          for (const mUnknown of policies)
          for (const mBlank of policies)
            for (const sourceType of sourceTypes)
              for (const detectionStatus of detections)
                for (const clinicalConcept of concepts)
                  for (const practiceDefault of defaults)
                    for (const expectedDataType of dataTypes)
                    for (const bindingType of bindings)
                    for (const status of statuses)
                    for (const kind of kinds)
                    for (const rowPrototype of bools) {
                    const fieldOverrides = {
                      required: fReq,
                      unknownPolicy: fUnknown,
                      detectionStatus,
                      rendererBinding: { ...field('1').rendererBinding, bindingType },
                      // ⚠️ VARIED, NOT PINNED — ruling #234. This read
                      // `rowPrototype: false` with the constant DECLARED on the
                      // allowlist as "prototypes never offer". The claim was
                      // false: a prototype was offered under both binding
                      // types, and the declaration bought a 37/37 green over a
                      // planted offered-but-not-honoured lie. A dimension the
                      // mirror reads is varied or it is not covered.
                      rowPrototype,
                      kind,
                    };
                    const mappingOverrides = {
                      required: mReq,
                      unknownPolicy: mUnknown,
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
                      `mUnknown=${mUnknown} src=${sourceType} det=${detectionStatus} concept=${clinicalConcept ?? 'NONE'} ` +
                      `default=${practiceDefault === null ? 'null' : 'set'} type=${expectedDataType} bind=${bindingType} status=${status} kind=${kind} proto=${rowPrototype}`;

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
    const reads = readsIn(code);
    // `requiresClinicianInput` is called from the ladder, so its reads count too.
    const helper = src.slice(
      src.indexOf('export function requiresClinicianInput'),
      src.indexOf('export const RESOLVER_SHORT_CIRCUIT_SOURCE_TYPES') > 0
        ? src.indexOf('export const RESOLVER_SHORT_CIRCUIT_SOURCE_TYPES')
        : src.indexOf('export function omitBranchUnreachable'),
    );
    // ⚠️ RESOLVED THROUGH THE HELPER'S OWN PARAMETER NAMES, not by assuming it
    // spells them `field`/`mapping`. It does today; a helper that did not would
    // have contributed ZERO reads and widened this arm's blind spot silently.
    for (const r of readsIn(helper, aliasesOf(helper))) reads.add(r);

    // NON-VACUITY: an empty or tiny set would make the loop below prove nothing.
    expect(reads.size, `parsed only ${reads.size} reads from the mirror`).toBeGreaterThanOrEqual(8);

    // The matrix's own source is the authority on what it varies.
    //
    // ⚠️ COMMENTS STRIPPED, AND THAT IS THE ARM. Round four found this satisfied
    // by PROSE: the region is read as raw source, so a property discussed in a
    // comment counted as "varied". Demonstrated — a guard keyed on
    // `field.rowPrototype`, its token duly declared, with the word appearing
    // only in a comment here, scored 37/37 GREEN while the matrix never varied
    // it once. That is the exact failure this arm was written to prevent,
    // living inside the arm itself.
    //
    // The strip is deliberately crude (whole-line `//` and block-comment lines):
    // a matrix VARIES a property by writing it in a fixture, and fixtures are
    // code. Anything that only ever appears in prose is, by construction, not
    // varied.
    //
    // ⚠️ OWNER RULING #227 — THE RESIDUAL CLOSES BY DECLARATION, NOT JUDGEMENT.
    //
    // This arm used to check *MENTIONED IN CODE*, not *VARIED*: a property
    // written once at a constant satisfied it. Measured — a guard keyed on
    // `field.rowPrototype`, its token declared, passed. I named that residual
    // and left it open, on the ground that deciding which constants are
    // deliberate is a product judgement rather than a test fix.
    //
    // It IS a product judgement. A DECLARATION is how a product judgement gets
    // written down instead of inferred. `INTENTIONAL_CONSTANTS` above carries
    // one line of reason per held-constant property, and this arm now has
    // THREE states and none of them is silent:
    //
    //     varied across the cross-product        -> pass
    //     declared constant, with its reason     -> pass, reason on the record
    //     neither                                -> RED
    //
    // An allowlist entry is a claim somebody made on purpose. An undeclared
    // constant is an oversight wearing the same clothes, and the difference is
    // exactly what this arm could not see before.
    const thisFile = readFileSync(__filename, 'utf-8');
    const matrix = thisFile.slice(thisFile.indexOf('OFFERED  ⟺  HONOURED'));
    const varied = matrix
      .slice(0, matrix.indexOf('expect(disagreements)'))
      .split('\n')
      .filter((l) => {
        const t = l.trimStart();
        return !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*');
      })
      .join('\n');

    // ⚠️ A DIMENSION IS *VARIED* ONLY IF IT IS DRIVEN BY A LOOP VARIABLE,
    // AND IT IS KEYED ON THE (OBJECT, PROPERTY) PAIR — RULING #234.
    //
    // Keying on the property NAME alone reported `mapping.unknownPolicy` as
    // varied on the strength of `field.unknownPolicy` being varied. They share
    // a name and nothing else: the mapping's copy was constant across all rows
    // and a guard reading it was invisible. **A property name is not an
    // identity.** So the matrix's two override literals are searched
    // SEPARATELY, and a pair is varied only inside its own object.
    const loopVars = new Set(
      [...matrix.matchAll(/for \(const (\w+) of (\w+)\)/g)].map((m) => m[1]!),
    );

    /** The object literal assigned to `<name>`, braces included. */
    const blockOf = (name: string): string => {
      const i = varied.indexOf(`const ${name} = {`);
      if (i < 0) return '';
      const open = varied.indexOf('{', i);
      let depth = 0;
      for (let k = open; k < varied.length; k += 1) {
        if (varied[k] === '{') depth += 1;
        else if (varied[k] === '}') {
          depth -= 1;
          if (depth === 0) return varied.slice(open, k + 1);
        }
      }
      return '';
    };
    const BLOCK: Record<Role, string> = {
      field: blockOf('fieldOverrides'),
      mapping: blockOf('mappingOverrides'),
    };
    expect(BLOCK.field, 'the fieldOverrides literal moved — this arm reads nothing').not.toBe('');
    expect(BLOCK.mapping, 'the mappingOverrides literal moved — this arm reads nothing').not.toBe('');

    /**
     * `null` when the key is absent; `''` when written as SHORTHAND (`kind,`);
     * otherwise the value text, to the entry's own comma at depth zero.
     */
    const entryFor = (text: string, key: string): string | null => {
      const m = new RegExp(`\\b${key}\\b\\s*(:)?`).exec(text);
      if (!m) return null;
      if (!m[1]) return '';
      const start = m.index + m[0].length;
      let depth = 0;
      for (let k = start; k < text.length; k += 1) {
        const c = text[k];
        if (c === '{' || c === '[' || c === '(') depth += 1;
        else if (c === '}' || c === ']' || c === ')') {
          if (depth === 0) return text.slice(start, k);
          depth -= 1;
        } else if (c === ',' && depth === 0) return text.slice(start, k);
      }
      return text.slice(start);
    };

    const mentionsLoopVar = (text: string) =>
      [...loopVars].some((v) => new RegExp(`\\b${v}\\b`).test(text));

    const isVaried = (pair: string) => {
      const [role, head, leaf] = pair.split('.') as [Role, string, string?];
      const block = BLOCK[role];
      if (!block) return false;
      const entry = entryFor(block, head);
      if (entry === null) return false;
      if (leaf === undefined) {
        // shorthand (`rowPrototype,`) is varied exactly when the key IS a loop
        // variable; `head: <value>` is varied when the value mentions one.
        return entry === '' ? loopVars.has(head) : mentionsLoopVar(entry);
      }
      // ⚠️ NESTED — `field.rendererBinding.bindingType`. The matrix writes
      // `rendererBinding: { ...field('1').rendererBinding, bindingType }`, so
      // the LEAF is what varies and the head is a spread of constants. Checking
      // the head alone would call the whole binding varied and hide a second,
      // constant property sitting beside `bindingType`.
      const inner = entryFor(entry, leaf);
      if (inner === null) return false;
      return inner === '' ? loopVars.has(leaf) : mentionsLoopVar(inner);
    };

    const undeclared = [...reads].filter(
      (r) => !isVaried(r) && !(r in INTENTIONAL_CONSTANTS),
    );
    expect(
      undeclared,
      `the mirror reads [${undeclared.join(', ')}] and the biconditional neither ` +
        `VARIES ${undeclared.length === 1 ? 'it' : 'them'} nor DECLARES ` +
        `${undeclared.length === 1 ? 'it' : 'them'} in INTENTIONAL_CONSTANTS — so a ` +
        `guard keyed on ${undeclared.length === 1 ? 'that input' : 'those inputs'} is ` +
        `invisible to this matrix. Vary it, or declare it with the reason it is ` +
        `held constant. Ruling #227: an undeclared constant is an oversight ` +
        `wearing an intentional one's clothes.`,
    ).toEqual([]);

    // ⚠️ AND THE ALLOWLIST IS NOT A DUMPING GROUND — it may not name a property
    // the mirror does not read, or one the matrix already varies. Both would be
    // a stale declaration quietly widening the exemption.
    const staleDeclarations = Object.keys(INTENTIONAL_CONSTANTS).filter(
      (k) => !reads.has(k) || isVaried(k),
    );
    expect(
      staleDeclarations,
      `INTENTIONAL_CONSTANTS declares [${staleDeclarations.join(', ')}] which the ` +
        `mirror does not read, or which the matrix now varies. A declaration that ` +
        `has outlived its constant exempts nothing and hides the next one.`,
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

  // ══════════════════════════════════════════════════════════════════════════
  // RULING #234 — THE PROPERTY THE FALSE DECLARATION WAS REACHING FOR.
  //
  // #227's allowlist asserted "prototypes never offer" and nobody measured it.
  // The cure is not a better sentence: it is this arm plus the varied
  // dimension. #192 says a prototype must not clone its text into every row;
  // that bound the KEEP and it binds the OFFER, because a judgement recorded
  // against a prototype is recorded against every row stamped from it —
  // including rows that do not exist yet and the doctor has never seen.
  // ══════════════════════════════════════════════════════════════════════════
  it.each([['content_control'], ['table_cell']] as const)(
    '⚠️ a repeating-section PROTOTYPE is never offered — %s binding',
    (bindingType) => {
      const f = field('1', {
        rowPrototype: true,
        rendererBinding: { ...field('1').rendererBinding, bindingType },
      });
      const m = mapping(f, 'ros.cardiovascular');

      expect(canOmitWhenUnmentioned(f, m)).toBe(false);
      expect(omitBranchUnreachable(f, m)).toBe('row_prototype_not_offerable');
      expect(OMIT_GUARD_TOKEN_PREFIXES['row_prototype_not_offerable']).toBeDefined();
    },
  );

  it('⚠️ …and the withhold is CONSERVATIVE, stated as one — the resolver WOULD have honoured it', () => {
    // The non-vacuity half. If a prototype were refused by the resolver anyway,
    // this guard would be free and the arm above would prove nothing about the
    // cost being accepted. It is not free: measured, the omit IS honoured.
    const { resolution } = resolveOne(
      { rowPrototype: true },
      { unmentionedPolicy: 'omit' },
    );
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
  });

  it('⚠️ the non-prototype grid cell still routes to its OWN guard, not the new one', () => {
    // The guard above returns first for every prototype, so the `table_cell`
    // ladder below it must still be reachable — otherwise this change silently
    // swallowed `fixed_grid_cell_deferred`.
    const f = field('1', {
      rowPrototype: false,
      rendererBinding: { ...field('1').rendererBinding, bindingType: 'table_cell' },
    });
    expect(omitBranchUnreachable(f, mapping(f, 'ros.cardiovascular')))
      .toBe('fixed_grid_cell_deferred');
  });
});

// ============================================================================
// RULING #234 — THE EXTRACTOR ITSELF IS TESTED, because the arm that uses it is
// only as good as what it can SEE. Round five demonstrated four blind spots and
// each one made "a guard added without its dimension reds HERE" false.
// ============================================================================
describe('readsIn — every spelling the extractor can name', () => {
  it('the dotted form, with optional chaining and the cast', () => {
    expect(readsIn('field.required')).toContain('field.required');
    expect(readsIn('mapping?.sourceType')).toContain('mapping.sourceType');
    expect(readsIn('(field as { x: 1 }).criticality')).toContain('field.criticality');
  });

  it('⚠️ DESTRUCTURING — invisible before, and it is how a helper usually reads', () => {
    expect(readsIn('const { required, kind } = field;')).toContain('field.kind');
    expect(readsIn('const { sourceType: s } = mapping;')).toContain('mapping.sourceType');
    expect(readsIn('const { practiceDefault = null } = mapping;'))
      .toContain('mapping.practiceDefault');
  });

  it('⚠️ BRACKET ACCESS — invisible before', () => {
    expect(readsIn("field['rowPrototype']")).toContain('field.rowPrototype');
    expect(readsIn('mapping["blankPolicy"]')).toContain('mapping.blankPolicy');
  });

  it('⚠️ THE NESTED BINDING READ — the leaf is the dimension, not the head', () => {
    const r = readsIn('field.rendererBinding?.bindingType === "table_cell"');
    expect(r).toContain('field.rendererBinding');
    expect(r).toContain('field.rendererBinding.bindingType');
  });

  it('⚠️ THE PAIR IS THE IDENTITY — the same property on two objects is two reads', () => {
    const r = readsIn('field.unknownPolicy === mapping.unknownPolicy');
    expect(r).toContain('field.unknownPolicy');
    expect(r).toContain('mapping.unknownPolicy');
    expect(r.size).toBe(2);
  });

  it('⚠️ A MODULE-LOCAL HELPER RESOLVES THROUGH ITS OWN PARAMETER NAMES', () => {
    const sig = 'function g(f: Pick<TemplateField, "kind">, m: SemanticMapping)';
    const alias = aliasesOf(sig);
    expect(alias).toEqual({ f: 'field', m: 'mapping' });
    expect(readsIn('f.kind || m.sourceType', alias))
      .toEqual(new Set(['field.kind', 'mapping.sourceType']));
  });

  it('does NOT invent reads from unrelated identifiers', () => {
    expect(readsIn('shielding.required || remapping.kind')).toEqual(new Set());
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
  // ⚠️ THE DECIDING INPUT IS THE RESOLUTION'S `reasonCode`, AND THE PREVIOUS
  // VERSION OF THIS BLOCK HELD IT CONSTANT. Every arm below used one shared
  // `blankNow = { status: 'not_mentioned', value: null }`, and BOTH universes
  // this feature must tell apart project onto exactly that shape:
  //
  //   HONOURED : { status:'not_mentioned', value:null, reasonCode:'omitted_unsupported_default' }
  //   REFUSED  : { status:'not_mentioned', value:null, reasonCode:'temporality_not_approved' }
  //
  // With `reasonCode` dropped they are byte-identical, so an arm asserting
  // `=== false` was satisfied by both and could never witness an
  // over-withdrawal. That is this file's own catalogued failure — a control
  // that holds constant the one input deciding the answer — and it PINNED the
  // bug: the correct fix turns the old green arm red.
  const base = mapping(field('1'), 'ros.cardiovascular') as Record<string, unknown>;
  const omitted = { status: 'not_mentioned', value: null, reasonCode: 'omitted_unsupported_default' };
  const refusedVisit = { status: 'not_mentioned', value: null, reasonCode: 'temporality_not_approved' };
  const noFacts = { status: 'not_mentioned', value: null, reasonCode: 'fact_not_mentioned' };

  it('⚠️ the offer is WITHDRAWN when the resolver ACTUALLY honoured the omit', () => {
    expect(
      scaffoldDefaultOfferable({ field: field('1'), mapping: base, current: omitted }),
    ).toBe(false);
  });

  it('⚠️ THE ARM THAT WOULD HAVE CAUGHT THE REGRESSION — a visit the omit did NOT fire on keeps the remedy', () => {
    // The doctor ticked "expected blank"; on THIS visit they dictated the
    // field's own concept at a temporality the mapping does not approve, so the
    // resolver returned `temporality_not_approved`, the field stayed in
    // `notMentioned`, and the surface says "1 still blank". Withdrawing the
    // remedy here leaves them strictly worse off than not ticking at all.
    //
    // The withdrawal used to be decided by `canOmitWhenUnmentioned`, a CONFIRM-
    // time property of the mapping — true for this field on EVERY visit. So it
    // withdrew here too. Measured over 7 visit shapes: 5 false rejections.
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: base, current: refusedVisit }),
      'a visit where the omit did not fire must keep "Insert my default"',
    ).toBe(true);
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: base, current: noFacts }),
      'a visit that extracted no facts at all must keep it too',
    ).toBe(true);
  });

  it('⚠️ NON-VACUITY — the SAME field and SAME mapping differ ONLY by reasonCode', () => {
    // The two inputs below are identical except for the one property that
    // decides the answer, and they must give OPPOSITE answers. An arm that
    // varies nothing is satisfied by a predicate that always returns the same
    // thing, which is a different bug wearing this arm's green.
    const f = field('1');
    const withdrawn = scaffoldDefaultOfferable({ field: f, mapping: base, current: omitted });
    const kept = scaffoldDefaultOfferable({ field: f, mapping: base, current: refusedVisit });
    expect({ ...omitted, reasonCode: 'X' }).toEqual({ ...refusedVisit, reasonCode: 'X' });
    expect(withdrawn).toBe(false);
    expect(kept).toBe(true);
    expect(withdrawn).not.toBe(kept);
  });

  it('⚠️ THE TOKEN IS THE RESOLVER\'S OWN, not a string this test invented', () => {
    // A proof that retypes what it checks agrees with whichever copy its author
    // read last. The token is read from the emitter.
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src, 'the resolver no longer emits the token this gate keys on').toContain(
      "'omitted_unsupported_default'",
    );
    // and the consumer keys on the same literal
    const consumer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(consumer).toContain("current?.reasonCode === 'omitted_unsupported_default'");
  });

  it('⚠️ THE DECISION IS NOT TAKEN FROM THE MAPPING — that is what made it wrong', () => {
    // `unmentionedPolicy` and `canOmitWhenUnmentioned` are static properties of
    // the mapping: true on every visit or none. Neither may decide a per-visit
    // question, and the previous version used both.
    const consumer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    const fn = consumer.slice(consumer.indexOf('export function scaffoldDefaultOfferable'));
    const body = fn.slice(0, fn.indexOf('\n}'));
    const code = body
      .split('\n')
      .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
      .join('\n');
    // NON-VACUITY: the slice must actually contain the clause under test.
    expect(code).toContain('reasonCode');
    expect(code, 'the mapping policy is being consulted again').not.toContain('unmentionedPolicy');
    expect(code, 'a confirm-time predicate is deciding a per-visit question').not.toContain(
      'canOmitWhenUnmentioned',
    );
  });

  it('⚠️ THE DOOR DOES NOT REFUSE ON THE STATIC POLICY — and this arm reads CODE, not prose', () => {
    // ⚠️ THE ARM THIS REPLACES WAS VACUOUS AND WAS CAUGHT BEING VACUOUS. It did
    // `expect(src).toMatch(/unmentionedPolicy === 'omit'/)` over the WHOLE FILE.
    // The static refusal was then deleted and this arm STAYED GREEN, because
    // the only remaining occurrence of that string is inside the comment
    // explaining the deletion. A substring assertion over a whole source file
    // is satisfied by the paragraph describing the thing it claims to check.
    //
    // So: comments are stripped before anything is asserted, and the arm proves
    // its own non-vacuity by requiring the stripped source to still contain the
    // symbols it reasons about.
    const raw = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'set-template-control.ts'),
      'utf-8',
    );
    const code = raw
      .split('\n')
      .filter((l) => {
        const t2 = l.trim();
        return !t2.startsWith('//') && !t2.startsWith('*') && !t2.startsWith('/*');
      })
      .join('\n');

    // NON-VACUITY: the stripped source must still be the file we mean.
    expect(code).toContain('insertScaffoldDefaultAction');
    expect(code).toContain('undoScaffoldDefaultAction');

    // The door must NOT gate on a confirm-time property of the mapping. The
    // offer gates per visit; a static refusal here produced a button that
    // errored for the doctor on every visit the omit did not fire on.
    expect(
      code,
      'the insert door is refusing on the static policy again — it will refuse clicks the panel offers',
    ).not.toMatch(/unmentionedPolicy\s*===\s*'omit'/);

    // ...and it must not fetch the column for a decision it no longer makes.
    expect(code, 'a column fetched for a decision nobody makes').not.toContain(
      'unmentionedPolicy: true',
    );
  });

  it('⚠️ RULING #203 — THE CACHE KEY MOVED WITH THE FIX, or a warm entry serves the OLD offer list', () => {
    // `insertableDefaults` lives INSIDE the cached payload (`CachedFill`, TTL 30
    // minutes). This fix changes which fields that list CONTAINS and not its
    // SHAPE, so a pre-deploy entry deserialises perfectly and serves the
    // pre-fix offer list — a default offered on every omit field — for up to the
    // TTL. No schema check can see a contents-only change.
    const cache = readFileSync(join(__dirname, '..', '..', 'docx-preview', 'fill-cache.ts'), 'utf-8');
    const m = cache.match(/const KEY_VERSION = 'v(\d+)';/);
    // NON-VACUITY: a failed parse would make every assertion below trivially true.
    expect(m, 'KEY_VERSION did not parse — this arm proves nothing until it does').not.toBeNull();
    const v = Number((m as RegExpMatchArray)[1]);
    expect(v, 'KEY_VERSION must be at least v7 — ruling #203').toBeGreaterThanOrEqual(7);

    // ...and it is bound to THIS fix, not merely bumped at some point: the
    // per-visit gate and the key move together or the pairing is a coincidence.
    const offer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(offer).toContain("current?.reasonCode === 'omitted_unsupported_default'");

    // The writer and the invalidation scan share ONE constant, by construction —
    // the v4->v5 bump moved the writer and not the scan. Divergence must stay
    // unrepresentable.
    expect(cache.match(/const KEY_VERSION/g) ?? []).toHaveLength(1);
    expect(cache.match(/\$\{KEY_VERSION\}/g) ?? []).toHaveLength(2);
  });

  it('⚠️ THE PER-VISIT GATE LIVES IN THE OFFER, and the two agree by construction', () => {
    // The offer and the door agreed before by both consulting the mapping. They
    // agree now by the door consulting NOTHING and the offer consulting the
    // resolution — which is the only place the per-visit answer exists.
    const offer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(offer).toContain("current?.reasonCode === 'omitted_unsupported_default'");

    // An insert remains a HUMAN act and is audited as one — ruling #194's
    // principle, and the reason removing the door's refusal is safe.
    const door = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'set-template-control.ts'),
      'utf-8',
    );
    expect(door).toContain('DEFAULT_INSERTED_BY_DOCTOR');
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
