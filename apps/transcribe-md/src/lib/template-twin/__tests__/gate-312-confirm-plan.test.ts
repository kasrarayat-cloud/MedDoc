// ============================================================================
// #311(d) / #312 — THE CONFIRM'S PLANNER. Pure: no database, no writer.
// ----------------------------------------------------------------------------
// The claims, each with the arm that would fail if it were false:
//   · it confirms EXACTLY the ten, and passes the 43 through BY REFERENCE
//   · it refuses when ANY attribute differs from the proposal the decisions
//     were made against — the drift matrix is DERIVED from the schema's keys,
//     so an attribute added later is covered or this file goes red
//   · a second run, a wrong version, a wrong count refuse
//   · the table itself is sound: ten distinct ids, one kind change, two
//     visit_metadata, every confirmed concept registered
//   · the audit accounting and the arguments refuse vacuous input
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { isRegisteredConcept } from '../concept-registry';
import { SemanticMappingSchema, type SemanticMapping } from '../ir';
import {
  RULING_312,
  canonicalJson,
  countFailedGuards,
  missingAuditTargets,
  parseConfirmArgs,
  planConfirmation,
  withoutAddress,
  type ConfirmField,
  type ConfirmTable,
} from '../confirm-plan';

const VERSION = RULING_312.compiledVersionId;
const DRIFT = 'decided fields whose proposal DRIFTED from the judged one';

function certifiedMapping(fieldId: string): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    sourceType: 'extraction',
    clinicalConcept: 'plan',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  });
}

const hex24 = (n: number) => n.toString(16).padStart(24, '0');

/** The 53-field shape as the re-issue left it: 43 certified, the ten exactly as judged. */
function reissued(): ConfirmField[] {
  const decided: ConfirmField[] = RULING_312.decisions.map((d) => ({
    fieldId: d.fieldId,
    displayOrder: d.displayOrder,
    originalLabel: d.label,
    // Through the STRICT schema, as the writer's reader would return it.
    mapping: SemanticMappingSchema.parse({ fieldId: d.fieldId, ...d.judged }),
  }));
  const certified: ConfirmField[] = Array.from({ length: 43 }, (_, i) => {
    const fieldId = `ttf_${hex24(1000 + i)}`;
    return { fieldId, displayOrder: 100 + i, originalLabel: `Certified ${i}`, mapping: certifiedMapping(fieldId) };
  });
  return [...decided, ...certified].sort((a, b) => a.displayOrder - b.displayOrder);
}

const EXPECT = { fields: 53, alreadyCertified: 43, confirm: 10 };

function plan(fields = reissued(), table: ConfirmTable = RULING_312, expectOver = {}) {
  return planConfirmation({ compiledVersionId: VERSION, fields, table, expect: { ...EXPECT, ...expectOver } });
}

function refusedOn(p: ReturnType<typeof plan>): string[] {
  expect(p.ok).toBe(false);
  return p.ok ? [] : p.failed;
}

const PATIENT = 'ttf_e59e5a33c5975f8b3744dc2f';

function withPatient(over: Partial<SemanticMapping>): ConfirmField[] {
  const fields = reissued();
  const i = fields.findIndex((f) => f.fieldId === PATIENT);
  fields[i] = { ...fields[i]!, mapping: SemanticMappingSchema.parse({ ...fields[i]!.mapping, ...over }) };
  return fields;
}

describe('#312 · the planner confirms exactly the ten', () => {
  it('the happy path: 53 rows out, every one certified, ten moved', () => {
    const p = plan();
    expect(p.ok).toBe(true);
    if (!p.ok) return;
    expect(countFailedGuards(p.guards)).toBe(0);
    expect(p.payload).toHaveLength(53);
    expect(p.payload.every((m) => m.status === 'certified')).toBe(true);
    expect(p.moves).toHaveLength(10);
  });

  it('⚠️ the 43 are passed BY REFERENCE — nothing about a transferred row can change here', () => {
    const fields = reissued();
    const p = plan(fields);
    if (!p.ok) throw new Error('expected ok');
    const decided = new Set(RULING_312.decisions.map((d) => d.fieldId));
    let same = 0;
    fields.forEach((f, i) => {
      if (decided.has(f.fieldId)) {
        expect(p.payload[i]).not.toBe(f.mapping);
      } else {
        expect(p.payload[i]).toBe(f.mapping);
        same += 1;
      }
    });
    expect(same).toBe(43);
  });

  it('each confirmed row carries its decision, and nothing else about it moves', () => {
    const fields = reissued();
    const p = plan(fields);
    if (!p.ok) throw new Error('expected ok');
    for (const d of RULING_312.decisions) {
      const i = fields.findIndex((f) => f.fieldId === d.fieldId);
      const after = p.payload[i]!;
      expect(after.sourceType).toBe(d.confirmAs.sourceType);
      expect(after.clinicalConcept).toBe(d.confirmAs.clinicalConcept);
      expect(after.status).toBe('certified');
      const strip = (m: SemanticMapping) => {
        const { sourceType: _s, clinicalConcept: _c, status: _t, ...rest } = withoutAddress(m);
        return rest;
      };
      expect(canonicalJson(strip(after))).toBe(canonicalJson(strip(fields[i]!.mapping)));
    }
  });

  it('⚠️ telehealth goes to manual with NO concept and NO policy — the writer refuses manual+omit', () => {
    const p = plan();
    if (!p.ok) throw new Error('expected ok');
    const tele = p.payload.find((m) => m.fieldId === 'ttf_86cf11d77e63d9e64a6b045b')!;
    expect(tele.sourceType).toBe('manual');
    expect(tele.clinicalConcept).toBeNull();
    expect(tele.unmentionedPolicy ?? null).toBeNull();
  });

  it('every payload row survives the STRICT schema the writer parses with', () => {
    const p = plan();
    if (!p.ok) throw new Error('expected ok');
    for (const m of p.payload) expect(() => SemanticMappingSchema.parse(m)).not.toThrow();
  });

  it('does not mutate its input', () => {
    const fields = reissued();
    const snapshot = JSON.stringify(fields);
    plan(fields);
    expect(JSON.stringify(fields)).toBe(snapshot);
  });
});

describe('#312 · ANY drift from the judged proposal refuses the whole act', () => {
  // ⚠️ DERIVED FROM THE SCHEMA, NOT WRITTEN BY HAND. The first draft compared
  // seven attributes, and the refutation pass certified an edited Marital row
  // (`blankPolicy`, `approvedSynonyms`) that nobody judged. Every key the
  // mapping schema has, except the address, must refuse when it alone moves.
  // A key the schema gains later has no alternate here and fails the coverage
  // arm below — the matrix cannot silently fall behind the schema.
  const ALTERNATE: Record<string, unknown> = {
    sourceType: 'extraction',
    clinicalConcept: 'visit_metadata.patient_age',
    expectedDataType: 'number',
    polarityBehavior: 'affirmative_only',
    temporality: 'historical',
    laterality: 'optional',
    unitPolicy: 'optional',
    approvedSynonyms: ['Single'],
    conceptScope: ['visit_metadata.patient_name'],
    required: true,
    blankPolicy: 'requires_input',
    unknownPolicy: 'requires_input',
    unmentionedPolicy: 'omit',
    practiceDefault: 'Jane Doe',
    status: 'needs_confirmation',
  };
  const KEYS = Object.keys(SemanticMappingSchema.shape).filter((k) => k !== 'fieldId');

  it('⚠️ coverage: every schema key has an alternate, and nothing else does', () => {
    expect([...KEYS].sort()).toEqual(Object.keys(ALTERNATE).sort());
  });

  it.each(KEYS)('⚠️ drift in `%s` alone refuses', (key) => {
    const fields = withPatient({ [key]: ALTERNATE[key] } as Partial<SemanticMapping>);
    const i = fields.findIndex((f) => f.fieldId === PATIENT);
    // The alternate really differs — an arm whose mutation equals the original proves nothing.
    expect(canonicalJson(withoutAddress(fields[i]!.mapping))).not.toBe(
      canonicalJson(RULING_312.decisions.find((d) => d.fieldId === PATIENT)!.judged),
    );
    expect(refusedOn(plan(fields))).toContain(DRIFT);
  });

  it('a REORDERED synonym list is a different proposal', () => {
    expect(refusedOn(plan(withPatient({ approvedSynonyms: ['Name', 'Pt Name', 'Patient Name'] })))).toContain(DRIFT);
  });

  it('a relabelled field is drift, even with an identical mapping', () => {
    const fields = reissued();
    const i = fields.findIndex((f) => f.fieldId === 'ttf_73ef2a9a25aa550b8ad8e170');
    fields[i] = { ...fields[i]!, originalLabel: 'Date of birth' };
    expect(refusedOn(plan(fields))).toContain(DRIFT);
  });

  it('a moved displayOrder is drift', () => {
    const fields = reissued();
    const i = fields.findIndex((f) => f.fieldId === PATIENT);
    fields[i] = { ...fields[i]!, displayOrder: 99 };
    expect(refusedOn(plan(fields))).toContain(DRIFT);
  });
});

describe('#312 · it refuses anything else that is not the judged state', () => {
  it('a decided row that is already certified refuses — the act has run, or someone confirmed it', () => {
    expect(refusedOn(plan(withPatient({ status: 'certified' })))).toContain('decided fields that are ALREADY certified');
  });

  it('⚠️ RE-RUNNING the planner on its own output refuses — the act cannot apply twice', () => {
    const fields = reissued();
    const first = plan(fields);
    if (!first.ok) throw new Error('expected ok');
    const after = fields.map((f, i) => ({ ...f, mapping: first.payload[i]! }));
    const failed = refusedOn(plan(after));
    expect(failed).toContain('decided fields that are ALREADY certified');
    expect(failed).toContain('fields CERTIFIED before the act');
  });

  it('an undecided row that is NOT certified refuses — the transfer was not what we judged', () => {
    const fields = reissued();
    const i = fields.findIndex((f) => f.originalLabel === 'Certified 7');
    fields[i] = { ...fields[i]!, mapping: { ...fields[i]!.mapping, status: 'recognized' } };
    const failed = refusedOn(plan(fields));
    expect(failed).toContain('undecided fields that are NOT certified');
    expect(failed).toContain('fields CERTIFIED before the act');
  });

  it('a decision naming a field that is not on the version refuses', () => {
    const fields = reissued().filter((f) => f.fieldId !== 'ttf_ef6e199276f1691e18cf84d8');
    expect(refusedOn(plan(fields))).toContain('decisions naming a field NOT on this version');
  });

  it('the wrong compiled version refuses', () => {
    const p = planConfirmation({
      compiledVersionId: '18a7ae19-0d23-44a5-8e98-5459081782be',
      fields: reissued(),
      table: RULING_312,
      expect: EXPECT,
    });
    expect(refusedOn(p)).toContain('the table is for THIS compiled version');
  });

  it('⚠️ an EMPTY field set refuses — every count would otherwise read 0 === 0', () => {
    const empty: ConfirmTable = { ...RULING_312, decisions: [] };
    expect(refusedOn(plan([], empty, { fields: 0, alreadyCertified: 0, confirm: 0 }))).toContain(
      'the field set is non-empty',
    );
  });

  it('a duplicated decision refuses', () => {
    const dup: ConfirmTable = { ...RULING_312, decisions: [...RULING_312.decisions, RULING_312.decisions[0]!] };
    expect(refusedOn(plan(reissued(), dup, { confirm: 11 }))).toContain('decisions sharing a fieldId');
  });

  it('a decision judged against an already-certified proposal refuses', () => {
    const [first, ...rest] = RULING_312.decisions;
    const bad: ConfirmTable = { ...RULING_312, decisions: [{ ...first!, judged: { ...first!.judged, status: 'certified' } }, ...rest] };
    expect(refusedOn(plan(reissued(), bad))).toContain('decisions judged against an already-CERTIFIED proposal');
  });

  it('⚠️ a table confirming a MANUAL row WITH a concept refuses — manual carries no evidence', () => {
    const bad: ConfirmTable = {
      ...RULING_312,
      decisions: RULING_312.decisions.map((d) =>
        d.confirmAs.sourceType === 'manual' ? { ...d, confirmAs: { sourceType: 'manual', clinicalConcept: 'plan' } } : d,
      ),
    };
    expect(refusedOn(plan(reissued(), bad))).toContain('manual confirmations carrying a concept');
  });

  it('⚠️ a table confirming a MODEL-FILLED row with NO concept refuses — the writer would certify an empty slot', () => {
    const bad: ConfirmTable = {
      ...RULING_312,
      decisions: RULING_312.decisions.map((d) =>
        d.label === 'Marital status' ? { ...d, confirmAs: { sourceType: 'extraction', clinicalConcept: null } } : d,
      ),
    };
    expect(refusedOn(plan(reissued(), bad))).toContain('non-manual confirmations carrying NO concept');
  });

  it('a mapping addressed to a different field refuses', () => {
    const fields = reissued();
    fields[5] = { ...fields[5]!, mapping: { ...fields[5]!.mapping, fieldId: fields[6]!.fieldId } };
    expect(refusedOn(plan(fields))).toContain('mappings addressed to a different field');
  });

  it('a wrong declared count refuses', () => {
    expect(refusedOn(plan(reissued(), RULING_312, { fields: 52 }))).toContain('fields on the version');
    expect(refusedOn(plan(reissued(), RULING_312, { alreadyCertified: 42 }))).toContain(
      'fields CERTIFIED before the act',
    );
  });

  it('a refusal reports EVERY failing guard, not just the first', () => {
    const failed = refusedOn(plan(withPatient({ status: 'certified' }), RULING_312, { fields: 99 }));
    expect(failed.length).toBeGreaterThanOrEqual(3);
  });
});

describe('#312 · the table itself', () => {
  const ds = RULING_312.decisions;

  it('ten decisions, ten distinct well-formed fieldIds', () => {
    expect(ds).toHaveLength(10);
    expect(new Set(ds.map((d) => d.fieldId)).size).toBe(10);
    for (const d of ds) expect(d.fieldId).toMatch(/^ttf_[a-f0-9]{24}$/);
  });

  it('every judged proposal is a valid mapping', () => {
    for (const d of ds) expect(() => SemanticMappingSchema.parse({ fieldId: d.fieldId, ...d.judged })).not.toThrow();
  });

  it('⚠️ exactly ONE row is not confirmed as proposed, and it is telehealth', () => {
    const changed = ds.filter(
      (d) =>
        d.confirmAs.sourceType !== d.judged.sourceType ||
        d.confirmAs.clinicalConcept !== d.judged.clinicalConcept,
    );
    expect(changed.map((d) => d.label)).toEqual(['Telehealth consent']);
  });

  it('two rows are visit_metadata — Patient and Age — each named on its own (#261)', () => {
    expect(ds.filter((d) => d.confirmAs.sourceType === 'visit_metadata').map((d) => d.label)).toEqual([
      'Patient',
      'Age',
    ]);
  });

  it('every confirmed concept is REGISTERED — an off-registry concept is nulled by the next compile', () => {
    const concepts = ds.map((d) => d.confirmAs.clinicalConcept).filter((c): c is string => c !== null);
    expect(concepts).toHaveLength(9);
    for (const c of concepts) expect(isRegisteredConcept(c), c).toBe(true);
  });

  it('every decision states why', () => {
    for (const d of ds) expect(d.why.length).toBeGreaterThan(10);
  });
});

describe('#312 · canonical comparison', () => {
  it('key order does not matter, absent and undefined are the same, array order does', () => {
    expect(canonicalJson({ a: 1, b: [1, 2] })).toBe(canonicalJson({ b: [1, 2], a: 1 }));
    expect(canonicalJson({ a: 1, u: undefined })).toBe(canonicalJson({ a: 1 }));
    expect(canonicalJson({ b: [1, 2] })).not.toBe(canonicalJson({ b: [2, 1] }));
    expect(canonicalJson({ n: null })).not.toBe(canonicalJson({}));
  });
});

describe('#312 · the audit accounting', () => {
  it('names exactly what is owed and missing, in order, once', () => {
    expect(missingAuditTargets(['a', 'b', 'c'], ['b'])).toEqual(['a', 'c']);
    expect(missingAuditTargets(['a', 'b'], ['a', 'b', 'b'])).toEqual([]);
    expect(missingAuditTargets(['a', 'a'], [])).toEqual(['a']);
  });

  it('⚠️ an empty present set means EVERYTHING is owed, never nothing', () => {
    expect(missingAuditTargets(['a', 'b'], [])).toEqual(['a', 'b']);
  });
});

describe('#312 · the arguments', () => {
  const OK = [
    '--compiled-version', VERSION,
    '--expect-fields', '53',
    '--expect-certified', '43',
    '--expect-confirm', '10',
  ];

  it('parses the declared invocation, dry run by default', () => {
    expect(parseConfirmArgs(OK)).toEqual({
      ok: true,
      args: {
        compiledVersion: VERSION,
        expectFields: 53,
        expectCertified: 43,
        expectConfirm: 10,
        commit: false,
      },
    });
    const c = parseConfirmArgs([...OK, '--commit']);
    expect(c.ok && c.args.commit).toBe(true);
  });

  it('⚠️ the deleted recovery door is REFUSED, not silently ignored', () => {
    // Round two proved `--reissue-audit` could attest a #311(d) confirmation the
    // act never performed. It is gone; a caller who half-remembers it is told.
    const r = parseConfirmArgs([...OK, '--reissue-audit', '--commit']);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('unknown argument');
  });

  it.each([
    [['--compiled-version', VERSION, '--expect-fields', '53', '--expect-certified', '43'], 'missing'],
    [[...OK.slice(0, 2), '--expect-fields', '53x', ...OK.slice(4)], 'plain integer'],
    [['--compiled-version', 'd2120cdd', ...OK.slice(2)], 'full uuid'],
    [[...OK, '--expect-fields', '53'], 'twice'],
    [[...OK, '--commit', '--commit'], 'twice'],
    [[...OK, '--force'], 'unknown'],
    [['--compiled-version', VERSION, '--expect-fields', '0', '--expect-certified', '0', '--expect-confirm', '0'], 'vacuously'],
    [['--compiled-version', VERSION, '--expect-fields', '53', '--expect-certified', '43', '--expect-confirm', '9'], 'must equal'],
    [['--compiled-version', '--expect-fields', '53'], 'needs a value'],
  ])('refuses %j (%s)', (argv, why) => {
    const r = parseConfirmArgs(argv);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain(why);
  });
});
