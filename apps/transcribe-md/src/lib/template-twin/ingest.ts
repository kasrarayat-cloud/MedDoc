// ============================================================================
// RULING #274 — THE INGEST ENTRY POINT: the I/O half.
// ----------------------------------------------------------------------------
// The PURE half — `structuralKey`, `planTransfer`, and the reasoning that
// decided them — lives in `./ingest-plan`, so its arms need no database.
// ============================================================================
import { createHash } from 'node:crypto';

import { prisma, type Prisma } from '@meddoc/db';

import { compileTemplateDocx } from '../note-template-docx';

import { fromPersistedMapping } from './certification-lifecycle';
import { fieldCreateInput } from './create-draft';
import {
  planTransfer,
  TemplateTwinIngestRefused,
  type IngestTemplateTwinInput,
  type IngestTemplateTwinResult,
} from './ingest-plan';
import { type SemanticMapping, type TemplateDocIR } from './ir';
import { fallbackSemanticMappings, proposeSemanticMappings } from './semantic-mapping';

export * from './ingest-plan';

function sha256(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * Ingest stored bytes into a NEW note template + compiled version, carrying
 * certified dispositions across by structural correspondence.
 *
 * ⚠️ ATOMIC BY CONSTRUCTION: template, compiled version, field definitions,
 * transferred mappings and the demotion all land in ONE transaction. A partial
 * apply here is a template that exists and cannot be filled, or a demotion with
 * nothing promoted in its place — and the doctor meets both as "my form is
 * gone".
 */
export async function ingestTemplateTwin(
  input: IngestTemplateTwinInput,
): Promise<IngestTemplateTwinResult> {
  const actualSha = sha256(input.source);

  // ── PRE-GUARD 1 · the bytes are the ones the record pins ──────────────────
  const expectedSha = input.guards?.expectSourceSha256;
  if (expectedSha !== undefined && expectedSha !== actualSha) {
    throw new TemplateTwinIngestRefused({
      code: 'SOURCE_SHA_MISMATCH',
      expected: expectedSha,
      actual: actualSha,
    });
  }

  // ⚠️ THE COMPILE IS PURE — `compiler.ts` holds no `prisma` and no `await` —
  // which is what lets both remaining guards run before any write. A guard
  // after a write is not a guard; it is a cleanup obligation.
  const ir = compileTemplateDocx(input.source);
  if (ir.fields.length === 0) {
    throw new TemplateTwinIngestRefused({ code: 'NO_FILLABLE_FIELDS' });
  }

  // ── PRE-GUARD 2 · the field ids are exactly the ones expected ─────────────
  const expectIds = input.guards?.expectFieldIds;
  if (expectIds !== undefined) {
    const got = new Set(ir.fields.map((f) => f.fieldId));
    const want = new Set(expectIds);
    const missing = [...want].filter((id) => !got.has(id)).sort();
    const unexpected = [...got].filter((id) => !want.has(id)).sort();
    if (missing.length > 0 || unexpected.length > 0) {
      throw new TemplateTwinIngestRefused({
        code: 'FIELD_IDS_NOT_SET_EQUAL',
        missing,
        unexpected,
      });
    }
  }

  // ── the transfer source, read before anything is written ─────────────────
  let sourceIr: TemplateDocIR | null = null;
  let certifiedByFieldId = new Map<string, SemanticMapping>();
  let demotedNoteTemplateId: string | null = null;

  if (input.transferFrom) {
    const from = await prisma.templateTwinCompiledVersion.findUnique({
      where: { id: input.transferFrom },
      include: { fields: { include: { mapping: true } } },
    });
    if (!from) {
      throw new TemplateTwinIngestRefused({
        code: 'TRANSFER_SOURCE_NOT_FOUND',
        compiledVersionId: input.transferFrom,
      });
    }
    // ⚠️ TENANCY IS CHECKED ON THE READ, NOT ON THE WRITE. Reading another
    // practice's dispositions and copying them into this one is a
    // cross-practice disclosure even if every subsequent write is scoped
    // correctly — the data has already crossed by then.
    if (from.practiceId !== input.actor.practiceId) {
      throw new TemplateTwinIngestRefused({
        code: 'TRANSFER_SOURCE_WRONG_PRACTICE',
        compiledVersionId: input.transferFrom,
      });
    }
    sourceIr = from.compiledDocumentIr as unknown as TemplateDocIR;
    demotedNoteTemplateId = from.noteTemplateId;
    certifiedByFieldId = new Map(
      from.fields
        .filter((f) => f.mapping !== null && f.mapping.mappingStatus === 'CERTIFIED')
        .map((f) => [
          f.fieldId,
          fromPersistedMapping(f.fieldId, f.mapping as Parameters<typeof fromPersistedMapping>[1]),
        ]),
    );
  }

  const plan = planTransfer({ target: ir, sourceIr, certifiedByFieldId });

  // ── PRE-GUARD 3 · the transfer moved what the caller declared ─────────────
  // ⚠️ CHECKED HERE, STILL BEFORE ANY WRITE. A declared count that does not
  // match means the correspondence did something other than what the
  // declaration described, and #2.5's whole product is that the answer was
  // fixed before the evidence existed.
  const expectTransfer = input.guards?.expectTransferCount;
  if (expectTransfer !== undefined && expectTransfer !== plan.transferred.length) {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_COUNT_MISMATCH',
      expected: expectTransfer,
      actual: plan.transferred.length,
    });
  }

  // ── the re-proposal, for every field with no certified counterpart ───────
  // ⚠️ OUTSIDE THE TRANSACTION, DELIBERATELY. This is a model call; holding a
  // database transaction open across a network round-trip to a third party is
  // how a pool gets exhausted by one slow provider.
  let proposedByModel: string | null = null;
  let proposedForRest: SemanticMapping[] = [];
  if (plan.reproposed.length > 0) {
    const needsProposal = {
      ...ir,
      fields: ir.fields.filter((f) => plan.reproposed.includes(f.fieldId)),
    } as TemplateDocIR;
    try {
      proposedForRest = await proposeSemanticMappings(needsProposal, {
        practiceId: input.actor.practiceId,
        userId: input.actor.userId,
      });
      proposedByModel = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';
    } catch {
      // Structure stays useful when the provider is unavailable; the fallback
      // is visibly unconfirmed and cannot be certified until a physician rules.
      proposedForRest = fallbackSemanticMappings(needsProposal);
      proposedByModel = null;
    }
  }

  // ⚠️ TRANSFERRED FIRST, THEN PROPOSED — and `fieldCreateInput` demands EXACTLY
  // one mapping per compiled field, throwing otherwise. That is the arithmetic
  // check this function would otherwise have to write for itself.
  const allMappings: SemanticMapping[] = [
    ...plan.transferred.map((t) => t.mapping),
    ...proposedForRest,
  ];

  const result = await prisma.$transaction(async (tx) => {
    const noteTemplate = await tx.noteTemplate.create({
      data: {
        practiceId: input.actor.practiceId,
        // ⚠️ `doctorId`, NOT `createdById` — and the biconditional
        // `note_templates_practice_iff_doctor` pairs it with `practiceId`, so
        // the two move together or the constraint refuses the row. tsc caught
        // the wrong name here; it cannot catch the pairing, because the shared
        // prisma client is `any`.
        doctorId: input.actor.userId,
        name: input.templateName,
        encounterType: null,
        sections: [] as unknown as Prisma.InputJsonValue,
        version: 1,
        // ⚠️ DRAFT, AND ACTIVATION IS A SEPARATE RULED STEP. This function
        // mints and transfers; it does NOT promote. The owner confirms the
        // rows, then certification and activation run as their own acts —
        // which is what keeps "ingest" reusable by the upload path, where
        // nothing should be activated on the doctor's behalf at all.
        status: 'draft',
        isSystemDefault: false,
      },
      select: { id: true },
    });

    const artifact = await tx.templateTwinSourceArtifact.create({
      data: {
        practiceId: input.actor.practiceId,
        createdById: input.actor.userId,
        lineageId: noteTemplate.id,
        lineageVersion: 1,
        objectKey: `ingest/${input.actor.practiceId}/${actualSha}`,
        sha256: actualSha,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        sizeBytes: input.source.byteLength,
        validationStatus: 'accepted',
        rejectionCodes: [],
      },
      select: { id: true },
    });

    const compiled = await tx.templateTwinCompiledVersion.create({
      data: {
        sourceArtifactId: artifact.id,
        noteTemplateId: noteTemplate.id,
        practiceId: input.actor.practiceId,
        compilerVersion: ir.compilerVersion,
        irSchemaVersion: ir.irSchemaVersion,
        compiledDocumentIr: ir as unknown as Prisma.InputJsonValue,
        unsupportedElements: ir.unsupported as unknown as Prisma.InputJsonValue,
        structureSha256: ir.structureSha256,
        staticContentSha256: ir.staticContentSha256,
        blockingUnsupportedCount: ir.stats.blockingUnsupported,
      },
      select: { id: true },
    });

    // ⚠️ THE COLUMN LIST IS `create-draft.ts`'s, IMPORTED — NEVER RETYPED.
    // The first draft of this function hand-rolled it and wrote
    // `conceptScope: []` where the rule is `Prisma.DbNull`. That is not a
    // cosmetic difference: `[]` is a VALUE, it moves the attestation sha of
    // every mapping, and every template silently stops being certified. The
    // rule is documented at the writer, and the copy did not carry the comment
    // with it — which is how these copies always fail.
    await tx.templateTwinCompiledVersion.update({
      where: { id: compiled.id },
      data: {
        fields: {
          create: fieldCreateInput(ir, allMappings, proposedByModel, input.actor.practiceId),
        },
      },
    });

    return { noteTemplateId: noteTemplate.id, compiledVersionId: compiled.id };
  });

  return {
    noteTemplateId: result.noteTemplateId,
    compiledVersionId: result.compiledVersionId,
    sourceSha256: actualSha,
    fieldCount: ir.fields.length,
    transferred: plan.transferred.length,
    reproposed: plan.reproposed.length,
    demotedNoteTemplateId,
  };
}
