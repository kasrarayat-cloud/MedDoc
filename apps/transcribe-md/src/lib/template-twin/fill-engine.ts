import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";
import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
} from "@meddoc/ai";

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
  TemplateTwinValidationResultSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinEncounterSourceReceipt,
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
import type { TemplateTwinConceptProvider } from "./supported-concepts";
import type { CertifiedTemplateFieldSpecification } from "./custom-concepts/specification";
import {
  buildCanonicalCustomConceptEvidence,
  createCertifiedCustomConceptProvider,
  customConceptProviderOperationInstance,
  extractCertifiedCustomConcepts,
  TEMPLATE_CUSTOM_EXTRACTION_DEFAULT_MODEL,
  type CertifiedCustomExtractionProvenance,
  type CustomConceptFieldOutcome,
} from "./custom-concepts";
import { assertTemplateTwinCustomExamplesReadyForCertification } from "./custom-example-service";
import {
  customConceptSpecifications,
  fieldRequiresExplicitIntent,
  fieldsWithCertifiedCustomIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
} from "./field-intent";
import { verifyCustomExtractionOutcomeProof } from "./custom-outcome-proof";
import { TemplateTwinStagingQaDisabledError } from "./staging-qa-gate";
import {
  lockAndAssertTemplateTwinStagingQaAttempt,
  TemplateTwinStagingQaVisitGuardError,
  type TemplateTwinSyntheticQaAttemptClaim,
} from "./staging-qa-visit-guard";
import { runTemplateTwinSyntheticQaClaimBoundMutation } from "@/worker/staging-qa-mutation-fence";
import {
  isTemplateTwinRollbackCompatRuntime,
  templateTwinRuntimeEnabled,
} from "@/lib/runtime-protocol";
import { createTemplateTwinEncounterSourceReceipt } from "./canonical-encounter-source";
import { isTemplateTwinSourceAdmissionCurrent } from "./source-admission";
import {
  isTemplateTwinLiveProviderCompilationOwned,
  isTemplateTwinStagingProviderCompilationOwned,
} from "./live-provider-ownership";
import {
  buildTemplateTwinProviderOwnershipReceipt,
  getTemplateTwinProviderOwnershipContext,
  getTemplateTwinProviderPlanDisposition,
  recordTemplateTwinProviderNotApplicable,
  TemplateTwinProviderOwnershipError,
  type TemplateTwinProviderExpectedPlanEntry,
} from "./provider-ownership";

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
    | "MANIFEST_CONFLICT"
    | "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE";

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
  encounterSourceReceipt?: TemplateTwinEncounterSourceReceipt | null;
  validationNow: Date | string;
  allowUncertifiedForSyntheticTest?: boolean;
  fieldIntentsSha256?: string | null;
  customExampleProofSha256?: string | null;
  staticFieldIds?: readonly string[];
  conceptProviders?: readonly TemplateTwinConceptProvider[];
  customExtraction?:
    | (CertifiedCustomExtractionProvenance & {
        readonly fields?: readonly Omit<
          CustomConceptFieldOutcome,
          "value" | "unit"
        >[];
        readonly blocksSigning?: boolean;
      })
    | null;
  effectiveFields?: readonly TemplateField[];
  customSpecifications?: readonly CertifiedTemplateFieldSpecification[];
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

function applyCustomExtractionValidation(input: {
  validation: ReturnType<typeof validateTemplateTwin>;
  extraction: PrepareTemplateTwinFillInput["customExtraction"];
  specifications: readonly CertifiedTemplateFieldSpecification[];
  resolutions: readonly FieldResolution[];
  facts: ReturnType<typeof projectEncounterFacts>;
}) {
  const issues = [...input.validation.issues];
  const add = (fieldId: string | null, code: string, message: string) => {
    issues.push({ fieldId, code, severity: "blocking" as const, message });
  };
  for (const issue of verifyCustomExtractionOutcomeProof({
    specifications: input.specifications,
    proof: input.extraction
      ? {
          ...input.extraction,
          fields: (input.extraction.fields ?? []).map((field) => ({
            ...field,
            sourceFactIds: [...field.sourceFactIds],
            evidenceAnchorIds: [...field.evidenceAnchorIds],
          })),
          blocksSigning: input.extraction.blocksSigning ?? false,
        }
      : null,
    resolutions: input.resolutions,
    facts: input.facts,
  })) {
    add(issue.fieldId, issue.code, issue.message);
  }
  return TemplateTwinValidationResultSchema.parse({
    ...input.validation,
    valid: issues.every((issue) => issue.severity !== "blocking"),
    issues,
  });
}

export async function finalizeTemplateTwinFill(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) =>
    SemanticMappingSchema.parse(mapping),
  );
  const fields = [...input.resolutions];
  const definitions = input.effectiveFields ?? ir.fields;
  const independentValidation = validateTemplateTwin({
    fields: definitions,
    mappings,
    facts: input.facts,
    resolutions: fields,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
    staticFieldIds: input.staticFieldIds,
    conceptProviders: input.conceptProviders,
    customSpecifications: input.customSpecifications,
    now: input.validationNow,
  });
  const validation = applyCustomExtractionValidation({
    validation: independentValidation,
    extraction: input.customExtraction,
    specifications: input.customSpecifications ?? [],
    resolutions: fields,
    facts: input.facts,
  });
  const counts = templateTwinCounts(fields, definitions);
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
    encounterSourceReceipt: input.encounterSourceReceipt ?? null,
    fieldIntentsSha256: input.fieldIntentsSha256 ?? null,
    customExampleProofSha256: input.customExampleProofSha256 ?? null,
    customExtraction: input.customExtraction
      ? {
          extractorVersion: input.customExtraction.extractorVersion,
          extractionSchemaVersion:
            input.customExtraction.extractionSchemaVersion,
          extractionSchemaHash: input.customExtraction.extractionSchemaHash,
          provider: input.customExtraction.provider,
          model: input.customExtraction.model,
          fields: (input.customExtraction.fields ?? []).map((outcome) => ({
            fieldId: outcome.fieldId,
            conceptId: outcome.conceptId,
            status: outcome.status,
            sourceFactIds: [...outcome.sourceFactIds],
            evidenceAnchorIds: [...outcome.evidenceAnchorIds],
            reasonCode: outcome.reasonCode,
            needsClinicianReview: outcome.needsClinicianReview,
            blocksSigning: outcome.blocksSigning,
          })),
          blocksSigning: input.customExtraction.blocksSigning ?? false,
        }
      : null,
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
    effectiveFields: definitions,
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
    fields: input.effectiveFields ?? ir.fields,
    mappings,
    facts: input.facts,
  });
  const resolvedFields = resolveTemplateFields({
    fields: input.effectiveFields ?? ir.fields,
    mappings,
    facts,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
    staticFieldIds: input.staticFieldIds,
    conceptProviders: input.conceptProviders,
    customSpecifications: input.customSpecifications,
  });
  const outcomeByFieldId = new Map(
    (input.customExtraction?.fields ?? []).map((outcome) => [
      outcome.fieldId,
      outcome,
    ]),
  );
  const fields = resolvedFields.map((resolution) => {
    const outcome = outcomeByFieldId.get(resolution.fieldId);
    if (!outcome) return resolution;
    if (outcome.status === "ambiguous" || outcome.status === "unknown") {
      return {
        fieldId: resolution.fieldId,
        status: "ambiguous" as const,
        value: null,
        sourceFactIds: [...outcome.sourceFactIds],
        evidenceAnchorIds: [...outcome.evidenceAnchorIds],
        selectedOptionOrdinal: null,
        reasonCode: outcome.reasonCode,
        clinicianReviewed: false,
      };
    }
    if (outcome.status === "conflict") {
      return {
        fieldId: resolution.fieldId,
        status: "conflict" as const,
        value: null,
        sourceFactIds: [...outcome.sourceFactIds],
        evidenceAnchorIds: [...outcome.evidenceAnchorIds],
        selectedOptionOrdinal: null,
        reasonCode: outcome.reasonCode,
        clinicianReviewed: false,
      };
    }
    return resolution;
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

type PersistedIntentDecisionRow = Omit<
  PersistedTemplateTwinFieldIntent,
  "fieldDefinitionId" | "fieldId"
>;

interface PersistedFieldWithIntent {
  id: string;
  fieldId: string;
  detectionStatus: string;
  intentDecisions: PersistedIntentDecisionRow[];
  mapping: PersistedMappingRow | null;
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
  patientId: string;
  status: string;
  deletedAt: Date | null;
  archivedAt: Date | null;
  soapVersion: number;
  soapFinal: string | null;
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
  inputMode: string;
  rawTextInput: string | null;
  transcriptText: string | null;
  transcriptRaw: unknown;
  speakerMap: unknown;
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
      "patientId",
      "status"::text AS "status",
      "deletedAt",
      "archivedAt",
      "soapVersion",
      "soapFinal",
      "noteTemplateId",
      "noteTemplateVersion",
      "inputMode",
      "rawTextInput",
      "transcriptText",
      "transcriptRaw",
      "speakerMap"
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
  if (!templateTwinRuntimeEnabled(process.env)) {
    const rollbackCompat = isTemplateTwinRollbackCompatRuntime(process.env);
    throw new TemplateTwinFillError(
      rollbackCompat
        ? "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE"
        : "TEMPLATE_TWIN_RUNTIME_MODE_INVALID",
      rollbackCompat
        ? "Template Twin provider work is unavailable in this runtime mode."
        : "Template Twin runtime configuration is invalid.",
    );
  }
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
  const syntheticQaContext = getTemplateTwinSyntheticQaProviderContext();
  const syntheticQaAttempt: TemplateTwinSyntheticQaAttemptClaim | null =
    syntheticQaContext
      ? {
          runId: syntheticQaContext.runId,
          visitId: syntheticQaContext.visitId,
          practiceId: syntheticQaContext.practiceId,
          doctorId: input.doctorId,
          fixtureVersion: syntheticQaContext.fixtureVersion,
          requestSha256: syntheticQaContext.requestSha256,
          attempt: syntheticQaContext.attempt,
          workerClaimId: syntheticQaContext.workerClaimId,
          pinnedGlobalGeneration: syntheticQaContext.pinnedGlobalGeneration,
          pinnedPracticeGeneration: syntheticQaContext.pinnedPracticeGeneration,
        }
      : null;
  if (
    syntheticQaAttempt &&
    (syntheticQaAttempt.visitId !== input.visitId ||
      syntheticQaAttempt.practiceId !== input.practiceId)
  ) {
    throw new TemplateTwinFillError(
      "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      "Synthetic QA worker context does not match this Template Twin fill.",
    );
  }
  const syntheticParentAdmissionId = syntheticQaContext
    ? ((
        await prisma.templateTwinSyntheticQaAdmission.findUnique({
          where: { id: syntheticQaContext.admissionId },
          select: { parentAdmissionId: true },
        })
      )?.parentAdmissionId ?? null)
    : null;
  if (syntheticQaContext && !syntheticParentAdmissionId) {
    throw new TemplateTwinFillError(
      "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      "Synthetic QA provider admission is not bound to its certified upload admission.",
    );
  }

  // Persist the first selected version before source I/O, resolution, model-
  // derived evidence processing, or rendering. A retry must never switch to a
  // newly activated template after partial work against this version.
  const claimedTemplate = await runTemplateTwinSyntheticQaClaimBoundMutation({
    visitId: input.visitId,
    userId: input.doctorId,
    practiceId: input.practiceId,
    requireOrdinaryProcessingStatus: false,
    mutate: (client) =>
      client.transcribeVisit.updateMany({
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
      }),
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
          providerOwnershipEvidence: true,
          providerOwnershipSha256: true,
          certification: {
            select: {
              id: true,
              approvedMappingsSha256: true,
              approvedFieldIntentsSha256: true,
              approvedCustomExampleProofSha256: true,
              sourcePrivacyScanEvidenceSha256: true,
            },
          },
          sourceArtifact: {
            select: {
              id: true,
              practiceId: true,
              lineageId: true,
              lineageVersion: true,
              objectKey: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              sizeBytes: true,
              validationStatus: true,
              privacyScanEvidence: true,
              providerOwnershipEvidence: true,
              providerOwnershipSha256: true,
              quarantineArtifact: {
                select: {
                  practiceId: true,
                  lineageId: true,
                  intakeMode: true,
                  sha256: true,
                  sizeBytes: true,
                  status: true,
                  malwareScanEvidence: true,
                  metadataMinimizationEvidence: true,
                  rejectionCodes: true,
                  scannedAt: true,
                  admittedAt: true,
                },
              },
            },
          },
          fields: {
            orderBy: { displayOrder: "asc" },
            select: {
              id: true,
              fieldId: true,
              detectionStatus: true,
              intentDecisions: {
                orderBy: { version: "desc" },
                take: 1,
                select: {
                  id: true,
                  version: true,
                  intentKind: true,
                  supportedConcept: true,
                  customConceptId: true,
                  customSpec: true,
                  customSpecSha256: true,
                  reason: true,
                  decidedById: true,
                  decidedAt: true,
                },
              },
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
    !(syntheticQaAttempt
      ? isTemplateTwinStagingProviderCompilationOwned({
          practiceId: input.practiceId,
          actorUserId: input.doctorId,
          noteTemplateId: row.id,
          noteTemplateVersion: row.version,
          compiledVersionId: compiled.id,
          sourceArtifactId: compiled.sourceArtifact.id,
          sourceLineageId: compiled.sourceArtifact.lineageId,
          sourceLineageVersion: compiled.sourceArtifact.lineageVersion,
          sourceSha256: compiled.sourceArtifact.sha256,
          sourceProviderOwnershipEvidence:
            compiled.sourceArtifact.providerOwnershipEvidence,
          sourceProviderOwnershipSha256:
            compiled.sourceArtifact.providerOwnershipSha256,
          compiledProviderOwnershipEvidence: compiled.providerOwnershipEvidence,
          compiledProviderOwnershipSha256: compiled.providerOwnershipSha256,
          expectedSyntheticAdmissionId: syntheticParentAdmissionId!,
        })
      : isTemplateTwinLiveProviderCompilationOwned({
          practiceId: input.practiceId,
          actorUserId: input.doctorId,
          noteTemplateId: row.id,
          noteTemplateVersion: row.version,
          compiledVersionId: compiled.id,
          sourceArtifactId: compiled.sourceArtifact.id,
          sourceLineageId: compiled.sourceArtifact.lineageId,
          sourceLineageVersion: compiled.sourceArtifact.lineageVersion,
          sourceSha256: compiled.sourceArtifact.sha256,
          sourceProviderOwnershipEvidence:
            compiled.sourceArtifact.providerOwnershipEvidence,
          sourceProviderOwnershipSha256:
            compiled.sourceArtifact.providerOwnershipSha256,
          compiledProviderOwnershipEvidence: compiled.providerOwnershipEvidence,
          compiledProviderOwnershipSha256: compiled.providerOwnershipSha256,
        })) ||
    !isTemplateTwinSourceAdmissionCurrent(compiled.sourceArtifact) ||
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
  const persistedFields = compiled.fields as PersistedFieldWithIntent[];
  const certifiedFieldIds: string[] = [];
  const mappings = persistedFields.map((field) => {
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
  });
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
  const persistedFieldById = new Map(
    persistedFields.map((field) => [field.fieldId, field]),
  );
  const explicitIntents = ir.fields
    .filter(fieldRequiresExplicitIntent)
    .map((field) => {
      const persisted = persistedFieldById.get(field.fieldId);
      if (!persisted) {
        throw new TemplateTwinFillError(
          "TEMPLATE_PROVENANCE_MISMATCH",
          "A certified placeholder field has no intent definition.",
        );
      }
      const decision = persisted.intentDecisions[0];
      return {
        fieldId: field.fieldId,
        intent: decision
          ? parsePersistedFieldIntent({
              ...decision,
              fieldDefinitionId: persisted.id,
              fieldId: field.fieldId,
            } satisfies PersistedTemplateTwinFieldIntent)
          : unresolvedFieldIntent(),
      };
    });
  const fieldIntentsSha256 = templateTwinFieldIntentsSha256(explicitIntents);
  if (
    !compiled.certification.approvedFieldIntentsSha256 ||
    compiled.certification.approvedFieldIntentsSha256 !== fieldIntentsSha256 ||
    explicitIntents.some((entry) => entry.intent.intentKind === "unresolved")
  ) {
    throw new TemplateTwinFillError(
      "TEMPLATE_PROVENANCE_MISMATCH",
      "The certified placeholder intents no longer match their certification.",
    );
  }
  const customSpecifications = customConceptSpecifications(explicitIntents);
  const customConceptOperationInstance =
    customConceptProviderOperationInstance(customSpecifications);
  const customExtractionModel =
    input.resolverModelVersion ?? TEMPLATE_CUSTOM_EXTRACTION_DEFAULT_MODEL;
  let customExampleProofSha256: string | null = null;
  if (customSpecifications.length > 0) {
    customExampleProofSha256 =
      await assertTemplateTwinCustomExamplesReadyForCertification({
        tx: prisma,
        compiledVersionId: compiled.id,
        specifications: customSpecifications,
        mappingsSha256: templateTwinMappingsSha256(mappings),
        fieldIntentsSha256,
        physicianUserId: input.doctorId,
        expectedModel: customExtractionModel,
      });
    if (
      !compiled.certification.approvedCustomExampleProofSha256 ||
      customExampleProofSha256 !==
        compiled.certification.approvedCustomExampleProofSha256
    ) {
      throw new TemplateTwinFillError(
        "TEMPLATE_PROVENANCE_MISMATCH",
        "The physician-reviewed custom-field examples no longer match this certification.",
      );
    }
  } else if (compiled.certification.approvedCustomExampleProofSha256 !== null) {
    throw new TemplateTwinFillError(
      "TEMPLATE_PROVENANCE_MISMATCH",
      "A custom-field example proof exists without a certified custom field.",
    );
  }
  const conceptProviders =
    customSpecifications.length > 0
      ? [createCertifiedCustomConceptProvider(customSpecifications)]
      : [];
  const staticFieldIds = explicitIntents.flatMap((entry) =>
    entry.intent.intentKind === "static" ? [entry.fieldId] : [],
  );
  const effectiveFields = fieldsWithCertifiedCustomIntent({
    fields: ir.fields,
    intents: explicitIntents,
  });
  const projectedFacts = projectEncounterFacts({
    mode: input.inputMode,
    contextText: input.contextText,
    entities: input.entities as EncounterEntitySnapshot,
    asrQuality: input.asrQuality,
  });
  const customExtraction =
    customSpecifications.length > 0
      ? await extractCertifiedCustomConcepts({
          specifications: customSpecifications,
          evidence: buildCanonicalCustomConceptEvidence({
            mode: input.inputMode,
            contextText: input.contextText,
            asrQuality: input.asrQuality,
          }),
          practiceId: input.practiceId,
          visitId: input.visitId,
          userId: input.doctorId,
          model: customExtractionModel,
        })
      : null;
  const facts = [...projectedFacts, ...(customExtraction?.facts ?? [])];
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
    encounterSourceReceipt: createTemplateTwinEncounterSourceReceipt({
      mode: input.inputMode,
      contextText: input.contextText,
    }),
    fieldIntentsSha256,
    customExampleProofSha256,
    staticFieldIds,
    conceptProviders,
    customExtraction,
    effectiveFields,
    customSpecifications,
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
      providerOwnershipSha256: true,
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
  const providerContext = getTemplateTwinProviderOwnershipContext();
  if (
    !providerContext ||
    providerContext.scope !== "VISIT_PIPELINE" ||
    providerContext.practiceId !== input.practiceId ||
    providerContext.actorUserId !== input.doctorId ||
    providerContext.visitId !== input.visitId ||
    providerContext.sourceArtifactId !== compiled.sourceArtifact.id ||
    providerContext.compiledVersionId !== compiled.id ||
    providerContext.noteTemplateId !== row.id ||
    providerContext.noteTemplateVersion !== row.version
  ) {
    throw new TemplateTwinProviderOwnershipError(
      "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    );
  }
  if (customSpecifications.length === 0) {
    await recordTemplateTwinProviderNotApplicable({
      operation: "CUSTOM_CONCEPT_EXTRACTION",
      operationInstance: customConceptOperationInstance,
      reasonCode: "NO_CERTIFIED_CUSTOM_SPECIFICATIONS",
    });
  }
  const inputModePlan: TemplateTwinProviderExpectedPlanEntry[] =
    input.inputMode === "conversation"
      ? [
          { operation: "L1_TRANSCRIBE", disposition: "EXECUTED" },
          {
            operation: "L1B_TRANSCRIBE",
            disposition: "NOT_APPLICABLE",
            reasonCode: "INPUT_MODE_CONVERSATION",
          },
          { operation: "L2_SPEAKER_ROLES", disposition: "EXECUTED" },
        ]
      : input.inputMode === "dictation"
        ? [
            {
              operation: "L1_TRANSCRIBE",
              disposition: "NOT_APPLICABLE",
              reasonCode: "INPUT_MODE_DICTATION",
            },
            { operation: "L1B_TRANSCRIBE", disposition: "EXECUTED" },
            {
              operation: "L2_SPEAKER_ROLES",
              disposition: "NOT_APPLICABLE",
              reasonCode: "INPUT_MODE_DICTATION",
            },
          ]
        : [
            {
              operation: "L1_TRANSCRIBE",
              disposition: "NOT_APPLICABLE",
              reasonCode: "INPUT_MODE_TEXT",
            },
            {
              operation: "L1B_TRANSCRIBE",
              disposition: "NOT_APPLICABLE",
              reasonCode: "INPUT_MODE_TEXT",
            },
            {
              operation: "L2_SPEAKER_ROLES",
              disposition: "NOT_APPLICABLE",
              reasonCode: "INPUT_MODE_TEXT",
            },
          ];
  const anchorPlan = [1, 2, 3].map((pass) =>
    getTemplateTwinProviderPlanDisposition({
      operation: "L4_ANCHOR_VERIFY",
      operationInstance: `ensemble-pass-${pass}`,
    }),
  );
  const anchorDisposition = anchorPlan[0];
  if (
    anchorPlan.some(
      (entry) =>
        entry.disposition !== anchorDisposition.disposition ||
        entry.reasonCode !== anchorDisposition.reasonCode,
    ) ||
    (anchorDisposition.disposition === "NOT_APPLICABLE" &&
      ![
        "EVIDENCE_ANCHORS_DISABLED",
        "NO_ANCHORED_CLAIMS",
        "DETERMINISTIC_ANCHOR_MOCK",
      ].includes(anchorDisposition.reasonCode ?? ""))
  ) {
    throw new TemplateTwinProviderOwnershipError(
      "TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE",
    );
  }
  const polishPlan = getTemplateTwinProviderPlanDisposition({
    operation: "L6_POLISH",
  });
  const fidelityPlan = getTemplateTwinProviderPlanDisposition({
    operation: "L6_FIDELITY_VERIFY",
  });
  if (
    (polishPlan.disposition === "NOT_APPLICABLE" &&
      (polishPlan.reasonCode !== "NO_FIXABLE_CRITIQUE_WORK" ||
        fidelityPlan.disposition !== "NOT_APPLICABLE" ||
        fidelityPlan.reasonCode !== "POLISH_NOT_EXECUTED")) ||
    (polishPlan.disposition === "EXECUTED" &&
      fidelityPlan.disposition === "NOT_APPLICABLE" &&
      fidelityPlan.reasonCode !== "EMPTY_POLISH_OUTPUT")
  ) {
    throw new TemplateTwinProviderOwnershipError(
      "TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE",
    );
  }
  const customConceptPlan: TemplateTwinProviderExpectedPlanEntry =
    customSpecifications.length > 0
      ? {
          operation: "CUSTOM_CONCEPT_EXTRACTION",
          operationInstance: customConceptOperationInstance,
          disposition: "EXECUTED",
        }
      : {
          operation: "CUSTOM_CONCEPT_EXTRACTION",
          operationInstance: customConceptOperationInstance,
          disposition: "NOT_APPLICABLE",
          reasonCode: "NO_CERTIFIED_CUSTOM_SPECIFICATIONS",
        };
  const providerReceipt = buildTemplateTwinProviderOwnershipReceipt({
    projection: {
      subjectId: providerContext.subjectId,
      subjectSha256: providerContext.subjectSha256,
      visitId: input.visitId,
      sourceArtifactId: compiled.sourceArtifact.id,
      compiledVersionId: compiled.id,
      noteTemplateId: row.id,
    },
    expectedExecutionPlan: [
      ...inputModePlan,
      { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
      { operation: "L4_GENERATE_SOAP", disposition: "EXECUTED" },
      ...anchorPlan,
      { operation: "L5_SELF_CRITIQUE", disposition: "EXECUTED" },
      polishPlan,
      fidelityPlan,
      customConceptPlan,
    ],
  });
  if (
    existing &&
    (!existing.providerOwnershipSha256 ||
      existing.providerOwnershipSha256 !== providerReceipt.sha256)
  ) {
    throw new TemplateTwinProviderOwnershipError(
      "TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE",
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
  const lockSyntheticQaAttempt = async (
    tx: Prisma.TransactionClient,
    currentRolloutToken: TemplateTwinRolloutToken,
  ): Promise<{ code: string; reason: string } | null> => {
    if (!syntheticQaAttempt) return null;
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
    try {
      await lockAndAssertTemplateTwinStagingQaAttempt({
        tx,
        claim: syntheticQaAttempt,
        currentRolloutToken,
        allowedStatuses: ["PROCESSING"],
        allowedAdmissionPhases: ["PROCESSING"],
        requireLiveWorkerLease: true,
      });
      return null;
    } catch (error) {
      if (
        !(error instanceof TemplateTwinStagingQaDisabledError) &&
        !(error instanceof TemplateTwinStagingQaVisitGuardError)
      ) {
        throw error;
      }
      const code = error.code;
      await enqueueTemplateTwinAudit(tx, {
        eventKey:
          `template-twin:staging-attempt-final-claim-blocked:` +
          `${syntheticQaAttempt.runId}:${syntheticQaAttempt.attempt}:${code}`,
        practiceId: input.practiceId,
        actorId: input.doctorId,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TranscribeVisit",
        targetId: input.visitId,
        metadata: {
          reasonCode: code,
          operation: "staging_final_output_claim",
          stagingQaRunId: syntheticQaAttempt.runId,
          stagingQaAttempt: syntheticQaAttempt.attempt,
          outputWrittenUnclaimed: storedOutput !== null,
        },
      });
      return {
        code,
        reason:
          "A newer synthetic QA attempt replaced this worker claim. Retry from the current run.",
      };
    }
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
    fieldIntentsSha256,
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
    providerOwnershipEvidence: asJson(providerReceipt.evidence),
    providerOwnershipSha256: providerReceipt.sha256,
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
            stagingAttemptRejected: null,
          } as const;
        }
        const stagingAttemptRejected = await lockSyntheticQaAttempt(
          tx,
          finalRollout.token,
        );
        if (stagingAttemptRejected) {
          return {
            count: 0,
            soapBindingStale: false,
            rolloutRejected: null,
            stagingAttemptRejected,
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
            stagingAttemptRejected: null,
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
          stagingAttemptRejected: null,
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
    if (updated.stagingAttemptRejected) {
      throw new TemplateTwinFillError(
        "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
        updated.stagingAttemptRejected.reason,
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
              stagingAttemptRejected: null,
            } as const;
          }
          const stagingAttemptRejected = await lockSyntheticQaAttempt(
            tx,
            finalRollout.token,
          );
          if (stagingAttemptRejected) {
            return {
              soapBindingStale: false,
              rolloutRejected: null,
              stagingAttemptRejected,
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
              stagingAttemptRejected: null,
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
            stagingAttemptRejected: null,
          } as const;
        },
        // The database's cross-table physician/tenant lineage guard uses a
        // shared advisory gate and a post-wait READ COMMITTED snapshot. Row
        // locks plus the unique visit fill and optimistic manifest claims
        // retain the transaction's existing concurrency boundaries.
        { isolationLevel: "ReadCommitted" },
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
      if (createdResult.stagingAttemptRejected) {
        throw new TemplateTwinFillError(
          "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
          createdResult.stagingAttemptRejected.reason,
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
