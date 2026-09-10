// ============================================================================
// IMAGING-REPORT BUILDERS, KEYED BY THE CATALOG ROW'S OWN NAME
// (ADMIN-3 PR-1, ruling #197)
// ----------------------------------------------------------------------------
// An imaging-report specialty used to be the literal `id === 'ultrasound'`,
// and everything downstream of it was ultrasound-shaped: L4 always bound
// ULTRASOUND_REPORT_TEMPLATE + buildUltrasoundSystemPrompt, and the worker
// always ran the venous-duplex `reconcileMeasurementTables` rebuild. Once the
// imaging rule became catalog DATA (`reportKind: 'imaging'`), a second imaging
// row — x-ray, CT — would have inherited all three SILENTLY: an x-ray report
// written from the ultrasound prompt, with vein tables rebuilt into it.
//
// So every 'imaging' row names a `reportBuilder`, and the two consumers look
// the builder up BY THAT NAME here:
//   - L4 (worker/layers/04-generate-soap.ts): the fallback template and the
//     system-prompt builder;
//   - the worker (worker.ts, after L6): the deterministic final-note pass.
//
// ⚠️ FAIL CLOSED. An imaging row whose name is missing, or not registered
// here, THROWS — it never falls back to another imaging type's builder. The
// visit fails loudly instead of producing a report from the wrong prompt.
// `tsc` already refuses such a row (the catalog `satisfies` a discriminated
// union, and this registry is a mapped type over every declared name); the
// throw is for the runtime, where vitest and a hand-edited build do not
// type-check. Pinned by gate-admin3-imaging-report-builders.test.ts.
//
// ⚠️ BYTE-IDENTICAL FOR ULTRASOUND. The entry below hands back the SAME
// template object and calls the SAME two functions the call sites used to
// bind directly; the wrappers resolve the live ESM binding at call time, so a
// test that mocks either module still reaches its mock.
// ============================================================================

import {
  SPECIALTIES,
  isImagingReportSpecialty,
  type ImagingReportBuilderName,
} from '@meddoc/shared/specialties';
import type { BuildSystemPromptOpts, ResolvedNoteTemplate } from './build-soap-prompt';
import { buildUltrasoundSystemPrompt } from './build-ultrasound-prompt';
import { reconcileMeasurementTables } from './reconcile-measurement-tables';
import { ULTRASOUND_REPORT_TEMPLATE } from './ultrasound-report-template';

export interface ImagingReportBuilder {
  /** L4's template when the doctor has no custom (non-system-default) one. */
  readonly defaultTemplate: ResolvedNoteTemplate;
  /** L4's system-prompt builder for this report type. */
  readonly buildSystemPrompt: (
    template: ResolvedNoteTemplate,
    opts: BuildSystemPromptOpts
  ) => string;
  /** The worker's deterministic pass over the polished note, before fan-out.
   *  REQUIRED, so a new imaging type must decide it explicitly — an identity
   *  function is a legitimate answer; inheriting the vein-table rebuild is not. */
  readonly reconcileFinalNote: (note: string) => string;
}

/** A mapped type over EVERY declared builder name: declaring a name in
 *  `IMAGING_REPORT_BUILDERS` without implementing it here fails `tsc`. */
export const IMAGING_REPORT_BUILDER_REGISTRY: {
  readonly [K in ImagingReportBuilderName]: ImagingReportBuilder;
} = Object.freeze({
  ultrasound: Object.freeze({
    defaultTemplate: ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate,
    buildSystemPrompt: (template: ResolvedNoteTemplate, opts: BuildSystemPromptOpts) =>
      buildUltrasoundSystemPrompt(template, opts),
    reconcileFinalNote: (note: string) => reconcileMeasurementTables(note),
  }),
});

/** The builder an imaging catalog row names. THROWS when the row is not an
 *  imaging row, names nothing, or names something this registry does not own
 *  (own-property check: a name like 'toString' must not resolve to
 *  Object.prototype). Exported so the gate can drive it with rows the real
 *  catalog does not contain. */
export function resolveImagingReportBuilder(row: {
  readonly id: string;
  readonly reportKind: string;
  readonly reportBuilder?: unknown;
}): ImagingReportBuilder {
  const name = row.reportBuilder;
  if (
    row.reportKind !== 'imaging' ||
    typeof name !== 'string' ||
    !Object.prototype.hasOwnProperty.call(IMAGING_REPORT_BUILDER_REGISTRY, name)
  ) {
    throw new Error(
      `[imaging-report-builders] specialty "${row.id}" (reportKind ` +
        `"${row.reportKind}") names no registered imaging report builder ` +
        `(reportBuilder: ${JSON.stringify(name ?? null)}). Refusing to fall back ` +
        `to another imaging type's template, prompt or table rebuild.`
    );
  }
  return IMAGING_REPORT_BUILDER_REGISTRY[name as ImagingReportBuilderName];
}

/** null for every specialty that is not an imaging report (the SAME exact-id
 *  predicate the E/M switch and the CPT-layer skip read — flag-agnostic, like
 *  `isImagingReportSpecialty`); the row's own builder for an imaging one;
 *  THROWS for an imaging row with no registered builder. */
export function imagingReportBuilderFor(
  specialtyId: string | null | undefined
): ImagingReportBuilder | null {
  if (!isImagingReportSpecialty(specialtyId)) return null;
  const row = SPECIALTIES.find((s) => s.id === specialtyId);
  if (!row) {
    // Unreachable: the predicate above matched an exact-id row. Kept loud so a
    // future predicate change cannot turn this into a silent null.
    throw new Error(
      `[imaging-report-builders] "${String(specialtyId)}" is an imaging report ` +
        'but has no catalog row'
    );
  }
  return resolveImagingReportBuilder(row);
}
