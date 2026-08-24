// ============================================================================
// F24-S5 — THE WIRING AT THE LAYER THE LAST SLICE DIED ONE ABOVE.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS FILE IS SEPARATE FROM THE OVERLAY GATE. The overlay gate proves
// `prepareTemplateTwinFill` applies a correction — by calling it DIRECTLY with
// `clinicianOverrides` already in hand. That is precisely the geometry that hid
// the refuted slice's defect: "all 16 arms call the overlay or the fill
// directly; the loss happens one layer ABOVE".
//
// The pass's own mutation was *delete the `clinicianOverrides` argument from
// the `prepareTemplateTwinFill` CALL* — inside `readAndPrepareTemplateTwinFill`
// — and a gate that calls the fill directly cannot see it, however behavioural
// it is. So this file drives `readAndPrepareTemplateTwinFill`: the function
// every real caller (worker, preview, export, sign freeze) actually goes
// through.
//
// ⚠️ STATED APPROXIMATION. Two unrelated guards are stubbed so that the SUBJECT
// is reachable at all: the mappings-provenance hash (`./mapping-hash`) and the
// audit sink. Neither is what this file asserts, and stubbing them changes no
// route the fill takes — the compiled IR, the resolver, the overlay and the
// merge are all the shipped code.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';

const noteTemplateFindFirst = vi.fn();
const overrideFindMany = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: (...a: unknown[]) => noteTemplateFindFirst(...a) },
    templateTwinFieldOverride: { findMany: (...a: unknown[]) => overrideFindMany(...a) },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
// The certification's `approvedMappingsSha256` must equal the hash of the
// derived mappings. `mappingFromRow` is module-private, so reproducing that
// value in the test would mean re-implementing shipped code — which canon warns
// against more strongly than it warns against stubbing an unrelated guard.
vi.mock('../mapping-hash', () => ({
  templateTwinMappingsSha256: () => 'MAPPINGS_SHA',
}));

import { readAndPrepareTemplateTwinFill } from '../fill-engine';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));
const ir = compileTemplateDocx(wmIovBytes);
const selects = ir.fields.filter(
  (f) => f.rendererBinding.bindingType === 'content_control' && f.allowedOptions.length > 0,
);

const mappingRow = {
  sourceType: 'extraction',
  clinicalConcept: 'exam.side',
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
  mappingStatus: 'CERTIFIED',
};

const storage = {
  readSourceArtifact: async () => wmIovBytes,
  storeOutputArtifact: async () => ({
    objectKey: 'k',
    sha256: 's',
    mimeType: 'm',
    sizeBytes: 1,
  }),
  readOutputArtifact: async () => wmIovBytes,
};

beforeEach(() => {
  noteTemplateFindFirst.mockReset();
  overrideFindMany.mockReset();
  overrideFindMany.mockResolvedValue([]);
  noteTemplateFindFirst.mockResolvedValue({
    id: 'tpl-1',
    version: 1,
    templateTwinCompiledVersion: {
      id: 'cv-1',
      compilerVersion: ir.compilerVersion,
      compiledDocumentIr: ir,
      certificationStatus: 'CERTIFIED',
      certification: { id: 'cert-1', approvedMappingsSha256: 'MAPPINGS_SHA' },
      sourceArtifact: {
        practiceId: 'prac-1',
        objectKey: 'obj',
        sha256: 'sha',
        sizeBytes: 1,
        validationStatus: 'accepted',
      },
      fields: ir.fields.map((f) => ({
        fieldId: f.fieldId,
        detectionStatus: 'CERTIFIED',
        mapping: mappingRow,
      })),
    },
  });
});

async function run(overrides: { fieldId: string; selectedOptionOrdinal: number }[]) {
  overrideFindMany.mockResolvedValue(overrides);
  return readAndPrepareTemplateTwinFill({
    visitId: 'v1',
    practiceId: 'prac-1',
    doctorId: 'doc-1',
    noteTemplateId: 'tpl-1',
    noteTemplateVersion: 1,
    inputMode: 'dictation',
    contextText: 'right GSV incompetent',
    entities: {},
    generatedNote: 'IMPRESSION: right GSV incompetent.',
    visitDate: new Date('2026-08-24T00:00:00.000Z'),
    validationNow: new Date('2026-08-24T00:00:00.000Z'),
    resolverModelVersion: null,
    storage: storage as never,
  } as never);
}

describe('F24-S5 — the READ PATH carries the correction into the fill', () => {
  it('⚠️ THE OVERRIDE SET IS READ, scoped by visit AND practice', async () => {
    await run([]);
    expect(overrideFindMany).toHaveBeenCalledTimes(1);
    const arg = overrideFindMany.mock.calls[0][0] as { where: unknown };
    // ⚠️ KILLS "drop visitId from the override where" — without it, one
    // patient's corrections would be applied to another patient's document.
    expect(arg.where).toEqual({ visitId: 'v1', practiceId: 'prac-1' });
  });

  it('⚠️ KILLS "delete the clinicianOverrides argument" — AT THE REAL CALL SITE', async () => {
    const field = selects[0];
    const opt = field.allowedOptions[field.allowedOptions.length - 1];

    const without = await run([]);
    const withOverride = await run([
      { fieldId: field.fieldId, selectedOptionOrdinal: opt.ordinal },
    ]);

    const before = without.prepared.manifest.fields.find(
      (f) => f.fieldId === field.fieldId,
    )!;
    const after = withOverride.prepared.manifest.fields.find(
      (f) => f.fieldId === field.fieldId,
    )!;

    // NON-VACUITY: the two runs must actually differ, and in the right
    // direction. If the argument is dropped at the call site, `after` equals
    // `before` and this reddens — which the substring arm it replaces could
    // never do.
    expect(before.value).not.toBe(opt.value);
    expect(after.value).toBe(opt.value);
    expect(after.reasonCode).toBe('clinician_override');
    expect(after.clinicianReviewed).toBe(true);
  });

  it('⚠️ AND THE READ PATH RETURNS THE LIST IT USED — so the stamp cannot drift', async () => {
    // `overridesSha256` is stamped from THIS list, not from a fresh read. If the
    // read path stopped returning it, the persist would have to re-read and
    // could stamp an identity the rendered document does not correspond to.
    const field = selects[0];
    const opt = field.allowedOptions[0];
    const out = await run([{ fieldId: field.fieldId, selectedOptionOrdinal: opt.ordinal }]);
    expect(out.clinicianOverrides).toEqual([
      { fieldId: field.fieldId, selectedOptionOrdinal: opt.ordinal },
    ]);
  });
});
