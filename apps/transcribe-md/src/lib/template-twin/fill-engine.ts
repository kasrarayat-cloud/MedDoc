import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import {
  renderTemplateDocx,
  type RenderTemplateDocxResult,
} from "@/lib/note-template-docx";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
  type EncounterInputMode,
} from "./encounter-facts";
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
} from "./ir";
import { templateTwinMappingsSha256 } from "./mapping-hash";
import { canonicalSoapSha256 } from "./soap-binding";
import { assertTemplateTwinSourceProvenance } from "./source-phi-evidence";
import {
  lockTemplateTwinRolloutForFinalClaim,
  templateTwinRolloutAuditMetadata,
  type LockedTemplateTwinRolloutDecision,
  type TemplateTwinRolloutCode,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  resolveTemplateFields,
  withApprovedPracticeDefaultFacts,
} from "./resolver";
import {
  claimTemplateTwinObject,
  createTemplateTwinArtifactStore,
  quarantineTemplateTwinObject,
  type TemplateTwinArtifactStore,
} from "./storage";
import { validateTemplateTwin } from "./validation";

/** The worker-owned review marker for an unresolved Template Twin fill.
 * Correction code may clear it only by exact equality after a fully verified
 * replacement, so unrelated pipeline review reasons remain untouched. */
export const TEMPLATE_TWIN_REVIEW_REASON =
  "The Original Template DOCX has unresolved fields that require clinician review before signing.";

export class TemplateTwinFillError extends Error {
  readonly code:
    | "CERTIFIED_TEMPLATE_NOT_FOUND"
    | "TEMPLATE_PROVENANCE_MISMATCH"
    | "SOURCE_ARTIFACT_UNAVAILABLE"
    | "ROLLOUT_DISABLED"
    | TemplateTwinRolloutCode
    | "SOAP_BINDING_STALE"
    | "SIGNED_MANIFEST_IMMUTABLE"
    | "MANIFEST_CONFLICT";

  constructor(
    code: TemplateTwinFillError["code"],
    message: string,
    cause?: unknown,
  ) {
    super(message, { cause });
    this.name = "TemplateTwinFillError";
    this.code = code;
  }
}

export interface PrepareTemplateTwinFillInput {
  soapVersion: number;
  soapFinal: string;
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

export interface FinalizeTemplateTwinFillInput extends Omit<
  PrepareTemplateTwinFillInput,
  "facts"
> {
  facts: ReturnType<typeof projectEncounterFacts>;
  resolutions: readonly FieldResolution[];
}

export async function finalizeTemplateTwinFill(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) =>
    SemanticMappingSchema.parse(mapping),
  );
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
    soapVersion: input.soapVersion,
    soapSha256: canonicalSoapSha256(input.soapFinal),
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
      "SOURCE_ARTIFACT_UNAVAILABLE",
      "The immutable source document is unavailable for verified rendering.",
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
  const mappings = input.mappings.map((mapping) =>
    SemanticMappingSchema.parse(mapping),
  );
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

function mappingFromRow(
  fieldId: string,
  row: PersistedMappingRow,
): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms)
      ? row.approvedSynonyms
      : [],
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

export interface LockedTemplateTwinVisit {
  id: string;
  userId: string;
  status: string;
  deletedAt: Date | null;
  archivedAt: Date | null;
  soapVersion: number;
  soapFinal: string | null;
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
}

/**
 * Locks the physician-visible SOAP source at the final relational commit
 * boundary. Rendering and immutable object storage intentionally happen
 * before this transaction; therefore the initial optimistic visit claim is
 * not sufficient to prove that those bytes still describe the current SOAP.
 */
export async function lockCurrentTemplateTwinVisit(
  tx: Prisma.TransactionClient,
  visitId: string,
): Promise<LockedTemplateTwinVisit | null> {
  const rows = await tx.$queryRaw<LockedTemplateTwinVisit[]>(Prisma.sql`
    SELECT
      "id",
      "userId",
      "status"::text AS "status",
      "deletedAt",
      "archivedAt",
      "soapVersion",
      "soapFinal",
      "noteTemplateId",
      "noteTemplateVersion"
    FROM "transcribe_visits"
    WHERE "id" = ${visitId}
    FOR UPDATE
  `);
  return rows[0] ?? null;
}

export function visitMatchesPreparedSoap(input: {
  visit: LockedTemplateTwinVisit | null;
  doctorId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  soapFinal: string;
  manifest: TemplateTwinFillManifest;
}): boolean {
  const { visit, manifest } = input;
  return Boolean(
    visit &&
    visit.userId === input.doctorId &&
    visit.status !== "SIGNED" &&
    visit.deletedAt === null &&
    visit.archivedAt === null &&
    visit.noteTemplateId === input.noteTemplateId &&
    visit.noteTemplateVersion === input.noteTemplateVersion &&
    visit.soapVersion === manifest.soapVersion &&
    typeof visit.soapFinal === "string" &&
    visit.soapFinal === input.soapFinal &&
    canonicalSoapSha256(visit.soapFinal) === manifest.soapSha256,
  );
}

export interface ProcessTemplateTwinVisitInput {
  visitId: string;
  soapVersion: number;
  soapFinal: string;
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
  asrQuality?: "high" | "review" | "unknown";
  validationNow: Date | string;
  resolverModelVersion: string | null;
  /** Exact epoch returned with the worker's selected Template Twin. It must
   * survive L4-L6 and is never replaced by a later admission token. */
  rolloutToken: TemplateTwinRolloutToken;
  storage?: TemplateTwinArtifactStore;
}

/** Resolves, independently validates, conditionally renders, stores, and
 * records one visit against its already-selected immutable template version. */
export async function processTemplateTwinVisit(
  input: ProcessTemplateTwinVisitInput,
): Promise<PreparedTemplateTwinFill> {
  const practice = await prisma.practice.findFirst({
    where: {
      id: input.practiceId,
      users: {
        some: {
          id: input.doctorId,
          role: "DOCTOR",
          isActive: true,
        },
      },
    },
    select: { id: true },
  });
  if (!practice) {
    throw new TemplateTwinFillError(
      "ROLLOUT_DISABLED",
      "Template Twin is not enabled for this practice.",
    );
  }
  const rolloutToken: TemplateTwinRolloutToken = {
    ...input.rolloutToken,
  };
  if (rolloutToken.practiceId !== input.practiceId) {
    throw new TemplateTwinFillError(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "The selected Template Twin rollout admission does not belong to this practice.",
    );
  }

  // Persist the first selected version before source I/O, resolution, model-
  // derived evidence processing, or rendering. A retry must never switch to a
  // newly activated template after partial work against this version.
  const claimedTemplate = await prisma.transcribeVisit.updateMany({
    where: {
      id: input.visitId,
      userId: input.doctorId,
      deletedAt: null,
      archivedAt: null,
      status: { not: "SIGNED" },
      soapVersion: input.soapVersion,
      soapFinal: input.soapFinal,
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
      "TEMPLATE_PROVENANCE_MISMATCH",
      "This visit is already pinned to another note template version.",
    );
  }

  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.doctorId,
      templateKind: "template_twin_docx",
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
          certification: {
            select: {
              id: true,
              approvedMappingsSha256: true,
              sourcePrivacyScanEvidenceSha256: true,
            },
          },
          sourceArtifact: {
            select: {
              practiceId: true,
              objectKey: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              sizeBytes: true,
              validationStatus: true,
              privacyScanEvidence: true,
            },
          },
          fields: {
            orderBy: { displayOrder: "asc" },
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
  if (
    !row ||
    !compiled ||
    compiled.certificationStatus !== "CERTIFIED" ||
    !compiled.certification
  ) {
    throw new TemplateTwinFillError(
      "CERTIFIED_TEMPLATE_NOT_FOUND",
      "The selected Template Twin version is not certified and active.",
    );
  }
  let sourceProvenanceValid = true;
  try {
    assertTemplateTwinSourceProvenance({
      privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
      requireBinding: true,
      boundEvidenceSha256:
        compiled.certification.sourcePrivacyScanEvidenceSha256,
    });
  } catch {
    sourceProvenanceValid = false;
  }
  if (
    row.version !== input.noteTemplateVersion ||
    compiled.sourceArtifact.practiceId !== input.practiceId ||
    compiled.sourceArtifact.validationStatus !== "accepted" ||
    !sourceProvenanceValid ||
    !compiled.sourceArtifact.objectKey ||
    !compiled.sourceArtifact.objectVersionId ||
    !compiled.sourceArtifact.objectEtag
  ) {
    throw new TemplateTwinFillError(
      "TEMPLATE_PROVENANCE_MISMATCH",
      "The selected Template Twin provenance does not match this visit.",
    );
  }
  const certifiedFieldIds: string[] = [];
  const mappings = compiled.fields.map(
    (field: {
      fieldId: string;
      detectionStatus: string;
      mapping: PersistedMappingRow | null;
    }) => {
      if (!field.mapping) {
        throw new TemplateTwinFillError(
          "TEMPLATE_PROVENANCE_MISMATCH",
          "The certified Template Twin mapping set is incomplete.",
        );
      }
      if (field.detectionStatus !== "CERTIFIED") {
        throw new TemplateTwinFillError(
          "TEMPLATE_PROVENANCE_MISMATCH",
          "The certified Template Twin field set is incomplete.",
        );
      }
      certifiedFieldIds.push(field.fieldId);
      return mappingFromRow(field.fieldId, field.mapping);
    },
  );
  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  if (
    mappings.length !== ir.fields.length ||
    templateTwinMappingsSha256(mappings) !==
      compiled.certification.approvedMappingsSha256
  ) {
    throw new TemplateTwinFillError(
      "TEMPLATE_PROVENANCE_MISMATCH",
      "The certified Template Twin mappings no longer match their certification.",
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
    expectedObjectVersionId: compiled.sourceArtifact.objectVersionId,
    expectedObjectEtag: compiled.sourceArtifact.objectEtag,
    expectedSha256: compiled.sourceArtifact.sha256,
    expectedSizeBytes: compiled.sourceArtifact.sizeBytes,
  });
  const prepared = await prepareTemplateTwinFill({
    soapVersion: input.soapVersion,
    soapFinal: input.soapFinal,
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
      soapVersion: true,
      soapSha256: true,
      manifestVersion: true,
      manifestSha256: true,
      roundTripVerified: true,
      pinnedGlobalRolloutGeneration: true,
      pinnedPracticeRolloutGeneration: true,
    },
  });
  if (
    existing &&
    (existing.status === "SIGNED" || existing.signedDecisionAt !== null)
  ) {
    throw new TemplateTwinFillError(
      "SIGNED_MANIFEST_IMMUTABLE",
      "A signed Template Twin fill manifest cannot be replaced.",
    );
  }
  if (
    existing?.manifestSha256 === prepared.manifestSha256 &&
    existing.pinnedGlobalRolloutGeneration === rolloutToken.globalGeneration &&
    existing.pinnedPracticeRolloutGeneration ===
      rolloutToken.practiceGeneration &&
    (prepared.render === null || existing.roundTripVerified)
  ) {
    return prepared;
  }
  const reviewedManifestWasInvalidatedBySoapEdit = Boolean(
    existing?.reviewedAt != null &&
    existing.status === "NEEDS_REVIEW" &&
    (existing.soapVersion !== prepared.manifest.soapVersion ||
      existing.soapSha256 !== prepared.manifest.soapSha256),
  );
  if (
    existing?.reviewedAt != null &&
    !reviewedManifestWasInvalidatedBySoapEdit
  ) {
    throw new TemplateTwinFillError(
      "MANIFEST_CONFLICT",
      "A clinician-reviewed Template Twin fill cannot be replaced by a worker retry.",
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
  const status = prepared.render ? "VERIFIED" : "NEEDS_REVIEW";
  const renderAuditEventKey = storedOutput
    ? `template-twin:render-verified:${canonicalSha256({
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        outputObjectKey: storedOutput.objectKey,
      })}`
    : null;
  const safetyGateEventKey = !prepared.render
    ? `template-twin:safety-gate-blocked:${canonicalSha256({
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        blockerCodes: prepared.manifest.validation.issues
          .filter((issue) => issue.severity === "blocking")
          .map((issue) => issue.code)
          .sort(),
      })}`
    : null;
  const soapBindingStaleEventKey = `template-twin:soap-binding-stale:${canonicalSha256(
    {
      visitId: input.visitId,
      manifestSha256: prepared.manifestSha256,
      soapVersion: prepared.manifest.soapVersion,
    },
  )}`;
  const enqueueRenderVerifiedAudit = async (
    tx: Prisma.TransactionClient,
  ): Promise<void> => {
    if (!storedOutput || !prepared.render || !renderAuditEventKey) return;
    await enqueueTemplateTwinAudit(tx, {
      eventKey: renderAuditEventKey,
      practiceId: input.practiceId,
      actorId: input.doctorId,
      action: "TEMPLATE_TWIN_RENDER_VERIFIED",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      metadata: {
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        rendererVersion: prepared.render.rendererVersion,
        outputSha256: storedOutput.sha256,
        outputVersionId: storedOutput.objectVersionId,
        outputEtag: storedOutput.objectEtag,
        manifestSha256: prepared.manifestSha256,
        fieldCount: prepared.manifest.counts.filled,
      },
    });
  };
  const enqueueSafetyGateAudit = async (
    tx: Prisma.TransactionClient,
  ): Promise<void> => {
    if (!safetyGateEventKey || prepared.render) return;
    const blockingIssues = prepared.manifest.validation.issues.filter(
      (issue) => issue.severity === "blocking",
    );
    await enqueueTemplateTwinAudit(tx, {
      eventKey: safetyGateEventKey,
      practiceId: input.practiceId,
      actorId: input.doctorId,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      metadata: {
        reasonCode: "FIELD_VALIDATION_BLOCKED_RENDER",
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        manifestSha256: prepared.manifestSha256,
        blockerCodes: [
          ...new Set(blockingIssues.map((issue) => issue.code)),
        ].sort(),
        blockerCount: blockingIssues.length,
        affectedFieldIds: [
          ...new Set(
            blockingIssues.flatMap((issue) =>
              issue.fieldId === null ? [] : [issue.fieldId],
            ),
          ),
        ].sort(),
      },
    });
  };
  const quarantineStaleOutput = async (
    tx: Prisma.TransactionClient,
  ): Promise<void> => {
    if (!storedOutput) return;
    await quarantineTemplateTwinObject(tx, {
      objectKey: storedOutput.objectKey,
      practiceId: input.practiceId,
      objectVersionId: storedOutput.objectVersionId,
      objectEtag: storedOutput.objectEtag,
      reasonCode: "SOAP_BINDING_STALE",
    });
  };
  const enqueueSoapBindingStaleAudit = async (
    tx: Prisma.TransactionClient,
    currentSoapVersion: number | null,
  ): Promise<void> => {
    await enqueueTemplateTwinAudit(tx, {
      eventKey: soapBindingStaleEventKey,
      practiceId: input.practiceId,
      actorId: input.doctorId,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      metadata: {
        reasonCode: "SOAP_BINDING_STALE",
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        manifestSha256: prepared.manifestSha256,
        expectedSoapVersion: prepared.manifest.soapVersion,
        currentSoapVersion,
        outputQuarantined: storedOutput !== null,
      },
    });
  };
  const enqueueRolloutRejectedAudit = async (
    tx: Prisma.TransactionClient,
    decision: Exclude<LockedTemplateTwinRolloutDecision, { allowed: true }>,
  ): Promise<void> => {
    await enqueueTemplateTwinAudit(tx, {
      eventKey: `template-twin:rollout-final-claim-blocked:${canonicalSha256({
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        reasonCode: decision.code,
        ...templateTwinRolloutAuditMetadata(
          rolloutToken,
          decision.currentToken,
        ),
      })}`,
      practiceId: input.practiceId,
      actorId: input.doctorId,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      metadata: {
        reasonCode: decision.code,
        operation: "final_output_claim",
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        manifestSha256: prepared.manifestSha256,
        outputWrittenUnclaimed: storedOutput !== null,
        ...templateTwinRolloutAuditMetadata(
          rolloutToken,
          decision.currentToken,
        ),
      },
    });
  };
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
    soapVersion: prepared.manifest.soapVersion,
    soapSha256: prepared.manifest.soapSha256,
    validationResult: asJson(prepared.manifest.validation),
    filledCount: prepared.manifest.counts.filled,
    needsReviewCount: prepared.manifest.counts.needsReview,
    notMentionedCount: prepared.manifest.counts.notMentioned,
    conflictCount: prepared.manifest.counts.conflicts,
    criticalUnresolvedCount: prepared.manifest.counts.criticalUnresolved,
    outputObjectKey: storedOutput?.objectKey ?? null,
    outputVersionId: storedOutput?.objectVersionId ?? null,
    outputEtag: storedOutput?.objectEtag ?? null,
    outputSha256: storedOutput?.sha256 ?? null,
    outputMimeType: storedOutput?.mimeType ?? null,
    outputSizeBytes: storedOutput?.sizeBytes ?? null,
    staticContentSha256: prepared.render ? ir.staticContentSha256 : null,
    roundTripVerified: prepared.render?.verification.verified === true,
    roundTripVerification: prepared.render
      ? asJson(prepared.render.verification)
      : Prisma.JsonNull,
    pinnedGlobalRolloutGeneration: rolloutToken.globalGeneration,
    pinnedPracticeRolloutGeneration: rolloutToken.practiceGeneration,
    signedGlobalRolloutGeneration: null,
    signedPracticeRolloutGeneration: null,
    // Regeneration creates a new review boundary. Prior physician decisions
    // remain append-only rows, but they cannot authorize the new SOAP-bound
    // manifest without a fresh review.
    reviewedAt: null,
    reviewedById: null,
    reviewedManifestVersion: null,
    reviewedManifestSha256: null,
  } as const;

  if (existing) {
    // Signing and clinician correction both use optimistic claims. The worker
    // must claim the exact unsigned row it observed; a signed or concurrently
    // replaced row produces no update and remains untouched.
    const updated = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId: input.practiceId,
          pinnedToken: rolloutToken,
        });
        if (!finalRollout.allowed) {
          await enqueueRolloutRejectedAudit(tx, finalRollout);
          return {
            count: 0,
            soapBindingStale: false,
            rolloutRejected: finalRollout,
          } as const;
        }
        const lockedVisit = await lockCurrentTemplateTwinVisit(
          tx,
          input.visitId,
        );
        if (
          !visitMatchesPreparedSoap({
            visit: lockedVisit,
            doctorId: input.doctorId,
            noteTemplateId: row.id,
            noteTemplateVersion: row.version,
            soapFinal: input.soapFinal,
            manifest: prepared.manifest,
          })
        ) {
          await quarantineStaleOutput(tx);
          await tx.templateTwinFillManifest.updateMany({
            where: {
              id: existing.id,
              status: { not: "SIGNED" },
              signedDecisionAt: null,
              reviewedAt: existing.reviewedAt,
              soapVersion: existing.soapVersion,
              soapSha256: existing.soapSha256,
              manifestVersion: existing.manifestVersion,
              manifestSha256: existing.manifestSha256,
            },
            data: {
              status: "NEEDS_REVIEW",
              reviewedAt: null,
              reviewedById: null,
              reviewedManifestVersion: null,
              reviewedManifestSha256: null,
            },
          });
          await enqueueSoapBindingStaleAudit(
            tx,
            lockedVisit?.soapVersion ?? null,
          );
          return {
            count: 0,
            soapBindingStale: true,
            rolloutRejected: null,
          } as const;
        }
        const claimedManifest = await tx.templateTwinFillManifest.updateMany({
          where: {
            id: existing.id,
            status: { not: "SIGNED" },
            signedDecisionAt: null,
            reviewedAt: existing.reviewedAt,
            soapVersion: existing.soapVersion,
            soapSha256: existing.soapSha256,
            manifestVersion: existing.manifestVersion,
            manifestSha256: existing.manifestSha256,
          },
          data: {
            ...writeData,
            manifestVersion: { increment: 1 },
          },
        });
        if (claimedManifest.count === 1 && storedOutput) {
          await claimTemplateTwinObject(tx, {
            objectKey: storedOutput.objectKey,
            practiceId: input.practiceId,
            claimType: "fill_manifest",
            claimId: existing.id,
          });
          await enqueueRenderVerifiedAudit(tx);
        }
        if (claimedManifest.count === 1 && !storedOutput) {
          await enqueueSafetyGateAudit(tx);
        }
        return {
          ...claimedManifest,
          soapBindingStale: false,
          rolloutRejected: null,
        } as const;
      },
      { isolationLevel: "Serializable" },
    );
    if (updated.soapBindingStale) {
      throw new TemplateTwinFillError(
        "SOAP_BINDING_STALE",
        "The SOAP note changed while the Original Template DOCX was being generated. Regenerate and review it before signing.",
      );
    }
    if (updated.rolloutRejected) {
      throw new TemplateTwinFillError(
        updated.rolloutRejected.code,
        updated.rolloutRejected.reason,
      );
    }
    if (updated.count !== 1) {
      const current = await prisma.templateTwinFillManifest.findUnique({
        where: { visitId: input.visitId },
        select: { status: true, signedDecisionAt: true },
      });
      if (
        current &&
        (current.status === "SIGNED" || current.signedDecisionAt !== null)
      ) {
        throw new TemplateTwinFillError(
          "SIGNED_MANIFEST_IMMUTABLE",
          "A signed Template Twin fill manifest cannot be replaced.",
        );
      }
      throw new TemplateTwinFillError(
        "MANIFEST_CONFLICT",
        "The Template Twin fill changed concurrently and was not replaced.",
      );
    }
  } else {
    try {
      const createdResult = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
            tx,
            practiceId: input.practiceId,
            pinnedToken: rolloutToken,
          });
          if (!finalRollout.allowed) {
            await enqueueRolloutRejectedAudit(tx, finalRollout);
            return {
              soapBindingStale: false,
              rolloutRejected: finalRollout,
            } as const;
          }
          const lockedVisit = await lockCurrentTemplateTwinVisit(
            tx,
            input.visitId,
          );
          if (
            !visitMatchesPreparedSoap({
              visit: lockedVisit,
              doctorId: input.doctorId,
              noteTemplateId: row.id,
              noteTemplateVersion: row.version,
              soapFinal: input.soapFinal,
              manifest: prepared.manifest,
            })
          ) {
            await quarantineStaleOutput(tx);
            await enqueueSoapBindingStaleAudit(
              tx,
              lockedVisit?.soapVersion ?? null,
            );
            return {
              soapBindingStale: true,
              rolloutRejected: null,
            } as const;
          }
          const created = await tx.templateTwinFillManifest.create({
            data: {
              practiceId: input.practiceId,
              visitId: input.visitId,
              ...writeData,
            },
            select: { id: true },
          });
          if (storedOutput) {
            await claimTemplateTwinObject(tx, {
              objectKey: storedOutput.objectKey,
              practiceId: input.practiceId,
              claimType: "fill_manifest",
              claimId: created.id,
            });
            await enqueueRenderVerifiedAudit(tx);
          } else {
            await enqueueSafetyGateAudit(tx);
          }
          return {
            soapBindingStale: false,
            rolloutRejected: null,
          } as const;
        },
        { isolationLevel: "Serializable" },
      );
      if (createdResult.soapBindingStale) {
        throw new TemplateTwinFillError(
          "SOAP_BINDING_STALE",
          "The SOAP note changed while the Original Template DOCX was being generated. Regenerate and review it before signing.",
        );
      }
      if (createdResult.rolloutRejected) {
        throw new TemplateTwinFillError(
          createdResult.rolloutRejected.code,
          createdResult.rolloutRejected.reason,
        );
      }
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        (error.code === "P2002" || error.code === "P2034")
      ) {
        throw new TemplateTwinFillError(
          "MANIFEST_CONFLICT",
          "Another worker created the Template Twin fill first.",
          error,
        );
      }
      throw error;
    }
  }

  return prepared;
}
