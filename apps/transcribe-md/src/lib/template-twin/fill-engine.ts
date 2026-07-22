import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { logTwinAudit as logAudit } from './twin-audit';
import {
  renderTemplateDocx,
  type RenderTemplateDocxResult,
} from '@/lib/note-template-docx';

import { canonicalSha256 } from './canonical';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
  type EncounterInputMode,
} from './encounter-facts';
import {
  SemanticMappingSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateTwinFillManifest,
} from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import {
  resolveTemplateFields,
  withApprovedPracticeDefaultFacts,
} from './resolver';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';
import { validateTemplateTwin } from './validation';

/** The worker-owned review marker for an unresolved Template Twin fill.
 * Correction code may clear it only by exact equality after a fully verified
 * replacement, so unrelated pipeline review reasons remain untouched. */
export const TEMPLATE_TWIN_REVIEW_REASON =
  'The Original Template DOCX has unresolved fields that require clinician review before signing.';

export class TemplateTwinFillError extends Error {
  readonly code:
    | 'CERTIFIED_TEMPLATE_NOT_FOUND'
    | 'TEMPLATE_PROVENANCE_MISMATCH'
    | 'SOURCE_ARTIFACT_UNAVAILABLE'
    | 'SIGNED_MANIFEST_IMMUTABLE'
    | 'MANIFEST_CONFLICT';

  constructor(code: TemplateTwinFillError['code'], message: string, cause?: unknown) {
    super(message, { cause });
    this.name = 'TemplateTwinFillError';
    this.code = code;
  }
}

export interface PrepareTemplateTwinFillInput {
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  ir: TemplateDocIR;
  mappings: readonly SemanticMapping[];
  facts: ReturnType<typeof projectEncounterFacts>;
  certifiedFieldIds?: readonly string[];
  source?: Uint8Array;
  resolverModelVersion: string | null;
  validationNow: Date | string;
  allowUncertifiedForSyntheticTest?: boolean;
}

export interface PreparedTemplateTwinFill {
  manifest: TemplateTwinFillManifest;
  manifestSha256: string;
  factSetSha256: string;
  render: RenderTemplateDocxResult | null;
}

export interface FinalizeTemplateTwinFillInput
  extends Omit<PrepareTemplateTwinFillInput, 'facts'> {
  facts: ReturnType<typeof projectEncounterFacts>;
  resolutions: readonly FieldResolution[];
}

export async function finalizeTemplateTwinFill(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) => SemanticMappingSchema.parse(mapping));
  const fields = [...input.resolutions];
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts: input.facts,
    resolutions: fields,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
    now: input.validationNow,
  });
  const counts = templateTwinCounts(fields, ir.fields);
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    facts: input.facts,
    fields,
    validation,
    counts,
  });
  const manifestSha256 = canonicalSha256(manifest);
  const factSetSha256 = canonicalSha256(input.facts);
  if (!validation.valid) {
    return { manifest, manifestSha256, factSetSha256, render: null };
  }
  if (!input.source) {
    throw new TemplateTwinFillError(
      'SOURCE_ARTIFACT_UNAVAILABLE',
      'The immutable source document is unavailable for verified rendering.',
    );
  }
  const render = await renderTemplateDocx({
    source: input.source,
    ir,
    resolutions: fields,
    validation,
  });
  return { manifest, manifestSha256, factSetSha256, render };
}

/** Pure clinical boundary apart from the exact renderer. Invalid or unresolved
 * fields are retained for review and never rendered. */
export async function prepareTemplateTwinFill(
  input: PrepareTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) => SemanticMappingSchema.parse(mapping));
  const facts = withApprovedPracticeDefaultFacts({
    fields: ir.fields,
    mappings,
    facts: input.facts,
  });
  const fields = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
  });
  return finalizeTemplateTwinFill({
    ...input,
    ir,
    mappings,
    facts,
    resolutions: fields,
  });
}

interface PersistedMappingRow {
  clinicalConcept: string | null;
  expectedDataType: string;
  polarityBehavior: string;
  temporality: string | null;
  laterality: string | null;
  unitPolicy: string | null;
  approvedSynonyms: unknown;
  required: boolean;
  blankPolicy: string;
  unknownPolicy: string;
  practiceDefault: string | null;
  mappingStatus: string;
}

function mappingFromRow(fieldId: string, row: PersistedMappingRow): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms) ? row.approvedSynonyms : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

export interface ProcessTemplateTwinVisitInput {
  visitId: string;
  practiceId: string;
  doctorId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  inputMode: EncounterInputMode;
  contextText: string;
  /** Runtime-validated Layer-3 entity object. The legacy generic Zod helper
   * widens some inferred leaf types to unknown, so this boundary narrows only
   * after Layer 3 has parsed the object. */
  entities: unknown;
  asrQuality?: 'high' | 'review' | 'unknown';
  validationNow: Date | string;
  resolverModelVersion: string | null;
  storage?: TemplateTwinArtifactStore;
}

/** Resolves, independently validates, conditionally renders, stores, and
 * records one visit against its already-selected immutable template version. */
export async function processTemplateTwinVisit(
  input: ProcessTemplateTwinVisitInput,
): Promise<PreparedTemplateTwinFill> {
  // Persist the first selected version before source I/O, resolution, model-
  // derived evidence processing, or rendering. A retry must never switch to a
  // newly activated template after partial work against this version.
  const claimedTemplate = await prisma.transcribeVisit.updateMany({
    where: {
      id: input.visitId,
      userId: input.doctorId,
      deletedAt: null,
      archivedAt: null,
      status: { not: 'SIGNED' },
      OR: [
        { noteTemplateId: null, noteTemplateVersion: null },
        {
          noteTemplateId: input.noteTemplateId,
          noteTemplateVersion: input.noteTemplateVersion,
        },
      ],
    },
    data: {
      noteTemplateId: input.noteTemplateId,
      noteTemplateVersion: input.noteTemplateVersion,
    },
  });
  if (claimedTemplate.count !== 1) {
    throw new TemplateTwinFillError(
      'TEMPLATE_PROVENANCE_MISMATCH',
      'This visit is already pinned to another note template version.',
    );
  }

  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.doctorId,
      version: input.noteTemplateVersion,
    },
    select: {
      id: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compilerVersion: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          certification: { select: { id: true, approvedMappingsSha256: true } },
          sourceArtifact: {
            select: {
              practiceId: true,
              objectKey: true,
              sha256: true,
              sizeBytes: true,
              validationStatus: true,
            },
          },
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
              detectionStatus: true,
              mapping: {
                select: {
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
                  unknownPolicy: true,
                  practiceDefault: true,
                  mappingStatus: true,
                },
              },
            },
          },
        },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion;
  if (!row || !compiled || compiled.certificationStatus !== 'CERTIFIED' || !compiled.certification) {
    throw new TemplateTwinFillError(
      'CERTIFIED_TEMPLATE_NOT_FOUND',
      'The selected Template Twin version is not certified and active.',
    );
  }
  if (
    row.version !== input.noteTemplateVersion ||
    compiled.sourceArtifact.practiceId !== input.practiceId ||
    compiled.sourceArtifact.validationStatus !== 'accepted' ||
    !compiled.sourceArtifact.objectKey
  ) {
    throw new TemplateTwinFillError(
      'TEMPLATE_PROVENANCE_MISMATCH',
      'The selected Template Twin provenance does not match this visit.',
    );
  }
  const certifiedFieldIds: string[] = [];
  const mappings = compiled.fields.map((field: {
    fieldId: string;
    detectionStatus: string;
    mapping: PersistedMappingRow | null;
  }) => {
    if (!field.mapping) {
      throw new TemplateTwinFillError(
        'TEMPLATE_PROVENANCE_MISMATCH',
        'The certified Template Twin mapping set is incomplete.',
      );
    }
    if (field.detectionStatus !== 'CERTIFIED') {
      throw new TemplateTwinFillError(
        'TEMPLATE_PROVENANCE_MISMATCH',
        'The certified Template Twin field set is incomplete.',
      );
    }
    certifiedFieldIds.push(field.fieldId);
    return mappingFromRow(field.fieldId, field.mapping);
  });
  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  if (
    mappings.length !== ir.fields.length ||
    templateTwinMappingsSha256(mappings) !==
      compiled.certification.approvedMappingsSha256
  ) {
    throw new TemplateTwinFillError(
      'TEMPLATE_PROVENANCE_MISMATCH',
      'The certified Template Twin mappings no longer match their certification.',
    );
  }
  const facts = projectEncounterFacts({
    mode: input.inputMode,
    contextText: input.contextText,
    entities: input.entities as EncounterEntitySnapshot,
    asrQuality: input.asrQuality,
  });
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const source = await storage.readSourceArtifact({
    practiceId: input.practiceId,
    objectKey: compiled.sourceArtifact.objectKey,
    expectedSha256: compiled.sourceArtifact.sha256,
    expectedSizeBytes: compiled.sourceArtifact.sizeBytes,
  });
  const prepared = await prepareTemplateTwinFill({
    compiledVersionId: compiled.id,
    noteTemplateId: row.id,
    noteTemplateVersion: row.version,
    ir,
    mappings,
    facts,
    certifiedFieldIds,
    source,
    resolverModelVersion: input.resolverModelVersion,
    validationNow: input.validationNow,
  });

  const existing = await prisma.templateTwinFillManifest.findUnique({
    where: { visitId: input.visitId },
    select: {
      id: true,
      status: true,
      signedDecisionAt: true,
      reviewedAt: true,
      manifestVersion: true,
      manifestSha256: true,
      roundTripVerified: true,
    },
  });
  if (
    existing &&
    (existing.status === 'SIGNED' || existing.signedDecisionAt !== null)
  ) {
    throw new TemplateTwinFillError(
      'SIGNED_MANIFEST_IMMUTABLE',
      'A signed Template Twin fill manifest cannot be replaced.',
    );
  }
  if (
    existing?.manifestSha256 === prepared.manifestSha256 &&
    (prepared.render === null || existing.roundTripVerified)
  ) {
    return prepared;
  }
  if (existing?.reviewedAt != null) {
    throw new TemplateTwinFillError(
      'MANIFEST_CONFLICT',
      'A clinician-reviewed Template Twin fill cannot be replaced by a worker retry.',
    );
  }

  const storedOutput = prepared.render
    ? await storage.storeOutputArtifact({
        practiceId: input.practiceId,
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        bytes: prepared.render.document,
      })
    : null;
  const status = prepared.render ? 'VERIFIED' : 'NEEDS_REVIEW';
  const writeData = {
    compiledVersionId: compiled.id,
    noteTemplateId: row.id,
    noteTemplateVersion: row.version,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    status,
    fillManifest: asJson(prepared.manifest),
    manifestSha256: prepared.manifestSha256,
    factSetSha256: prepared.factSetSha256,
    validationResult: asJson(prepared.manifest.validation),
    filledCount: prepared.manifest.counts.filled,
    needsReviewCount: prepared.manifest.counts.needsReview,
    notMentionedCount: prepared.manifest.counts.notMentioned,
    conflictCount: prepared.manifest.counts.conflicts,
    criticalUnresolvedCount: prepared.manifest.counts.criticalUnresolved,
    outputObjectKey: storedOutput?.objectKey ?? null,
    outputSha256: storedOutput?.sha256 ?? null,
    outputMimeType: storedOutput?.mimeType ?? null,
    outputSizeBytes: storedOutput?.sizeBytes ?? null,
    staticContentSha256: prepared.render ? ir.staticContentSha256 : null,
    roundTripVerified: prepared.render?.verification.verified === true,
    roundTripVerification: prepared.render
      ? asJson(prepared.render.verification)
      : Prisma.JsonNull,
  } as const;

  if (existing) {
    // Signing and clinician correction both use optimistic claims. The worker
    // must claim the exact unsigned row it observed; a signed or concurrently
    // replaced row produces no update and remains untouched.
    const updated = await prisma.templateTwinFillManifest.updateMany({
      where: {
        id: existing.id,
        status: { not: 'SIGNED' },
        signedDecisionAt: null,
        reviewedAt: null,
        manifestVersion: existing.manifestVersion,
        manifestSha256: existing.manifestSha256,
      },
      data: {
        ...writeData,
        manifestVersion: { increment: 1 },
      },
    });
    if (updated.count !== 1) {
      const current = await prisma.templateTwinFillManifest.findUnique({
        where: { visitId: input.visitId },
        select: { status: true, signedDecisionAt: true },
      });
      if (
        current &&
        (current.status === 'SIGNED' || current.signedDecisionAt !== null)
      ) {
        throw new TemplateTwinFillError(
          'SIGNED_MANIFEST_IMMUTABLE',
          'A signed Template Twin fill manifest cannot be replaced.',
        );
      }
      throw new TemplateTwinFillError(
        'MANIFEST_CONFLICT',
        'The Template Twin fill changed concurrently and was not replaced.',
      );
    }
  } else {
    try {
      await prisma.templateTwinFillManifest.create({
        data: {
          practiceId: input.practiceId,
          visitId: input.visitId,
          ...writeData,
        },
      });
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        (error.code === 'P2002' || error.code === 'P2034')
      ) {
        throw new TemplateTwinFillError(
          'MANIFEST_CONFLICT',
          'Another worker created the Template Twin fill first.',
          error,
        );
      }
      throw error;
    }
  }

  if (prepared.render) {
    await logAudit({
      action: 'TEMPLATE_TWIN_RENDER_VERIFIED',
      targetType: 'TranscribeVisit',
      targetId: input.visitId,
      userId: input.doctorId,
      practiceId: input.practiceId,
      metadata: {
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        rendererVersion: prepared.render.rendererVersion,
        outputSha256: prepared.render.outputSha256,
        fieldCount: prepared.manifest.counts.filled,
      },
    });
  }
  return prepared;
}
