// ============================================================================
// TEST SUPPORT — the frozen pre-ADMIN-3 imaging rule and the input universe
// the report-kind oracles run it over. Imported ONLY by tests:
//   - packages/shared/src/specialties-report-kind-oracle.test.ts
//   - apps/transcribe-md/src/worker/note-templates/__tests__/
//       gate-admin3-imaging-report-builders.test.ts
//   - apps/transcribe-md/src/worker/layers/__tests__/
//       gate-admin3-l4-route-oracle.test.ts
// One universe, shared by import, so the three oracles cannot quietly test
// different sets of inputs.
//
// ⚠️ THE `frozen` BODIES ARE VERBATIM COPIES of packages/shared/src/
// specialties.ts at origin/main 6fcd21d0 — before the rule became catalog
// data. They are the ORACLE: never "fix" them to match the new code. If the
// product is ever meant to answer differently, that is a new ruling and a new
// oracle, not an edit here.
// ============================================================================

import {
  LEGACY_SPECIALTY_KEYS,
  SPECIALTIES,
  SPECIALTIES_FOR_VISIT_CREATE,
  type Specialty,
} from '../specialties';

export const ULTRASOUND_FLAG = 'NEXT_PUBLIC_ULTRASOUND_SPECIALTY';

export const frozen = {
  /** 6fcd21d0 `ultrasoundSpecialtyEnabled` */
  flag(): boolean {
    return process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY === 'true';
  },
  /** 6fcd21d0 `isImagingReportSpecialty` */
  isImaging(id: string | null | undefined): boolean {
    return id === 'ultrasound';
  },
  /** 6fcd21d0 `emAppliesToSpecialty` */
  emApplies(id: string | null | undefined): boolean {
    return !(frozen.flag() && frozen.isImaging(id));
  },
  /** 6fcd21d0 `visibleSpecialties` */
  visible(opts?: { forVisitCreate?: boolean }): readonly Specialty[] {
    const usOn = frozen.flag();
    return (opts?.forVisitCreate ? SPECIALTIES_FOR_VISIT_CREATE : SPECIALTIES).filter(
      (s) => (s.id === 'ultrasound' ? usOn : true)
    );
  },
};

/** Flag values, not just on/off: only the exact string 'true' turns it on,
 *  and a near-miss must stay off in both implementations. `undefined` = unset. */
export const FLAG_STATES: readonly (string | undefined)[] = [
  undefined,
  'true',
  'false',
  '',
  'TRUE',
  'True',
  '1',
  'yes',
  'on',
  ' true',
  'true ',
];

const ORIGINAL_FLAG = process.env[ULTRASOUND_FLAG];

export function setUltrasoundFlag(value: string | undefined): void {
  if (value === undefined) delete process.env[ULTRASOUND_FLAG];
  else process.env[ULTRASOUND_FLAG] = value;
}

export function restoreUltrasoundFlag(): void {
  setUltrasoundFlag(ORIGINAL_FLAG);
}

const ADVERSARIAL_STRINGS: readonly string[] = [
  '',
  ' ',
  'Ultrasound',
  'ULTRASOUND',
  ' ultrasound',
  'ultrasound ',
  '\tultrasound',
  'ultrasound\n',
  'ultra sound',
  'ultra-sound',
  'ultrasounds',
  'ultrasoun',
  'ultrasound-report',
  'tmpl_ultrasound_report',
  'imaging',
  'office',
  'generic',
  'x-ray',
  'xray',
  'ct',
  'undefined',
  'null',
  // Prototype keys — a lookup-object implementation answers these wrongly.
  'toString',
  '__proto__',
  'constructor',
  'hasOwnProperty',
  'valueOf',
];

const dedupe = <T,>(xs: readonly T[]): T[] => [...new Set(xs)];

/** Every STRING input: DERIVED from the live catalog and legacy map (ids,
 *  labels, templateIds, case/whitespace variants of every id, every legacy
 *  key) plus the adversarial list. Deriving it means a new catalog row or
 *  legacy key joins the oracle without anyone editing this file. */
export const STRING_UNIVERSE: readonly string[] = dedupe([
  ...SPECIALTIES.map((s) => s.id),
  ...SPECIALTIES.map((s) => s.label),
  ...SPECIALTIES.map((s) => s.templateId),
  ...SPECIALTIES.flatMap((s) => [
    s.id.toUpperCase(),
    s.id[0]!.toUpperCase() + s.id.slice(1),
    ` ${s.id}`,
    `${s.id} `,
  ]),
  ...LEGACY_SPECIALTY_KEYS,
  ...ADVERSARIAL_STRINGS,
]);

/** Inputs the type forbids but a runtime can still deliver (an untyped prisma
 *  row, a cast). Both implementations use strict equality, so all are false. */
export const NON_STRING_INPUTS = [
  null,
  undefined,
  0,
  1,
  Number.NaN,
  true,
  false,
  {},
  [],
  ['ultrasound'],
  { id: 'ultrasound' },
  new String('ultrasound'),
  { toString: () => 'ultrasound' },
] as unknown as readonly (string | null | undefined)[];

export const FULL_UNIVERSE: readonly (string | null | undefined)[] = [
  ...STRING_UNIVERSE,
  ...NON_STRING_INPUTS,
];

export function show(u: unknown): string {
  if (u === undefined) return 'undefined';
  if (typeof u === 'number' && Number.isNaN(u)) return 'NaN';
  if (u instanceof String) return `String(${JSON.stringify(String(u))})`;
  try {
    return JSON.stringify(u) ?? String(u);
  } catch {
    return String(u);
  }
}
