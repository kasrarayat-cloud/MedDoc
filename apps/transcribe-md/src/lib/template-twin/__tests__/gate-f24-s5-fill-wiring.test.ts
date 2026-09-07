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
import path, { join } from 'node:path';

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

import { processTemplateTwinVisit, readAndPrepareTemplateTwinFill } from '../fill-engine';

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

async function run(
  overrides: { fieldId: string; selectedOptionOrdinal: number }[],
  simulateOverrides?: readonly {
    fieldId: string;
    overrideKind: string;
    selectedOptionOrdinal?: number | null;
    insertedText?: string | null;
  }[],
) {
  overrideFindMany.mockResolvedValue(overrides);
  return readAndPrepareTemplateTwinFill({
    ...(simulateOverrides ? { simulateOverrides } : {}),
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

  // ══════════════════════════════════════════════════════════════════════════
  // ROUND FIVE — THE POST-WRITE SIMULATION'S MERGE HAD **ZERO EXECUTABLE
  // COVERAGE ANYWHERE IN THE REPO**, and that is what these arms close.
  //
  // Measured by the pass: collapse the merge to
  // `const effectiveOverrides = clinicianOverrides;` and `simulateOverrides` is
  // accepted, typed, documented, passed by the door — and SILENTLY DISCARDED.
  // tsc exit 0; 450 files / 6269 tests green. The door's refusal at
  // set-template-control.ts:564 becomes unreachable and the door admits exactly
  // the inserts the whole fix exists to stop.
  //
  // ⚠️ IT WAS INVISIBLE FOR A GEOMETRIC REASON, WHICH IS THIS FILE'S OWN THESIS
  // ONE TURN LATER: every `simulateOverrides` assertion in the repo lived in the
  // DOOR's gate, which mocks `readAndPrepareTemplateTwinFill` outright — so it
  // could only prove the door PASSES the argument, never that the fill USES it.
  // The door proving it passes an argument nobody reads is the same shape as
  // "all 16 arms call the overlay directly" at the top of this file.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ A SIMULATED ROW REACHES THE FILL — kills "collapse the merge to clinicianOverrides"', async () => {
    const field = selects[0];
    const opt = field.allowedOptions[field.allowedOptions.length - 1];

    const withoutAnything = await run([]);
    const simulatedOnly = await run([], [
      { fieldId: field.fieldId, overrideKind: 'option', selectedOptionOrdinal: opt.ordinal },
    ]);

    const before = withoutAnything.prepared.manifest.fields.find(
      (f) => f.fieldId === field.fieldId,
    )!;
    const after = simulatedOnly.prepared.manifest.fields.find(
      (f) => f.fieldId === field.fieldId,
    )!;

    // NON-VACUITY FIRST — the two runs must genuinely differ, or the assertion
    // below is satisfied by a document that never changed.
    expect(before.value).not.toBe(opt.value);
    expect(after.value).toBe(opt.value);
    expect(after.reasonCode).toBe('clinician_override');
  });

  it('⚠️ MERGED BY fieldId — a simulated row REPLACES the stored row for that field', async () => {
    const field = selects[0];
    const stored = field.allowedOptions[0];
    const pending = field.allowedOptions[field.allowedOptions.length - 1];
    expect(stored.ordinal, 'fixture needs two distinct options').not.toBe(pending.ordinal);

    const merged = await run(
      [{ fieldId: field.fieldId, selectedOptionOrdinal: stored.ordinal }],
      [{ fieldId: field.fieldId, overrideKind: 'option', selectedOptionOrdinal: pending.ordinal }],
    );

    const got = merged.prepared.manifest.fields.find((f) => f.fieldId === field.fieldId)!;
    // The PENDING value wins. Collapsing the merge yields the STORED one, which
    // is a different, non-vacuous value — so this arm reds on that mutation
    // rather than on an absence.
    expect(got.value).toBe(pending.value);
    expect(got.value).not.toBe(stored.value);
  });

  it('⚠️ …and the OTHER stored rows survive the merge — it replaces one field, not the list', async () => {
    const [a, b] = selects;
    expect(b, 'fixture needs two override-able selects').toBeDefined();
    const aStored = a.allowedOptions[0];
    const aPending = a.allowedOptions[a.allowedOptions.length - 1];
    const bStored = b.allowedOptions[b.allowedOptions.length - 1];

    const out = await run(
      [
        { fieldId: a.fieldId, selectedOptionOrdinal: aStored.ordinal },
        { fieldId: b.fieldId, selectedOptionOrdinal: bStored.ordinal },
      ],
      [{ fieldId: a.fieldId, overrideKind: 'option', selectedOptionOrdinal: aPending.ordinal }],
    );

    const gotA = out.prepared.manifest.fields.find((f) => f.fieldId === a.fieldId)!;
    const gotB = out.prepared.manifest.fields.find((f) => f.fieldId === b.fieldId)!;
    expect(gotA.value).toBe(aPending.value);
    // ⚠️ THE HALF A NAIVE "REPLACE THE LIST" WOULD BREAK. If the merge dropped
    // the unsimulated rows instead of filtering only the simulated fieldIds, B
    // would silently lose the doctor's stored correction.
    expect(gotB.value).toBe(bStored.value);
    expect(gotB.reasonCode).toBe('clinician_override');
  });

  it('⚠️ THE RETURNED LIST IS THE STORED ONE — the stamp must NOT include the simulation', async () => {
    // The manifest is stamped `overridesIdentity(<stored>)`. If the simulated
    // row leaked into the returned list, a read-only simulation would move the
    // identity of a document nobody wrote — the exact drift the writer-side
    // refusal exists to prevent, arriving on the read side instead.
    const field = selects[0];
    const out = await run([], [
      { fieldId: field.fieldId, overrideKind: 'option', selectedOptionOrdinal: field.allowedOptions[0].ordinal },
    ]);
    expect(out.clinicianOverrides).toEqual([]);
  });

  it('⚠️ THE WRITER REFUSES A SIMULATED FILL — and the refusal was uncovered too', async () => {
    // The other half of the same round-five finding: deleting this `throw` left
    // 102 files / 1233 tests green. Simulation is a READ-side capability —
    // persisting it would stamp `overridesIdentity(<stored>)` onto a document
    // rendered from stored PLUS pending, i.e. a manifest asserting an identity
    // the bytes do not correspond to.
    //
    // ⚠️ THE REFUSAL IS THE FIRST STATEMENT IN THE FUNCTION, WHICH IS WHY THIS
    // ARM NEEDS NO WRITE MOCKS AT ALL. If it ever moves below the first prisma
    // call this arm fails with a DIFFERENT error, and that is the correct
    // outcome: a guard that has drifted below a write is not the guard the
    // comment describes.
    await expect(
      processTemplateTwinVisit({
        visitId: 'v1',
        practiceId: 'prac-1',
        doctorId: 'doc-1',
        simulateOverrides: [
          { fieldId: selects[0].fieldId, overrideKind: 'option', selectedOptionOrdinal: 0 },
        ],
      } as never),
    ).rejects.toThrow(/refusing a simulated fill/);
  });

  it('⚠️ THE NO-OP SHORT-CIRCUIT COMPARES THE OVERRIDE HALF, NOT ONLY THE MANIFEST SHA', async () => {
    // Found by refuting my own untested claim rather than by the suite.
    //
    // The persist returns WITHOUT writing when the prepared manifest equals the
    // stored one — and `overridesSha256` is stamped below that return. A state
    // where the manifest sha matches but the override identity does not would
    // leave the stamp stale FOREVER: every export would read `overrides_changed`,
    // recompute, short-circuit, and never converge; and the sign freeze would
    // return `refill_did_not_match`, so the visit signs STYLED and loses native
    // export permanently.
    //
    // No such state is reachable today — every override outcome happens to
    // perturb the manifest — but that is an emergent coupling between three
    // unrelated paths, not a guarantee. This arm pins the guard so a later
    // tidy-up cannot quietly re-introduce the dependency.
    const src = readFileSync(
      join(__dirname, '..', 'fill-engine.ts'),
      'utf8',
    );
    const code = src
      .split('\n')
      .filter((l) => !l.trim().startsWith('//'))
      .join('\n');
    const idx = code.indexOf('existing?.manifestSha256 === prepared.manifestSha256');
    expect(idx, 'the no-op short-circuit moved or was renamed').toBeGreaterThan(-1);
    // The override term must be part of THAT condition, not merely present
    // somewhere in the file — the substring trap this whole gate exists to avoid.
    const condition = code.slice(idx, code.indexOf('{', idx));
    expect(
      condition,
      'the short-circuit can skip the overridesSha256 stamp — a styled signature waiting to happen',
    ).toContain('overridesSha256');
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
