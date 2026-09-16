// ============================================================================
// Template Twin — upload -> compile -> propose -> persist DRAFT (Phase 2b).
// Compiles the uploaded .docx to the IR (fail-closed; quarantines a rejected
// source), proposes semantic mappings (bounded LLM), then persists a NoteTemplate
// (EXISTING columns only — no lineage) plus the twin source-artifact / compiled-
// version / field-definitions / proposed-mappings. prisma singleton + logTwinAudit.
// ============================================================================
import { createHash, randomUUID } from 'node:crypto';

import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';
import { asPracticeId, templateScope } from '@/lib/practice-scope';
import { extractNoteTextFromUpload } from '@/lib/note-template-parse/extract-note-text';
import { parseNoteToTemplate } from '@/lib/note-template-parse/parse-note-to-template';

import {
  TemplateDocxError,
} from '@/lib/note-template-docx';
import { logTwinAudit as logAudit } from './twin-audit';

import type { SemanticMapping, TemplateDocIR } from './ir';
import { DOCX_TEMPLATE_COMPILER } from './artifact-compiler';
import { deriveProseTwin, derivedTwinProbeIsValid } from './prose-form/derive-prose-twin';
import { isPdfSource, pdfToProseDocx, type SectionDirective } from './pdf-form/pdf-to-prose-docx';
import { relocateFillLinesToBlankState } from './pdf-form/fill-line-blank-state';
import { formDetectFillEnabled } from '@/config/form-detect-fill';
import { createDetectedFormDraft } from './create-detected-draft';
import {
  fallbackSemanticMappings,
  proposeSemanticMappings,
} from './semantic-mapping';
import {
  createTemplateTwinArtifactStore,
  DOCX_MIME_TYPE,
  PDF_MIME_TYPE,
  type TemplateTwinArtifactStore,
} from './storage';
import {
  assertTemplateTwinSourcePhiFree,
  TemplateTwinPhiRejectedError,
} from './source-phi';

export class TemplateTwinDraftError extends Error {
  readonly code:
    | 'NO_FILLABLE_FIELDS'
    | 'PDF_NO_TEXT_LAYER'
    | 'SYSTEM_TEMPLATE_MISSING'
    | 'ATTACH_TARGET_NOT_FOUND'
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
  /**
   * RC-2 — ATTACH to the note template the doctor just created, instead of
   * minting a second one.
   *
   * ⚠️ THIS IS WHAT MAKES THE DOOR REACHABLE. Without it the only caller is
   * `template-twin-certify.ts`, reached from `NativeTemplateManager`, which
   * renders **null** in production (`NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true`) —
   * so the compile path existed and nothing on earth could invoke it. Wiring
   * the ordinary Settings → My Note Format upload to this function would
   * otherwise create a DUPLICATE template beside the doctor's own.
   *
   * ⚠️ AND IT MAKES THE BRIDGE DEAD WEIGHT, DELIBERATELY. The bridge below
   * exists only to synthesise sections for the orphan template this function
   * used to mint. When attaching, the ordinary upload path has ALREADY parsed
   * the document into sections — better, and by the parser the doctor's own
   * note actually uses — so the bridge is skipped entirely rather than run and
   * discarded. Skipping it also removes its fallback, which is the failure mode
   * it was written to survive.
   *
   * The id is verified against the ACTOR'S OWN PRACTICE before anything is
   * written. A caller cannot bind a compiled version to another tenant's row.
   */
  attachToNoteTemplateId?: string;
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
  /** The rejected bytes' media — DOCX by default, PDF for an S2 PDF rejection.
   *  Recorded on the quarantine row so it names what was actually rejected. */
  mimeType?: string;
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
        mimeType: input.mimeType ?? DOCX_MIME_TYPE,
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

/**
 * ⚠️ EXPORTED FOR `ingest.ts`, AND THAT IS THE POINT — #274.
 *
 * The ingest entry point creates the same three rows this function does, and a
 * second copy of this column list is exactly the failure this repository keeps
 * paying for. The first draft of `ingest.ts` DID hand-roll it and got
 * `conceptScope` wrong in the one way the comment below warns about — writing
 * `[]` where the rule is `Prisma.DbNull`, which moves the attestation sha of
 * every mapping and de-certifies every template. Nothing would have failed
 * loudly; the templates would simply have stopped being certified.
 *
 * One writer for these columns. There is no second.
 */
export function fieldCreateInput(
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
          // ⚠️ #192 — NO COERCION. `?? 'keep'` would have opted every mapping
          // nobody ruled on into keeping, which is exactly the inference this
          // ruling forbids. Absent stays absent, and absent is fail-closed.
          unmentionedPolicy: mapping.unmentionedPolicy ?? null,
          // ⚠️ #217 — THIS IS THE TABLE'S ONLY INSERT, AND IT IS WHERE THE
          // COLUMN ACTUALLY GETS ITS VALUE. The certification writer is an
          // UPDATE; it can only change a row this statement already created. A
          // first version of #217 added the column, the UPDATE and the five
          // read-back projections and left this line out — so `conceptScope`
          // would have been NULL for the entire life of every row, and every
          // reader the ruling set out to revive would have stayed dead code
          // behind a migration that looked like it had fixed them.
          //
          // NULL when absent, never `[]`: an empty array is a value and would
          // move the attestation sha of every mapping.
          conceptScope:
            mapping.conceptScope && mapping.conceptScope.length > 0
              ? asJson(mapping.conceptScope)
              : Prisma.DbNull,
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
  // ⚠️ S1 — `source` is the twin's SOURCE OF TRUTH from here down. For a prose
  // form it is REPLACED by the derived-twin bytes below, so the compiled version,
  // the PHI scan, the stored source artifact and `sourceSha256` all describe the
  // SAME controlled document. Everything downstream reads `source`, never
  // `input.source`.
  let source = input.source;
  // ── S2 · UPLOAD-AND-CERTIFIED — PDF FORM → FAITHFUL PROSE DOCX ─────────────
  // A PDF has no `word/document.xml`, so it is reconstructed into a prose DOCX
  // FIRST (STRUCTURAL fidelity, ruling S2-1); everything below then runs the
  // IDENTICAL DOCX path (S1 derive → compile → propose → certify). The ORIGINAL
  // PDF is retained as the upload artifact (content-addressed, put-once) — stored
  // beside the twin. A scanned / text-less PDF reconstructs to nothing → null →
  // quarantine PDF_NO_TEXT_LAYER, declined cleanly with a plain message (ruling
  // S2-2; we never OCR).
  // ⚠️ Captured BEFORE `source` is overwritten with the reconstructed prose DOCX:
  // the S2 fill-line-blank-state relocation below runs ONLY for a PDF (a form S2
  // synthesised), never for an S1 doctor-uploaded DOCX (byte-preserved).
  const wasPdf = isPdfSource(source);
  // ── #326 ONE-PIPELINE INTERCEPT (Slice B, behind formDetectFillEnabled). A PDF
  // upload is routed onto the detect→fill pipeline instead of the PDF→prose-DOCX
  // twin derivation. `source` is still the ORIGINAL PDF here (it is overwritten by
  // the reconstructed prose DOCX below). Flag OFF ⇒ the existing DOCX-twin path
  // runs unchanged, byte-identical to today.
  if (wasPdf && formDetectFillEnabled()) {
    return await createDetectedFormDraft({
      pdf: source,
      actor: input.actor,
      attachToNoteTemplateId: input.attachToNoteTemplateId,
    });
  }
  // #325 — the per-line section directives from the PDF derivation, threaded to
  // `deriveProseTwin` so a numbered slot / single section block gets its concept
  // tag. Undefined for a DOCX upload (that path is byte-preserving, no directives).
  let proseDirectives: SectionDirective[] | undefined;
  if (wasPdf) {
    const prose = await pdfToProseDocx(source);
    if (!prose) {
      await quarantineRejectedSource({
        bytes: source,
        actor: input.actor,
        rejectionCode: 'PDF_NO_TEXT_LAYER',
        mimeType: PDF_MIME_TYPE,
      });
      throw new TemplateTwinDraftError(
        'PDF_NO_TEXT_LAYER',
        'This PDF has no readable text layer (it looks scanned). Upload a text-based PDF or a Word .docx, or paste the note instead.',
      );
    }
    source = prose.bytes;
    proseDirectives = prose.directives;
  }
  let ir: TemplateDocIR;
  try {
    ir = DOCX_TEMPLATE_COMPILER.compile(source);
  } catch (error) {
    const code = error instanceof TemplateDocxError ? error.code : 'DOCX_COMPILE_FAILED';
    await quarantineRejectedSource({
      bytes: source,
      actor: input.actor,
      rejectionCode: code,
    });
    throw error;
  }
  if (ir.fields.length === 0) {
    // ── S1 · UPLOAD-AND-CERTIFIED — DERIVE BEFORE QUARANTINE ──────────────────
    // A prose Word form (labels / blanks, no controls) compiled to zero fields.
    // Before quarantining, try to derive a fillable twin by inserting one control
    // per label/blank (layout preserved). The derivation SELF-VERIFIES against
    // this very compiler and returns null unless the derived package re-compiles
    // to EXACTLY the controls it added — so a wrong twin is never produced, and a
    // form we cannot derive falls through to the same NO_FILLABLE_FIELDS
    // quarantine as before. On success the derived bytes BECOME the source.
    const probe = async (bytes: Uint8Array, expected: number): Promise<boolean> => {
      try {
        return derivedTwinProbeIsValid(DOCX_TEMPLATE_COMPILER.compile(bytes), expected);
      } catch {
        return false;
      }
    };
    const derived = await deriveProseTwin(source, probe, proseDirectives);
    if (derived) {
      source = derived.bytes;
      // ⚠️ S2 ONLY (owner ruling, 2026-09-14): move each MATERIALISED fill-line
      // off the label and INTO its control's blank content, so a filled twin
      // shows the value alone — never "LABEL: ______value". Self-verifying (same
      // controls) and fail-safe: on any doubt it keeps the derived twin as-is.
      if (wasPdf) {
        const relocated = await relocateFillLinesToBlankState(source, derived.slots.length, probe);
        if (relocated) source = relocated;
      }
      ir = DOCX_TEMPLATE_COMPILER.compile(source);
    } else {
      await quarantineRejectedSource({
        bytes: source,
        actor: input.actor,
        rejectionCode: 'NO_FILLABLE_FIELDS',
      });
      throw new TemplateTwinDraftError(
        'NO_FILLABLE_FIELDS',
        'No supported fillable Word controls or table fields were detected.',
      );
    }
  }

  try {
    await assertTemplateTwinSourcePhiFree({
      source,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
  } catch (error) {
    if (error instanceof TemplateTwinPhiRejectedError) {
      await quarantineRejectedSource({
        bytes: source,
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

  // ── ATTACH, or MINT ───────────────────────────────────────────────────────
  // When attaching, the target must exist AND belong to this actor's practice.
  // Read it BEFORE any write: binding a compiled version to another tenant's
  // template would be a cross-practice disclosure, and the composite tenancy FK
  // does not cover this edge because both rows would carry the CALLER's practice.
  let attachedTemplateId: string | null = null;
  if (input.attachToNoteTemplateId) {
    // ⚠️ THROUGH THE ACCESSOR, NOT BY HAND. A literal
    // `practiceId: input.actor.practiceId` here is correct today and is still
    // the wrong shape: T5's point is that the tenancy predicate lives in ONE
    // place, so `note_templates`' ruled scope cannot drift between call sites.
    // The gate caught this as a second SYSTEM-context read in a file allowlisted
    // for exactly one — the system-default lookup, which is a genuinely
    // tenant-less query. This one is not.
    const target = await prisma.noteTemplate.findFirst({
      where: {
        id: input.attachToNoteTemplateId,
        ...templateScope(asPracticeId(input.actor.practiceId)),
      },
      select: { id: true },
    });
    if (!target) {
      throw new TemplateTwinDraftError(
        'ATTACH_TARGET_NOT_FOUND',
        'That note template does not exist in your practice.',
      );
    }
    attachedTemplateId = target.id;
  }

  // The system default and the bridge below are needed ONLY to synthesise the
  // orphan template. Attaching skips both — see `attachToNoteTemplateId`.
  const systemDefault = attachedTemplateId
    ? null
    : await prisma.noteTemplate.findFirst({
        where: { isSystemDefault: true },
        select: {
          sections: true,
          styleProfile: true,
          specialtyBaseline: true,
        },
      });
  if (!attachedTemplateId && !systemDefault) {
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
  let bridgedSections: Prisma.InputJsonValue =
    (systemDefault?.sections ?? []) as Prisma.InputJsonValue;
  let bridgedStyle: Prisma.InputJsonValue =
    (systemDefault?.styleProfile ?? {}) as Prisma.InputJsonValue;
  let bridgedName = 'Original Word template';
  let bridgeFallbackReason: string | null = null;

  if (!attachedTemplateId) try {
    const extracted = await extractNoteTextFromUpload(
      source,
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
          systemDefault?.styleProfile) as unknown as Prisma.InputJsonValue;
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
  const noteTemplateId = attachedTemplateId ?? randomUUID();
  const sourceArtifactId = randomUUID();
  const compiledVersionId = randomUUID();
  const artifactStore = input.storage ?? createTemplateTwinArtifactStore();
  const stored = await artifactStore.storeSourceArtifact({
    practiceId: input.actor.practiceId,
    lineageId,
    templateVersion: 1,
    // ⚠️ S1 — the DERIVED twin bytes when a prose form was derived (see top), so
    // the persisted source-of-truth carries the controls the compiled version and
    // every later fill/render/certify read. Identical to input.source otherwise.
    bytes: source,
  });

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      if (!attachedTemplateId) await tx.noteTemplate.create({
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
          specialtyBaseline: systemDefault!.specialtyBaseline,
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
