// ============================================================================
// THE CONFIRM — ruling #311(d), carrying the decisions of #312. Pure.
// ----------------------------------------------------------------------------
// The re-issue act left compiled version `d2120cdd` with 43 rows CERTIFIED by
// transfer and 10 re-proposed. #311(d) authorises confirming them on the
// owner's behalf; #312 records, per row, WHAT they are confirmed as. This module
// turns those decisions into the one payload the writer accepts, and refuses
// anything that does not match the state the decisions were made against.
//
// ⚠️ THE DECISIONS ARE KEYED BY `fieldId` AND PINNED TO ONE COMPILED VERSION,
// ON PURPOSE. A table matched by LABEL would confirm whatever re-proposal sits
// under "Patient" on the next re-issue — a decision made about one proposal
// silently applied to another. `fieldId` is salted with the package sha, so a
// different form mints different ids and every decision here misses, loudly.
//
// ⚠️ EACH DECISION PINS THE WHOLE PROPOSAL IT WAS MADE AGAINST — EVERY
// ATTRIBUTE, NOT A CHOSEN FEW. The first draft compared seven, and the
// refutation pass certified an edited Marital row carrying `blankPolicy:
// requires_input` and `approvedSynonyms: ["Single"]` under #311(d): values
// nobody judged. The comparison is now of the WHOLE object the writer's reader
// returns, so an attribute this file has never heard of — a column added next
// month — is a drift and refuses, rather than being waved through by a list.
//
// The draft is editable in the doctor's panel; if anyone changes a row between
// the judgement and the act, the act is no longer confirming what was decided,
// so it REFUSES rather than overwriting the edit.
//
// ⚠️ WHAT THIS DOES NOT DO. It changes no attribute the decision does not name,
// and the 43 transferred rows are passed by reference. The writer
// (`updateTemplateTwinMappings`) requires the FULL field set, so "confirm the
// ten" always means "send all 53, ten of them changed".
//
//   PROOF: __tests__/gate-312-confirm-plan.test.ts
// ============================================================================
import type { SemanticMapping } from './ir';

type SourceType = SemanticMapping['sourceType'];

/** A mapping as `fromPersistedMapping` returns it, without its address. */
export type JudgedMapping = Omit<SemanticMapping, 'fieldId'>;

export interface ConfirmDecision {
  readonly fieldId: string;
  readonly displayOrder: number;
  readonly label: string;
  /** The WHOLE proposal as judged — the act refuses unless the row still says exactly this. */
  readonly judged: JudgedMapping;
  readonly confirmAs: {
    readonly sourceType: SourceType;
    readonly clinicalConcept: string | null;
  };
  readonly why: string;
}

export interface ConfirmTable {
  readonly compiledVersionId: string;
  readonly ruling: string;
  /**
   * `templateTwinMappingsSha256` over ALL 53 rows as judged — the ten AND the
   * 43. The per-decision comparison pins the ten; this pins the set, so a drift
   * in a transferred row refuses too. Checked by the door against the rows it
   * reads (the planner's tests build synthetic rows, which no real sha matches).
   */
  readonly judgedSetSha256: string;
  readonly decisions: readonly ConfirmDecision[];
}

/** The actor named in every audit row this door writes — #311(d). */
export const CONFIRMING_ACTOR = 'ruling #311(d)';

const asProposed = (d: Omit<ConfirmDecision, 'confirmAs'>): ConfirmDecision => ({
  ...d,
  confirmAs: { sourceType: d.judged.sourceType, clinicalConcept: d.judged.clinicalConcept },
});

// Shared attribute blocks, read off the production rows of d2120cdd (the
// proposals as the re-issue act left them, 2026-09-09T15:42:32Z).
const PSH: JudgedMapping = {
  sourceType: 'extraction',
  clinicalConcept: 'past_surgical_history',
  expectedDataType: 'text',
  polarityBehavior: 'affirmative_only',
  temporality: 'historical',
  laterality: 'not_applicable',
  unitPolicy: 'forbidden',
  approvedSynonyms: ['PSH', 'Surgical History', 'Prior Surgeries', 'Operative History'],
  required: false,
  blankPolicy: 'blank',
  unknownPolicy: 'blank',
  practiceDefault: null,
  status: 'recognized',
};

const TOTAL_TIME = (approvedSynonyms: string[]): JudgedMapping => ({
  sourceType: 'extraction',
  clinicalConcept: 'total_time_minutes',
  expectedDataType: 'text',
  polarityBehavior: 'value_only',
  temporality: 'current',
  laterality: 'not_applicable',
  unitPolicy: 'optional',
  approvedSynonyms,
  required: false,
  blankPolicy: 'blank',
  unknownPolicy: 'blank',
  practiceDefault: null,
  status: 'recognized',
});

/**
 * #312 — the ten, by name. Nine as proposed; Telehealth consent to `manual`.
 *
 * ⚠️ #261: a row that prints a patient's name is never certified below the
 * fold. Patient and Age are here INDIVIDUALLY, each with its own reason, and
 * the audit writes one row per field — ten named confirmations, not a bulk one.
 */
export const RULING_312: ConfirmTable = {
  compiledVersionId: 'd2120cdd-74ae-43a3-85a3-1f185401e202',
  ruling: '#312',
  // Measured over the production rows, read-only, 2026-09-10; every one of the
  // ten decided rows still carried its re-issue timestamp (updatedAt = createdAt).
  judgedSetSha256: 'dd4dc3784b5c4baa3581983d03001a2311758cd8953e94429488418b03da05ad',
  decisions: [
    asProposed({
      fieldId: 'ttf_2f84538cad1878c2100fe836',
      displayOrder: 1,
      label: 'Referring MD',
      judged: {
        sourceType: 'extraction',
        clinicalConcept: 'visit_metadata.referring_physician',
        expectedDataType: 'text',
        polarityBehavior: 'value_only',
        temporality: 'current',
        laterality: 'not_applicable',
        unitPolicy: 'forbidden',
        approvedSynonyms: ['Referring Physician', 'Referring Doctor', 'Referring Provider', 'Ref MD', 'Referring Clinician'],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'recognized',
      },
      why: '#247 family 3: the referrer is DICTATED (encounter_evidence); acceptance row 7',
    }),
    asProposed({
      fieldId: 'ttf_e59e5a33c5975f8b3744dc2f',
      displayOrder: 2,
      label: 'Patient',
      judged: {
        sourceType: 'visit_metadata',
        clinicalConcept: 'visit_metadata.patient_name',
        expectedDataType: 'text',
        polarityBehavior: 'value_only',
        temporality: 'current',
        laterality: 'not_applicable',
        unitPolicy: 'forbidden',
        approvedSynonyms: ['Patient Name', 'Pt Name', 'Name'],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'recognized',
      },
      why: '#247: read off the record (visit_record); #311(d) names these rows; acceptance rows 3 and 7',
    }),
    asProposed({
      fieldId: 'ttf_73ef2a9a25aa550b8ad8e170',
      displayOrder: 3,
      label: 'Age',
      judged: {
        sourceType: 'visit_metadata',
        clinicalConcept: 'visit_metadata.patient_age',
        expectedDataType: 'number',
        polarityBehavior: 'value_only',
        temporality: 'current',
        laterality: 'not_applicable',
        unitPolicy: 'optional',
        approvedSynonyms: ['Patient Age', 'Pt Age', 'Age (years)'],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'recognized',
      },
      why: "#247: computed from the record's DOB; acceptance rows 3 and 7",
    }),
    asProposed({
      fieldId: 'ttf_ec2796a89b78ab1fb6f2b889',
      displayOrder: 22,
      label: 'Past Surgical History',
      judged: PSH,
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_4aa48c04debc2ccaf754f748',
      displayOrder: 23,
      label: 'Past Surgical History',
      judged: PSH,
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_029a5da0672909e0b2677ecf',
      displayOrder: 24,
      label: 'Past Surgical History',
      judged: PSH,
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_e00de0347ab744580475c023',
      displayOrder: 36,
      label: 'Marital status',
      judged: {
        sourceType: 'extraction',
        clinicalConcept: 'social_history.marital_status',
        expectedDataType: 'text',
        polarityBehavior: 'value_only',
        temporality: 'current',
        laterality: 'not_applicable',
        unitPolicy: 'not_applicable',
        approvedSynonyms: ['Marital status', 'Relationship status', 'Civil status'],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'recognized',
      },
      why: '#246 family 2: a social_history sub-concept; acceptance row 9',
    }),
    {
      fieldId: 'ttf_86cf11d77e63d9e64a6b045b',
      displayOrder: 56,
      label: 'Telehealth consent',
      judged: {
        sourceType: 'extraction',
        clinicalConcept: null,
        expectedDataType: 'text',
        polarityBehavior: 'affirmative_only',
        temporality: 'current',
        laterality: 'not_applicable',
        unitPolicy: 'not_applicable',
        approvedSynonyms: [],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'needs_confirmation',
      },
      confirmAs: { sourceType: 'manual', clinicalConcept: null },
      why:
        '#312: no registered concept exists and manual+omit is unwritable (manual_source_not_filled), ' +
        'so manual: the machine never prints it (the gap that nobody can yet insert it is filed)',
    },
    asProposed({
      fieldId: 'ttf_e2bdb95b03283f39388ca07b',
      displayOrder: 70,
      label: 'Total minutes spent with patient',
      judged: TOTAL_TIME(['Total minutes with patient', 'Time spent with patient', 'Visit duration', 'Total visit time']),
      why: '#246 family 4: the total is SAID, never computed; acceptance row 8; grounded by the total-time guard',
    }),
    asProposed({
      fieldId: 'ttf_ef6e199276f1691e18cf84d8',
      displayOrder: 71,
      label: 'Total time minutes',
      judged: TOTAL_TIME(['Total time in minutes', 'Visit duration minutes', 'Total encounter time', 'Minutes spent']),
      why: "#246 family 4 and #191's one datum, two renders; acceptance row 8; grounded by the total-time guard",
    }),
  ],
};

export interface ConfirmField {
  fieldId: string;
  displayOrder: number;
  originalLabel: string;
  mapping: SemanticMapping;
}

export interface ConfirmExpect {
  fields: number;
  alreadyCertified: number;
  confirm: number;
}

export type Guard = readonly [name: string, got: unknown, want: unknown];

export interface ConfirmMove {
  fieldId: string;
  displayOrder: number;
  label: string;
  from: { sourceType: SourceType; clinicalConcept: string | null; status: SemanticMapping['status'] };
  to: { sourceType: SourceType; clinicalConcept: string | null; status: 'certified' };
}

export type ConfirmPlan =
  | { ok: true; guards: Guard[]; payload: SemanticMapping[]; moves: ConfirmMove[] }
  | { ok: false; guards: Guard[]; failed: string[] };

export function countFailedGuards(guards: readonly Guard[]): number {
  return guards.filter(([, got, want]) => JSON.stringify(got) !== JSON.stringify(want)).length;
}

function failedNames(guards: readonly Guard[]): string[] {
  return guards
    .filter(([, got, want]) => JSON.stringify(got) !== JSON.stringify(want))
    .map(([name]) => name);
}

/**
 * Stable JSON: object keys sorted at every depth, `undefined` dropped. Array
 * order is kept — a reordered synonym list is a different proposal.
 */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(value, (_key, v: unknown) =>
    v !== null && typeof v === 'object' && !Array.isArray(v)
      ? Object.fromEntries(
          Object.keys(v as Record<string, unknown>)
            .sort()
            .map((k) => [k, (v as Record<string, unknown>)[k]]),
        )
      : v,
  );
}

/** The mapping without its address — every other key, whatever keys exist. */
export function withoutAddress(mapping: SemanticMapping): JudgedMapping {
  const { fieldId: _fieldId, ...rest } = mapping;
  return rest;
}

/** True when the row still carries EXACTLY the proposal the decision was made against. */
function stillAsJudged(field: ConfirmField, d: ConfirmDecision): boolean {
  return (
    field.originalLabel === d.label &&
    field.displayOrder === d.displayOrder &&
    canonicalJson(withoutAddress(field.mapping)) === canonicalJson(d.judged)
  );
}

/**
 * Build the full-set payload for `updateTemplateTwinMappings`, or refuse.
 *
 * Every guard is computed on every call, and a refusal carries all of them,
 * so an operator sees every disagreement at once rather than one per run.
 */
export function planConfirmation(input: {
  compiledVersionId: string;
  fields: readonly ConfirmField[];
  table: ConfirmTable;
  expect: ConfirmExpect;
}): ConfirmPlan {
  const { compiledVersionId, fields, table, expect } = input;
  const decisionById = new Map(table.decisions.map((d) => [d.fieldId, d]));
  const fieldIds = new Set(fields.map((f) => f.fieldId));

  const missing = table.decisions.filter((d) => !fieldIds.has(d.fieldId)).length;
  const certifiedBefore = fields.filter((f) => f.mapping.status === 'certified').length;
  const certifiedDecided = fields.filter(
    (f) => decisionById.has(f.fieldId) && f.mapping.status === 'certified',
  ).length;
  const undecidedUncertified = fields.filter(
    (f) => !decisionById.has(f.fieldId) && f.mapping.status !== 'certified',
  ).length;
  const drifted = fields.filter((f) => {
    const d = decisionById.get(f.fieldId);
    return d !== undefined && !stillAsJudged(f, d);
  }).length;
  const mappingIdMismatch = fields.filter((f) => f.mapping.fieldId !== f.fieldId).length;
  const judgedCertified = table.decisions.filter((d) => d.judged.status === 'certified').length;
  const manualWithConcept = table.decisions.filter(
    (d) => d.confirmAs.sourceType === 'manual' && d.confirmAs.clinicalConcept !== null,
  ).length;
  const conceptlessNonManual = table.decisions.filter(
    (d) => d.confirmAs.sourceType !== 'manual' && !d.confirmAs.clinicalConcept,
  ).length;

  const guards: Guard[] = [
    ['the table is for THIS compiled version', compiledVersionId, table.compiledVersionId],
    // ⚠️ NON-VACUITY FIRST. Every count below reads `0 === 0` on an empty set.
    ['the field set is non-empty', fields.length > 0, true],
    ['fields on the version', fields.length, expect.fields],
    ['fields sharing a fieldId', fields.length - fieldIds.size, 0],
    ['mappings addressed to a different field', mappingIdMismatch, 0],
    ['decisions in the table', table.decisions.length, expect.confirm],
    ['decisions sharing a fieldId', table.decisions.length - decisionById.size, 0],
    ['decisions naming a field NOT on this version', missing, 0],
    ['decisions judged against an already-CERTIFIED proposal', judgedCertified, 0],
    ['fields CERTIFIED before the act', certifiedBefore, expect.alreadyCertified],
    ['decided fields that are ALREADY certified', certifiedDecided, 0],
    ['undecided fields that are NOT certified', undecidedUncertified, 0],
    ['decided fields whose proposal DRIFTED from the judged one', drifted, 0],
    ['manual confirmations carrying a concept', manualWithConcept, 0],
    ['non-manual confirmations carrying NO concept', conceptlessNonManual, 0],
  ];

  if (countFailedGuards(guards) > 0) {
    return { ok: false, guards, failed: failedNames(guards) };
  }

  const moves: ConfirmMove[] = [];
  const payload = fields.map((f): SemanticMapping => {
    const d = decisionById.get(f.fieldId);
    // Not decided: the row the writer already holds, BY REFERENCE, so nothing
    // about a transferred disposition can be changed here even by accident.
    if (!d) return f.mapping;
    const next: SemanticMapping = {
      ...f.mapping,
      sourceType: d.confirmAs.sourceType,
      clinicalConcept: d.confirmAs.clinicalConcept,
      status: 'certified',
    };
    moves.push({
      fieldId: f.fieldId,
      displayOrder: f.displayOrder,
      label: f.originalLabel,
      from: {
        sourceType: f.mapping.sourceType,
        clinicalConcept: f.mapping.clinicalConcept,
        status: f.mapping.status,
      },
      to: { sourceType: next.sourceType, clinicalConcept: next.clinicalConcept, status: 'certified' },
    });
    return next;
  });

  return { ok: true, guards, payload, moves };
}

/**
 * The audit targets this door owes and has not written, in the order owed.
 *
 * ⚠️ WHY THIS EXISTS: `logAudit` NEVER THROWS. A failed insert is a line on
 * stderr, so the door reads its rows back and refuses — exit 1 — on any
 * shortfall. It does NOT re-issue: a recovery that cannot tell whose hands
 * confirmed a row is a false-record generator (round two).
 */
export function missingAuditTargets(
  expected: readonly string[],
  present: readonly string[],
): string[] {
  const have = new Set(present);
  const out: string[] = [];
  for (const id of expected) if (!have.has(id) && !out.includes(id)) out.push(id);
  return out;
}

// ── ARGUMENTS ────────────────────────────────────────────────────────────────

export interface ConfirmArgs {
  compiledVersion: string;
  expectFields: number;
  expectCertified: number;
  expectConfirm: number;
  commit: boolean;
}

export type ConfirmArgsResult = { ok: true; args: ConfirmArgs } | { ok: false; reason: string };

const USAGE =
  'usage: confirm-reissued-form.ts --compiled-version <uuid> --expect-fields <n> ' +
  '--expect-certified <n> --expect-confirm <n> [--commit]';

const VALUED = ['compiled-version', 'expect-fields', 'expect-certified', 'expect-confirm'];
// ⚠️ ONE FLAG. A `--reissue-audit` recovery door existed for one commit and
// round two proved it could attest a confirmation it never performed; it is
// deleted, and an unknown flag is refused, so it cannot be half-remembered.
const FLAGS = ['commit'];

/**
 * Every valued argument is REQUIRED and nothing is defaulted: a default is a
 * value nobody declared, and the declaration names each of these numbers so the
 * transcript can be compared against it.
 */
export function parseConfirmArgs(argv: readonly string[]): ConfirmArgsResult {
  const values = new Map<string, string>();
  const flags = new Set<string>();
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i]!;
    const name = a.startsWith('--') ? a.slice(2) : null;
    if (name && FLAGS.includes(name)) {
      if (flags.has(name)) return { ok: false, reason: `--${name} given twice` };
      flags.add(name);
      continue;
    }
    if (!name || !VALUED.includes(name)) return { ok: false, reason: `unknown argument '${a}'. ${USAGE}` };
    if (values.has(name)) return { ok: false, reason: `--${name} given twice` };
    const v = argv[i + 1];
    if (v === undefined || v.startsWith('--') || v.trim() === '') {
      return { ok: false, reason: `--${name} needs a value` };
    }
    values.set(name, v);
    i += 1;
  }
  for (const name of VALUED) {
    if (!values.has(name)) return { ok: false, reason: `missing required --${name}. ${USAGE}` };
  }
  const compiledVersion = values.get('compiled-version')!;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(compiledVersion)) {
    return { ok: false, reason: `--compiled-version must be a full uuid, got '${compiledVersion}'` };
  }
  const int = (name: string): number | string => {
    const raw = values.get(name)!;
    // ⚠️ STRICT — `parseInt('53x')` is 53.
    return /^\d+$/.test(raw) ? Number(raw) : `--${name} must be a plain integer, got '${raw}'`;
  };
  const fieldsN = int('expect-fields');
  const certifiedN = int('expect-certified');
  const confirmN = int('expect-confirm');
  for (const n of [fieldsN, certifiedN, confirmN]) if (typeof n === 'string') return { ok: false, reason: n };
  const f = fieldsN as number;
  const c = certifiedN as number;
  const k = confirmN as number;
  if (f === 0) return { ok: false, reason: '--expect-fields 0 would pass every count vacuously' };
  if (k === 0) return { ok: false, reason: '--expect-confirm 0 confirms nothing' };
  // The confirm COMPLETES the version: certification needs every field
  // certified, so the declared counts must cover the whole field set.
  if (c + k !== f) {
    return {
      ok: false,
      reason: `--expect-certified ${c} + --expect-confirm ${k} must equal --expect-fields ${f}`,
    };
  }
  return {
    ok: true,
    args: {
      compiledVersion,
      expectFields: f,
      expectCertified: c,
      expectConfirm: k,
      commit: flags.has('commit'),
    },
  };
}
