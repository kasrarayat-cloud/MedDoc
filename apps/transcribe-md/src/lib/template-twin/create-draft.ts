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
import { extractNoteTextFromUpload } from '@/lib/note-template-parse/extract-note-text';
import { parseNoteToTemplate } from '@/lib/note-template-parse/parse-note-to-template';

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
  // ⚠️ T7 — THREADED THROUGH THE NESTED CREATES. `fields.create` and its own
  // `mapping.create` are two more rows in the twin chain, and the migration
  // derives both from source_artifacts.practiceId. tsc surfaced the field level
  // only because this file imports concrete Prisma types — the shared client is
  // `any`, so nothing here is checked by default.
  practiceId: string,
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
      practiceId,
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
          practiceId,
          // The classification is decided at PROPOSAL time from the compiler's
          // own label. If it is not written here the row defaults to
          // 'extraction', and a field nobody dictates looks like a field the
          // extractor simply failed on — which blocks certification forever.
          sourceType: mapping.sourceType,
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

  // ── The BRIDGE ────────────────────────────────────────────────────────────
  // This used to hand the twin NoteTemplate `systemDefault.sections` verbatim,
  // i.e. Subjective / Objective / Assessment / Plan. That is the defect the
  // 2026-07-25 probe found: the twin extracted 80 field definitions from the
  // real WM_IOV docx and then generated against SOAP headings the document does
  // not contain, so L4 wrote a SOAP note and the fill bound almost nothing.
  //
  // The document's own structure is not something this file has to invent — the
  // ordinary one-tap upload path already derives it, and derives it well (the
  // same WM_IOV docx parses to "Venous Duplex Lower Extremities US Report,
  // 5 sections, 4 header fields"). So the bridge reuses that parser rather than
  // growing a second, divergent one.
  //
  // The IR is deliberately NOT the source of sections: it models fillable
  // controls and tables (flat `fields` + `tableId`), which is the right model
  // for BINDING but carries no section concept. Sections come from the prose
  // structure; bindings come from the IR. Two different questions.
  //
  // Fails SOFT, and visibly: if extraction or parsing fails we keep the
  // system-default sections so the draft still exists and the source artifact
  // is still preserved — but we record why, so the Settings card can say the
  // twin is running on fallback structure instead of pretending it is fine.
  let bridgedSections: Prisma.InputJsonValue = systemDefault.sections as Prisma.InputJsonValue;
  let bridgedStyle: Prisma.InputJsonValue = systemDefault.styleProfile as Prisma.InputJsonValue;
  let bridgedName = 'Original Word template';
  let bridgeFallbackReason: string | null = null;

  try {
    const extracted = await extractNoteTextFromUpload(
      input.source,
      'template.docx',
      DOCX_MIME_TYPE,
    );
    const noteText = extracted.ok ? extracted.text : '';
    if (!noteText.trim()) {
      bridgeFallbackReason = 'NO_TEXT_EXTRACTED';
    } else {
      const parsed = await parseNoteToTemplate(noteText, {
        practiceId: input.actor.practiceId,
        userId: input.actor.userId,
      });
      if (parsed.rejected || !parsed.template) {
        bridgeFallbackReason = 'PARSE_REJECTED';
      } else if (!Array.isArray(parsed.template.sections) || parsed.template.sections.length === 0) {
        bridgeFallbackReason = 'PARSE_EMPTY_SECTIONS';
      } else {
        bridgedSections = parsed.template.sections as unknown as Prisma.InputJsonValue;
        bridgedStyle = (parsed.template.styleProfile ??
          systemDefault.styleProfile) as unknown as Prisma.InputJsonValue;
        bridgedName = parsed.template.name?.trim() || bridgedName;
      }
    }
  } catch {
    // Never fail the draft on a bridge miss — the twin's structural work (the
    // IR, the artifact, the field definitions) is still valuable and is what
    // the physician reviews. Reason is surfaced, not swallowed.
    bridgeFallbackReason = 'BRIDGE_THREW';
  }
  if (bridgeFallbackReason) {
    console.warn(
      `[template-twin:bridge] fell back to system-default sections (${bridgeFallbackReason}) — ` +
        'the twin will generate against SOAP headings this document does not contain',
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
          // T7 — the biconditional `note_templates_practice_iff_doctor` pairs these
          // two. tsc cannot see it: the shared prisma client is `any`.
          practiceId: input.actor.practiceId,
          name: bridgedName,
          encounterType: null,
          sections: bridgedSections,
          styleProfile: bridgedStyle,
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
          // T7 — derived in the migration from source_artifacts.practiceId; the
          // same value, one layer up. The actor's practice IS the artifact's:
          // the artifact was created from this actor two statements above.
          practiceId: input.actor.practiceId,
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
            create: fieldCreateInput(ir, mappings, proposedByModel, input.actor.practiceId),
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
