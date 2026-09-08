// ============================================================================
// #287 — THE CHART'S PRACTICE OWNS THE TEMPLATE TOO.
// ----------------------------------------------------------------------------
// ⚠️ ONE SLOT WAS ANSWERING TWO QUESTIONS, AND THE TWO LANES HAD SHIPPED
// OPPOSITE WRONG ANSWERS INTO IT. `readAndPrepareTemplateTwinFill`'s
// `practiceId` scoped the VISIT (`transcribe_visits.practiceId` — the tenant,
// derived from the PATIENT) *and* validated the TEMPLATE
// (`sourceArtifact.practiceId` — the template's owner). Nothing constrains
// those equal; the schema comment on `TranscribeVisit.practiceId` says so in
// as many words:
//
//     "A note belongs to the practice that owns the CHART: a locum from
//      practice B seeing a patient of practice A creates a note in A.
//      Deriving from `user.practiceId` would file it in B and split that
//      patient's history."
//
//   main passed the AUTHOR's   -> the visit lookups missed on a locum visit
//   #267 passed the TENANT's   -> provenance threw and the document was withheld
//
// #287 decides the product question and the two questions get two names:
// `tenantPracticeId` scopes the visit AND selects/validates the template;
// `authorUserId` is who acted — audit and attribution, NEVER a scope.
//
// ⚠️ THE FIXTURE GIVES THREE IDENTITIES THREE DIFFERENT VALUES. Ruling #260:
// "a fixture that gives two distinct things the same value cannot witness them
// being confused" — and that is exactly how this defect survived, since every
// prior fixture had the tenant, the author and the author's practice agreeing.
// ============================================================================
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';

const noteTemplateFindFirst = vi.fn();
const overrideFindMany = vi.fn();
const visitFindFirst = vi.fn();
const visitUpdateMany = vi.fn();
const manifestFindFirst = vi.fn();
const compiledFindUnique = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: (...a: unknown[]) => noteTemplateFindFirst(...a) },
    templateTwinFieldOverride: { findMany: (...a: unknown[]) => overrideFindMany(...a) },
    templateTwinFillManifest: { findFirst: (...a: unknown[]) => manifestFindFirst(...a) },
    templateTwinCompiledVersion: { findUnique: (...a: unknown[]) => compiledFindUnique(...a) },
    transcribeVisit: {
      findFirst: (...a: unknown[]) => visitFindFirst(...a),
      updateMany: (...a: unknown[]) => visitUpdateMany(...a),
    },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
// Unrelated guard, stubbed only so the SUBJECT is reachable — same stated
// approximation the F24-S5 wiring gate makes, and for the same reason:
// reproducing `approvedMappingsSha256` here would mean re-implementing
// module-private shipped code.
vi.mock('../mapping-hash', () => ({ templateTwinMappingsSha256: () => 'MAPPINGS_SHA' }));

import { processTemplateTwinVisit, readAndPrepareTemplateTwinFill } from '../fill-engine';
import { loadOrComputeNativeTemplateDocxForVisit } from '../native-export';

// ── THE LOCUM, WITH THREE DISTINCT IDENTITIES ───────────────────────────────
const TENANT = 'practice-A-owns-the-chart';
const AUTHOR = 'user-locum-visiting-from-B';
const AUTHOR_PRACTICE = 'practice-B-the-locums-own';

const WM_IOV = new Uint8Array(
  readFileSync(path.resolve(process.cwd(), '../../WM IOV Template.docx')),
);
const ir = compileTemplateDocx(WM_IOV);

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
  readSourceArtifact: async () => WM_IOV,
  storeOutputArtifact: async () => ({ objectKey: 'k', sha256: 's', mimeType: 'm', sizeBytes: 1 }),
  readOutputArtifact: async () => WM_IOV,
};

/** A's certified template. `artifactPractice` is a knob so the negative control
 *  can hand the same tenant a template owned by somebody else. */
function templateRow(artifactPractice: string) {
  return {
    id: 'tpl-A',
    version: 1,
    templateTwinCompiledVersion: {
      id: 'cv-A',
      compilerVersion: ir.compilerVersion,
      compiledDocumentIr: ir,
      certificationStatus: 'CERTIFIED',
      certification: { id: 'cert-A', approvedMappingsSha256: 'MAPPINGS_SHA' },
      sourceArtifact: {
        practiceId: artifactPractice,
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
  };
}

const input = {
  visitId: 'visit-of-A-patient',
  tenantPracticeId: TENANT,
  authorUserId: AUTHOR,
  noteTemplateId: 'tpl-A',
  noteTemplateVersion: 1,
  inputMode: 'dictation',
  contextText: 'right GSV incompetent',
  entities: {},
  generatedNote: 'IMPRESSION: right GSV incompetent.',
  visitDate: new Date('2026-09-07T00:00:00.000Z'),
  validationNow: new Date('2026-09-07T00:00:00.000Z'),
  resolverModelVersion: null,
  storage: storage as never,
};

beforeEach(() => {
  noteTemplateFindFirst.mockReset();
  overrideFindMany.mockReset().mockResolvedValue([]);
  visitFindFirst.mockReset().mockResolvedValue({ patient: null });
  visitUpdateMany.mockReset().mockResolvedValue({ count: 0 });
  manifestFindFirst.mockReset().mockResolvedValue(null);
  compiledFindUnique.mockReset().mockResolvedValue({ certificationStatus: 'DRAFT' });
  noteTemplateFindFirst.mockResolvedValue(templateRow(TENANT));
});

describe("#287 — the locum's visit renders A's form", () => {
  it("⚠️ THE TEMPLATE IS SELECTED BY THE TENANT, and the author appears in NO filter", async () => {
    await readAndPrepareTemplateTwinFill(input as never);

    expect(noteTemplateFindFirst).toHaveBeenCalledTimes(1);
    const where = (noteTemplateFindFirst.mock.calls[0][0] as { where: Record<string, unknown> })
      .where;

    // The decision, observed as the query the engine actually issues.
    expect(where.practiceId).toBe(TENANT);
    expect(where.id).toBe('tpl-A');
    expect(where.version).toBe(1);

    // ⚠️ KILLS THE SHAPE THAT SHIPPED — `doctorId: input.doctorId`. Under it a
    // locum's visit selects the LOCUM's template (practice B), provenance then
    // compares B against tenant A, and the doctor gets
    // TEMPLATE_PROVENANCE_MISMATCH on a visit whose form exists and is
    // certified. Asserted on the VALUES, so any key carrying the actor reds.
    for (const [k, v] of Object.entries(where)) {
      expect(v, `\`${k}\` carries the ACTOR — #287 says the actor never scopes`).not.toBe(AUTHOR);
      expect(v, `\`${k}\` carries the AUTHOR'S PRACTICE, not the chart's`).not.toBe(
        AUTHOR_PRACTICE,
      );
    }
  });

  it("A's FORM ACTUALLY FILLS for a visit authored by B's locum", async () => {
    const { prepared, compiled } = await readAndPrepareTemplateTwinFill(input as never);

    // Not merely "did not throw": the document A owns was read and filled.
    expect(compiled.sourceArtifact.practiceId).toBe(TENANT);
    expect(prepared.manifest.fields.length).toBeGreaterThan(0);
  });

  it('⚠️ REACHABILITY CONTROL — provenance is LIVE, and it is measured against the TENANT', async () => {
    // Same tenant, same author, template owned by B. If this passed, the arm
    // above would be proving nothing: a fill that never checks provenance
    // renders every practice's form for every practice.
    noteTemplateFindFirst.mockResolvedValue(templateRow(AUTHOR_PRACTICE));
    await expect(readAndPrepareTemplateTwinFill(input as never)).rejects.toMatchObject({
      code: 'TEMPLATE_PROVENANCE_MISMATCH',
    });
  });

  it('⚠️ THE VISIT CLAIM SCOPES BY THE CHART, NOT BY THE ACTOR', async () => {
    // `processTemplateTwinVisit` claims the template version on the visit row
    // before any I/O. That `where` carried `userId: input.doctorId` — the ONE
    // of four visit reads in this function that did — so an actor who is not
    // the visit's author matched zero rows and got
    //   TEMPLATE_PROVENANCE_MISMATCH "already pinned to another note template
    //   version"
    // on a visit pinned to nothing at all: a false message for an ordinary
    // state. Count 0 is forced here so the claim is observable on its own.
    await expect(processTemplateTwinVisit(input as never)).rejects.toMatchObject({
      code: 'TEMPLATE_PROVENANCE_MISMATCH',
    });

    expect(visitUpdateMany).toHaveBeenCalledTimes(1);
    const where = (visitUpdateMany.mock.calls[0][0] as { where: Record<string, unknown> }).where;
    expect(where.practiceId).toBe(TENANT);
    expect(where.userId, 'the actor is back in the visit scope').toBeUndefined();
  });

  it('⚠️ CLASS CLOSURE — the actor reaches no `where` anywhere in the engine', () => {
    // A class gate, not a behavioural proof (#251): the two arms above measure
    // the two sites that exist TODAY. This one reds on a NINTH.
    const src = readFileSync(path.join(__dirname, '..', 'fill-engine.ts'), 'utf8')
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
      .join('\n');

    const reads = [...src.matchAll(/input\.authorUserId/g)];
    // NON-VACUITY: if the field is gone or renamed, this arm must not pass by
    // finding nothing. The engine attributes audit rows with it.
    expect(reads.length, 'no `input.authorUserId` reads at all — arm is vacuous').toBeGreaterThan(
      1,
    );

    for (const m of reads) {
      const before = src.slice(Math.max(0, m.index! - 200), m.index!);
      expect(
        /where\s*:\s*\{[^}]*$/.test(before),
        'a `where` filters on the actor — that is a scope, and #287 says never',
      ).toBe(false);
    }
  });
});

describe('#287 — the EXPORT door asked the same question a different way', () => {
  it("⚠️ THE COMPUTE PATH SCOPES BY THE CHART, matching the cached read it claims to match", async () => {
    // `native-export.ts` had TWO visit scopes one function apart. The cached
    // read used the visit's own `practiceId` column; the compute path used
    // `user: { practiceId }` — the AUTHOR's practice, through the relation —
    // under a comment reading "PRACTICE-SCOPED, LIKE THE READ".
    //
    // For a locum's visit in practice A the cached read FINDS it and the
    // compute path finds NOTHING: `visit_not_eligible`, silently falling back
    // to styled export. That is the exact divergence the comment promised to
    // prevent, in the direction it named.
    visitFindFirst
      .mockResolvedValueOnce({ status: 'READY', frozenFillManifestId: null }) // cached read
      .mockResolvedValueOnce({
        status: 'READY',
        inputMode: 'dictation',
        transcriptText: 't',
        entities: {},
        soapFinal: 'A note.',
        noteTemplateId: 'tpl-A',
        noteTemplateVersion: 1,
        createdAt: new Date('2026-09-07T00:00:00.000Z'),
        signedAt: null,
        userId: AUTHOR, // the locum authored it; the CHART is still A's
      });

    await loadOrComputeNativeTemplateDocxForVisit('visit-of-A-patient', TENANT);

    // NON-VACUITY: two reads, and the SECOND is the one under test. One read
    // would mean the compute path never ran and the arm proved nothing.
    expect(visitFindFirst).toHaveBeenCalledTimes(2);
    const where = (visitFindFirst.mock.calls[1][0] as { where: Record<string, unknown> }).where;

    expect(where.practiceId).toBe(TENANT);
    expect(where.id).toBe('visit-of-A-patient');
    // ⚠️ KILLS THE SHAPE THAT SHIPPED. `user: { practiceId }` reaches the
    // author's practice, which for a locum is not the chart's.
    expect(where.user, 'the visit is scoped through the AUTHOR relation again').toBeUndefined();
  });
});
