// ============================================================================
// Template Twin — upload -> compile -> propose -> persist DRAFT (Phase 2b).
// Compiles the uploaded .docx to the IR (fail-closed; quarantines a rejected
// source), proposes semantic mappings (bounded LLM), then persists a NoteTemplate
// (EXISTING columns only — no lineage) plus the twin source-artifact / compiled-
// version / field-definitions / proposed-mappings. prisma singleton + logTwinAudit.
// ============================================================================
import { createHash, randomUUID } from 'node:crypto';

import type { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import {
  TemplateDocxError,
} from '@/lib/note-template-docx';
import { logTwinAudit as logAudit } from './twin-audit';

import type { SemanticMapping, TemplateDocIR } from './ir';
import { DOCX_TEMPLATE_COMPILER } from './artifact-compiler';
import {
  fallbackSemanticMappings,
  proposeSemanticMappings,
} from './semantic-mapping';
import {
  createTemplateTwinArtifactStore,
  DOCX_MIME_TYPE,
  type TemplateTwinArtifactStore,
} from './storage';
import {
  assertTemplateTwinSourcePhiFree,
  TemplateTwinPhiRejectedError,
} from './source-phi';

export class TemplateTwinDraftError extends Error {
  readonly code:
    | 'NO_FILLABLE_FIELDS'
    | 'SYSTEM_TEMPLATE_MISSING'
    | 'PERSISTENCE_FAILED';

  constructor(code: TemplateTwinDraftError['code'], message: string, cause?: unknown) {
    super(message, { cause });
    this.name = 'TemplateTwinDraftError';
    this.code = code;
  }
}

export interface CreateTemplateTwinDraftInput {
  source: Uint8Array;
  actor: {
    userId: string;
    userEmail: string;
    practiceId: string;
  };
  storage?: TemplateTwinArtifactStore;
}

export interface CreateTemplateTwinDraftResult {
  noteTemplateId: string;
  sourceSha256: string;
  compilerVersion: string;
  fieldCount: number;
  blockingUnsupportedCount: number;
  usedFallbackMappings: boolean;
}

function enumStatus(
  value: 'recognized' | 'needs_confirmation' | 'unsupported' | 'certified',
): 'RECOGNIZED' | 'NEEDS_CONFIRMATION' | 'UNSUPPORTED' | 'CERTIFIED' {
  switch (value) {
    case 'recognized':
      return 'RECOGNIZED';
    case 'needs_confirmation':
      return 'NEEDS_CONFIRMATION';
    case 'unsupported':
      return 'UNSUPPORTED';
    case 'certified':
      return 'CERTIFIED';
  }
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

async function quarantineRejectedSource(input: {
  bytes: Uint8Array;
  actor: CreateTemplateTwinDraftInput['actor'];
  rejectionCode: string;
}): Promise<void> {
  if (input.bytes.byteLength < 1) return;
  const digest = createHash('sha256').update(input.bytes).digest('hex');
  try {
    const row = await prisma.templateTwinSourceArtifact.create({
      data: {
        practiceId: input.actor.practiceId,
        createdById: input.actor.userId,
        lineageId: randomUUID(),
        lineageVersion: 1,
        objectKey: null,
        sha256: digest,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: input.bytes.byteLength,
        validationStatus: 'quarantined',
        rejectionCodes: [input.rejectionCode.slice(0, 80)],
      },
      select: { id: true },
    });
    await logAudit({
      action: 'TEMPLATE_TWIN_QUARANTINED',
      targetType: 'TemplateTwinSourceArtifact',
      targetId: row.id,
      userId: input.actor.userId,
      userEmail: input.actor.userEmail,
      practiceId: input.actor.practiceId,
      success: false,
      errorCode: input.rejectionCode.slice(0, 80),
      metadata: { sha256: digest, sizeBytes: input.bytes.byteLength },
    });
  } catch {
    // The source bytes are still rejected and discarded. A failed metadata-only
    // quarantine write must not make an unsafe document acceptable.
  }
}

function fieldCreateInput(
  ir: TemplateDocIR,
  mappings: readonly SemanticMapping[],
  proposedByModel: string | null,
) {
  const mappingById = new Map(mappings.map((mapping) => [mapping.fieldId, mapping]));
  return ir.fields.map((field) => {
    const mapping = mappingById.get(field.fieldId);
    if (!mapping) {
      throw new TemplateTwinDraftError(
        'PERSISTENCE_FAILED',
        'A compiler field is missing its semantic mapping.',
      );
    }
    return {
      fieldId: field.fieldId,
      displayOrder: field.displayOrder,
      originalLabel: field.originalLabel,
      fieldKind: field.kind,
      allowedOptions: asJson(field.allowedOptions),
      rendererBinding: asJson(field.rendererBinding),
      detectionStatus: enumStatus(field.detectionStatus),
      clinicallyMaterial: field.clinicallyMaterial,
      criticality: field.criticality,
      required: field.required,
      mapping: {
        create: {
          clinicalConcept: mapping.clinicalConcept,
          expectedDataType: mapping.expectedDataType,
          polarityBehavior: mapping.polarityBehavior,
          temporality: mapping.temporality,
          laterality: mapping.laterality,
          unitPolicy: mapping.unitPolicy,
          approvedSynonyms: asJson(mapping.approvedSynonyms),
          required: mapping.required,
          blankPolicy: mapping.blankPolicy,
          unknownPolicy: mapping.unknownPolicy,
          practiceDefault: null,
          mappingStatus: enumStatus(mapping.status),
          proposedByModel,
        },
      },
    };
  });
}

export async function createTemplateTwinDraft(
  input: CreateTemplateTwinDraftInput,
): Promise<CreateTemplateTwinDraftResult> {
  let ir: TemplateDocIR;
  try {
    ir = DOCX_TEMPLATE_COMPILER.compile(input.source);
  } catch (error) {
    const code = error instanceof TemplateDocxError ? error.code : 'DOCX_COMPILE_FAILED';
    await quarantineRejectedSource({
      bytes: input.source,
      actor: input.actor,
      rejectionCode: code,
    });
    throw error;
  }
  if (ir.fields.length === 0) {
    await quarantineRejectedSource({
      bytes: input.source,
      actor: input.actor,
      rejectionCode: 'NO_FILLABLE_FIELDS',
    });
    throw new TemplateTwinDraftError(
      'NO_FILLABLE_FIELDS',
      'No supported fillable Word controls or table fields were detected.',
    );
  }

  try {
    await assertTemplateTwinSourcePhiFree({
      source: input.source,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
  } catch (error) {
    if (error instanceof TemplateTwinPhiRejectedError) {
      await quarantineRejectedSource({
        bytes: input.source,
        actor: input.actor,
        rejectionCode: error.code,
      });
    }
    throw error;
  }

  let mappings: SemanticMapping[];
  let proposedByModel: string | null;
  let usedFallbackMappings = false;
  try {
    mappings = await proposeSemanticMappings(ir, {
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
    proposedByModel =
      process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';
  } catch {
    // Structure remains useful when the semantic provider is unavailable.
    // The fallback is visibly unconfirmed and cannot be certified until the
    // physician supplies and confirms each concept.
    mappings = fallbackSemanticMappings(ir);
    proposedByModel = null;
    usedFallbackMappings = true;
  }

  const systemDefault = await prisma.noteTemplate.findFirst({
    where: { isSystemDefault: true },
    select: {
      sections: true,
      styleProfile: true,
      specialtyBaseline: true,
    },
  });
  if (!systemDefault) {
    throw new TemplateTwinDraftError(
      'SYSTEM_TEMPLATE_MISSING',
      'The standard note-format fallback is unavailable.',
    );
  }

  const lineageId = randomUUID();
  const noteTemplateId = randomUUID();
  const sourceArtifactId = randomUUID();
  const compiledVersionId = randomUUID();
  const artifactStore = input.storage ?? createTemplateTwinArtifactStore();
  const stored = await artifactStore.storeSourceArtifact({
    practiceId: input.actor.practiceId,
    lineageId,
    templateVersion: 1,
    bytes: input.source,
  });

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      await tx.noteTemplate.create({
        data: {
          id: noteTemplateId,
          doctorId: input.actor.userId,
          name: 'Original Word template',
          encounterType: null,
          sections: systemDefault.sections as Prisma.InputJsonValue,
          styleProfile: systemDefault.styleProfile as Prisma.InputJsonValue,
          specialtyBaseline: systemDefault.specialtyBaseline,
          version: 1,
          status: 'draft',
          isSystemDefault: false,
          // note_templates byte-identical: no lineage columns (twin lineage lives
          // on the source artifact).
        },
      });
      await tx.templateTwinSourceArtifact.create({
        data: {
          id: sourceArtifactId,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          lineageId,
          lineageVersion: 1,
          objectKey: stored.objectKey,
          sha256: stored.sha256,
          mimeType: stored.mimeType,
          sizeBytes: stored.sizeBytes,
          validationStatus: 'accepted',
          rejectionCodes: [],
        },
      });
      await tx.templateTwinCompiledVersion.create({
        data: {
          id: compiledVersionId,
          sourceArtifactId,
          noteTemplateId,
          compilerVersion: ir.compilerVersion,
          irSchemaVersion: ir.irSchemaVersion,
          compiledDocumentIr: asJson(ir),
          unsupportedElements: asJson(ir.unsupported),
          structureSha256: ir.structureSha256,
          staticContentSha256: ir.staticContentSha256,
          certificationStatus:
            ir.stats.blockingUnsupported > 0 ? 'UNSUPPORTED' : 'NEEDS_CONFIRMATION',
          blockingUnsupportedCount: ir.stats.blockingUnsupported,
          fields: {
            create: fieldCreateInput(ir, mappings, proposedByModel),
          },
        },
      });
    });
  } catch (error) {
    // The put-once source remains recoverable in the dedicated private bucket.
    // No delete is attempted from this request path because source deletion is
    // intentionally unavailable; Operations can reconcile a DB-less object by
    // its tenant prefix and digest without risking an overwrite.
    throw new TemplateTwinDraftError(
      'PERSISTENCE_FAILED',
      'The template could not be recorded. It was not activated.',
      error,
    );
  }

  await Promise.all([
    logAudit({
      action: 'TEMPLATE_TWIN_SOURCE_UPLOADED',
      targetType: 'TemplateTwinSourceArtifact',
      targetId: sourceArtifactId,
      userId: input.actor.userId,
      userEmail: input.actor.userEmail,
      practiceId: input.actor.practiceId,
      metadata: {
        sha256: stored.sha256,
        sizeBytes: stored.sizeBytes,
        lineageVersion: 1,
      },
    }),
    logAudit({
      action: 'TEMPLATE_TWIN_COMPILED',
      targetType: 'TemplateTwinCompiledVersion',
      targetId: compiledVersionId,
      userId: input.actor.userId,
      userEmail: input.actor.userEmail,
      practiceId: input.actor.practiceId,
      metadata: {
        compilerVersion: ir.compilerVersion,
        irSchemaVersion: ir.irSchemaVersion,
        fieldCount: ir.stats.totalFields,
        tableCount: ir.stats.tables,
        unsupportedCount: ir.stats.unsupported,
        blockingUnsupportedCount: ir.stats.blockingUnsupported,
        semanticProposalFallback: usedFallbackMappings,
      },
    }),
  ]);

  return {
    noteTemplateId,
    sourceSha256: stored.sha256,
    compilerVersion: ir.compilerVersion,
    fieldCount: ir.stats.totalFields,
    blockingUnsupportedCount: ir.stats.blockingUnsupported,
    usedFallbackMappings,
  };
}
