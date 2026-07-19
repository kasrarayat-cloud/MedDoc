import { randomUUID } from 'node:crypto';
import { z } from 'zod';

import type { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { TemplateDocxError } from '@/lib/note-template-docx';

import type { SemanticMapping, TemplateDocIR } from './ir';
import { DOCX_TEMPLATE_COMPILER } from './artifact-compiler';
import {
  fallbackSemanticMappings,
  proposeSemanticMappings,
} from './semantic-mapping';
import {
  createTemplateTwinArtifactStore,
  claimTemplateTwinObject,
  type TemplateTwinArtifactStore,
} from './storage';
import {
  assertTemplateTwinSourcePhiFree,
  TemplateTwinPhiRejectedError,
  TemplateTwinPhiScanUnavailableError,
  TemplateTwinSourcePrivacyUnsupportedError,
  type TemplateTwinSourcePhiScanEvidence,
} from './source-phi';
import { enqueueTemplateTwinAudit } from './audit-outbox';
import { lockAndAssertTemplateTwinStaticAssetBindingsCurrent } from './static-assets';
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from './rollout';
import type { TemplateTwinMalwareScanner } from './malware-scan';
import {
  admitTemplateTwinQuarantine,
  beginTemplateTwinQuarantine,
  rejectTemplateTwinQuarantine,
  scanTemplateTwinQuarantine,
} from './quarantine-admission';
import { minimizeTemplateTwinSourceMetadata } from './source-metadata';

export class TemplateTwinDraftError extends Error {
  readonly code:
    | 'INVALID_IDENTITY'
    | 'NO_FILLABLE_FIELDS'
    | 'SYSTEM_TEMPLATE_MISSING'
    | 'ROLLOUT_CHANGED'
    | 'PERSISTENCE_FAILED';

  constructor(code: TemplateTwinDraftError['code'], message: string, cause?: unknown) {
    super(message, { cause });
    this.name = 'TemplateTwinDraftError';
    this.code = code;
  }
}

const TemplateTwinIdentitySchema = z.object({
  name: z.string().trim().min(3).max(120),
  encounterType: z.string().trim().min(3).max(120),
  versionDescription: z.string().trim().min(3).max(500),
});

export interface CreateTemplateTwinDraftInput {
  source: Uint8Array;
  identity: {
    name: string;
    encounterType: string;
    versionDescription: string;
  };
  actor: {
    userId: string;
    userEmail: string;
    practiceId: string;
    rolloutToken: TemplateTwinRolloutToken;
  };
  /**
   * Visit-shaped provider identity supplied only by an admitted synthetic QA
   * context. Ordinary uploads leave this unset and retain the existing null
   * provider identity.
   */
  providerVisitId?: string | null;
  storage?: TemplateTwinArtifactStore;
  /** Explicit test seam. Runtime callers omit this and require the configured
   * Unix-socket ClamAV scanner. */
  malwareScanner?: TemplateTwinMalwareScanner;
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
  const identity = TemplateTwinIdentitySchema.safeParse(input.identity);
  if (!identity.success) {
    throw new TemplateTwinDraftError(
      'INVALID_IDENTITY',
      'Name the template, choose its visit scope, and describe this version.',
    );
  }
  const artifactStore = input.storage ?? createTemplateTwinArtifactStore();
  const quarantine = await beginTemplateTwinQuarantine({
    source: input.source,
    actor: input.actor,
    intakeMode: 'NATIVE_TEMPLATE',
    storage: artifactStore,
  });
  await scanTemplateTwinQuarantine({
    source: input.source,
    receipt: quarantine,
    actor: input.actor,
    ...(input.malwareScanner ? { scanner: input.malwareScanner } : {}),
  });

  let minimizedSource;
  try {
    minimizedSource = await minimizeTemplateTwinSourceMetadata(input.source);
  } catch (error) {
    const code = error instanceof TemplateDocxError ? error.code : 'DOCX_METADATA_MINIMIZATION_FAILED';
    await rejectTemplateTwinQuarantine({
      receipt: quarantine,
      actor: input.actor,
      rejectionCode: code,
    });
    throw error;
  }

  const admittedSource = minimizedSource.document;
  let ir: TemplateDocIR;
  try {
    ir = DOCX_TEMPLATE_COMPILER.compile(admittedSource);
  } catch (error) {
    const code = error instanceof TemplateDocxError ? error.code : 'DOCX_COMPILE_FAILED';
    await rejectTemplateTwinQuarantine({
      receipt: quarantine,
      actor: input.actor,
      rejectionCode: code,
      metadataEvidence: minimizedSource.evidence,
    });
    throw error;
  }
  if (ir.fields.length === 0) {
    await rejectTemplateTwinQuarantine({
      receipt: quarantine,
      actor: input.actor,
      rejectionCode: 'NO_FILLABLE_FIELDS',
      metadataEvidence: minimizedSource.evidence,
    });
    throw new TemplateTwinDraftError(
      'NO_FILLABLE_FIELDS',
      'No supported fillable Word controls or table fields were detected.',
    );
  }

  let privacyScanEvidence: TemplateTwinSourcePhiScanEvidence;
  try {
    privacyScanEvidence = await assertTemplateTwinSourcePhiFree({
      source: admittedSource,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
      providerVisitId: input.providerVisitId,
    });
  } catch (error) {
    if (
      error instanceof TemplateTwinPhiRejectedError ||
      error instanceof TemplateTwinPhiScanUnavailableError ||
      error instanceof TemplateTwinSourcePrivacyUnsupportedError
    ) {
      await rejectTemplateTwinQuarantine({
        receipt: quarantine,
        actor: input.actor,
        rejectionCode: error.code,
        metadataEvidence: minimizedSource.evidence,
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
      providerVisitId: input.providerVisitId,
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

  const lineageId = quarantine.lineageId;
  const noteTemplateId = randomUUID();
  const sourceArtifactId = randomUUID();
  const compiledVersionId = randomUUID();
  const stored = await artifactStore.storeSourceArtifact({
    practiceId: input.actor.practiceId,
    lineageId,
    templateVersion: 1,
    bytes: admittedSource,
  });

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      // The immutable PUT is deliberately performed before this transaction.
      // Revalidate the admission epoch before any source/configuration claim;
      // stale bytes remain WRITTEN_UNCLAIMED for durable reconciliation.
      const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!finalRollout.allowed) {
        throw new TemplateTwinDraftError(
          'ROLLOUT_CHANGED',
          `${finalRollout.code}: Template Twin availability changed while the template was being compiled. Upload it again.`,
        );
      }
      await lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
        practiceId: input.actor.practiceId,
        bindings: privacyScanEvidence.staticAssetApprovalBindings ?? [],
        db: tx as unknown as Parameters<
          typeof lockAndAssertTemplateTwinStaticAssetBindingsCurrent
        >[0]['db'],
      });
      await tx.noteTemplate.create({
        data: {
          id: noteTemplateId,
          doctorId: input.actor.userId,
          name: identity.data.name,
          encounterType: identity.data.encounterType,
          sections: systemDefault.sections as Prisma.InputJsonValue,
          styleProfile: systemDefault.styleProfile as Prisma.InputJsonValue,
          specialtyBaseline: systemDefault.specialtyBaseline,
          version: 1,
          versionDescription: identity.data.versionDescription,
          status: 'draft',
          isSystemDefault: false,
          lineageId,
          parentVersionId: null,
          templateKind: 'template_twin_docx',
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
          objectVersionId: stored.objectVersionId,
          objectEtag: stored.objectEtag,
          sha256: stored.sha256,
          mimeType: stored.mimeType,
          sizeBytes: stored.sizeBytes,
          validationStatus: 'accepted',
          rejectionCodes: [],
          privacyScanEvidence: asJson(privacyScanEvidence),
          quarantineArtifactId: quarantine.id,
        },
      });
      await admitTemplateTwinQuarantine({
        tx,
        receipt: quarantine,
        actor: input.actor,
        sourceArtifactId,
        metadataEvidence: minimizedSource.evidence,
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
      await claimTemplateTwinObject(tx, {
        objectKey: stored.objectKey,
        practiceId: input.actor.practiceId,
        claimType: 'source_artifact',
        claimId: sourceArtifactId,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:source-uploaded:${sourceArtifactId}:${stored.sha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_SOURCE_UPLOADED',
        targetType: 'TemplateTwinSourceArtifact',
        targetId: sourceArtifactId,
        metadata: {
          sha256: stored.sha256,
          sizeBytes: stored.sizeBytes,
          objectVersionId: stored.objectVersionId,
          objectEtag: stored.objectEtag,
          lineageVersion: 1,
          privacyScanProfileVersion: privacyScanEvidence.profileVersion,
          privacyScanProvider: privacyScanEvidence.provider,
          privacyScanModel: privacyScanEvidence.model,
          privacyScannedAt: privacyScanEvidence.scannedAt,
          approvedStaticAssetPolicySha256:
            privacyScanEvidence.approvedStaticAssetPolicySha256,
          approvedStaticAssetCount:
            privacyScanEvidence.approvedStaticAssetCount,
          approvedStaticAssetUsedCount:
            privacyScanEvidence.approvedStaticAssetUsedCount,
          quarantineArtifactId: quarantine.id,
          quarantinedSourceSha256: quarantine.stored.sha256,
          malwareScanProfileVersion: 'template-twin-clamd-instream-v1',
          metadataMinimizationProfileVersion:
            minimizedSource.evidence.profileVersion,
          metadataMinimizationSha256:
            minimizedSource.evidence.minimizedSha256,
        },
      });
      for (const binding of
        privacyScanEvidence.staticAssetApprovalBindings ?? []) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:static-asset-used:${sourceArtifactId}:${binding.decisionId}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: 'TEMPLATE_TWIN_STATIC_ASSET_USED',
          targetType: 'TemplateTwinStaticAsset',
          targetId: binding.assetId,
          metadata: {
            sha256: binding.sha256,
            decisionId: binding.decisionId,
            decisionVersion: binding.decisionVersion,
            inspectionEvidenceSha256:
              binding.inspectionEvidenceSha256,
            sourceArtifactId,
          },
        });
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:compiled:${compiledVersionId}:${ir.structureSha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_COMPILED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: compiledVersionId,
        metadata: {
          compilerVersion: ir.compilerVersion,
          irSchemaVersion: ir.irSchemaVersion,
          fieldCount: ir.stats.totalFields,
          tableCount: ir.stats.tables,
          unsupportedCount: ir.stats.unsupported,
          blockingUnsupportedCount: ir.stats.blockingUnsupported,
          semanticProposalFallback: usedFallbackMappings,
          rolloutGlobalGeneration:
            input.actor.rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration:
            input.actor.rolloutToken.practiceGeneration.toString(),
        },
      });
    }, { isolationLevel: 'ReadCommitted' });
  } catch (error) {
    if (error instanceof TemplateTwinDraftError) throw error;
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

  return {
    noteTemplateId,
    sourceSha256: stored.sha256,
    compilerVersion: ir.compilerVersion,
    fieldCount: ir.stats.totalFields,
    blockingUnsupportedCount: ir.stats.blockingUnsupported,
    usedFallbackMappings,
  };
}
