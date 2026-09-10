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
// ⚠️ AND EACH DECISION CARRIES THE PROPOSAL IT WAS MADE AGAINST. The draft is
// editable in the doctor's panel; if anyone changes a row between the judgement
// and the act, the act is no longer confirming what was decided. So a drifted
// proposal REFUSES the whole act rather than overwriting the edit — the doctor's
// own change is never silently replaced by a machine confirm.
//
// ⚠️ WHAT THIS DOES NOT DO. It changes no attribute the decision does not name:
// every other column comes through `fromPersistedMapping` (the WRITER's own
// reader) untouched, and the 43 transferred rows are passed by reference. The
// writer (`updateTemplateTwinMappings`) requires the FULL field set, so "confirm
// the ten" always means "send all 53, ten of them changed".
//
//   PROOF: __tests__/gate-312-confirm-plan.test.ts
// ============================================================================
import type { SemanticMapping } from './ir';

type Status = SemanticMapping['status'];
type SourceType = SemanticMapping['sourceType'];

export interface ConfirmDecision {
  readonly fieldId: string;
  readonly displayOrder: number;
  readonly label: string;
  /** The proposal as JUDGED — the act refuses unless the row still says this. */
  readonly proposed: {
    readonly sourceType: SourceType;
    readonly clinicalConcept: string | null;
    readonly status: Status;
  };
  readonly confirmAs: {
    readonly sourceType: SourceType;
    readonly clinicalConcept: string | null;
  };
  readonly why: string;
}

export interface ConfirmTable {
  readonly compiledVersionId: string;
  readonly ruling: string;
  readonly decisions: readonly ConfirmDecision[];
}

const asProposed = (d: Omit<ConfirmDecision, 'confirmAs'>): ConfirmDecision => ({
  ...d,
  confirmAs: { sourceType: d.proposed.sourceType, clinicalConcept: d.proposed.clinicalConcept },
});

/**
 * #312 — the ten, by name. Nine as proposed; Telehealth consent to `manual`.
 *
 * ⚠️ #261: a row that prints a patient's name is never certified below the
 * fold. Patient and Age are here INDIVIDUALLY, each with its own reason, and
 * the audit writes one row per field — this is ten named confirmations, not a
 * bulk one.
 */
export const RULING_312: ConfirmTable = {
  compiledVersionId: 'd2120cdd-74ae-43a3-85a3-1f185401e202',
  ruling: '#312',
  decisions: [
    asProposed({
      fieldId: 'ttf_2f84538cad1878c2100fe836',
      displayOrder: 1,
      label: 'Referring MD',
      proposed: { sourceType: 'extraction', clinicalConcept: 'visit_metadata.referring_physician', status: 'recognized' },
      why: '#247 family 3: the referrer is DICTATED (encounter_evidence); acceptance row 7',
    }),
    asProposed({
      fieldId: 'ttf_e59e5a33c5975f8b3744dc2f',
      displayOrder: 2,
      label: 'Patient',
      proposed: { sourceType: 'visit_metadata', clinicalConcept: 'visit_metadata.patient_name', status: 'recognized' },
      why: '#247: read off the record (visit_record); #311(d) names these rows; acceptance rows 3 and 7',
    }),
    asProposed({
      fieldId: 'ttf_73ef2a9a25aa550b8ad8e170',
      displayOrder: 3,
      label: 'Age',
      proposed: { sourceType: 'visit_metadata', clinicalConcept: 'visit_metadata.patient_age', status: 'recognized' },
      why: "#247: computed from the record's DOB; acceptance rows 3 and 7",
    }),
    asProposed({
      fieldId: 'ttf_ec2796a89b78ab1fb6f2b889',
      displayOrder: 22,
      label: 'Past Surgical History',
      proposed: { sourceType: 'extraction', clinicalConcept: 'past_surgical_history', status: 'recognized' },
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_4aa48c04debc2ccaf754f748',
      displayOrder: 23,
      label: 'Past Surgical History',
      proposed: { sourceType: 'extraction', clinicalConcept: 'past_surgical_history', status: 'recognized' },
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_029a5da0672909e0b2677ecf',
      displayOrder: 24,
      label: 'Past Surgical History',
      proposed: { sourceType: 'extraction', clinicalConcept: 'past_surgical_history', status: 'recognized' },
      why: '#246 family 1: its own concept; acceptance row 2',
    }),
    asProposed({
      fieldId: 'ttf_e00de0347ab744580475c023',
      displayOrder: 36,
      label: 'Marital status',
      proposed: { sourceType: 'extraction', clinicalConcept: 'social_history.marital_status', status: 'recognized' },
      why: '#246 family 2: a social_history sub-concept; acceptance row 9',
    }),
    {
      fieldId: 'ttf_86cf11d77e63d9e64a6b045b',
      displayOrder: 56,
      label: 'Telehealth consent',
      proposed: { sourceType: 'extraction', clinicalConcept: null, status: 'needs_confirmation' },
      confirmAs: { sourceType: 'manual', clinicalConcept: null },
      why:
        '#312: no registered concept exists and manual+omit is unwritable (manual_source_not_filled), ' +
        'so manual: the machine never prints it, the doctor attests it at review',
    },
    asProposed({
      fieldId: 'ttf_e2bdb95b03283f39388ca07b',
      displayOrder: 70,
      label: 'Total minutes spent with patient',
      proposed: { sourceType: 'extraction', clinicalConcept: 'total_time_minutes', status: 'recognized' },
      why: '#246 family 4: the total is SAID, never computed; acceptance row 8',
    }),
    asProposed({
      fieldId: 'ttf_ef6e199276f1691e18cf84d8',
      displayOrder: 71,
      label: 'Total time minutes',
      proposed: { sourceType: 'extraction', clinicalConcept: 'total_time_minutes', status: 'recognized' },
      why: "#246 family 4 and #191's one datum, two renders; acceptance row 8",
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
  from: { sourceType: SourceType; clinicalConcept: string | null; status: Status };
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

/** True when the row still carries exactly the proposal the decision was made against. */
function stillAsJudged(field: ConfirmField, d: ConfirmDecision): boolean {
  const m = field.mapping;
  return (
    field.originalLabel === d.label &&
    field.displayOrder === d.displayOrder &&
    m.sourceType === d.proposed.sourceType &&
    m.clinicalConcept === d.proposed.clinicalConcept &&
    m.status === d.proposed.status &&
    // The judged proposals carried no policy. A policy that appeared since is
    // somebody's edit, and `manual` + `omit` is refused by the writer anyway.
    (m.unmentionedPolicy ?? null) === null &&
    m.practiceDefault === null
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

/**
 * Every argument is REQUIRED and nothing is defaulted: a default is a value
 * nobody declared, and the declaration names each of these numbers so the
 * transcript can be compared against it.
 */
export function parseConfirmArgs(argv: readonly string[]): ConfirmArgsResult {
  const values = new Map<string, string>();
  let commit = false;
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i]!;
    if (a === '--commit') {
      commit = true;
      continue;
    }
    const name = a.startsWith('--') ? a.slice(2) : null;
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
    args: { compiledVersion, expectFields: f, expectCertified: c, expectConfirm: k, commit },
  };
}
