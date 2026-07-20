import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";
import type { ModelClient } from "@meddoc/ai";

import { SemanticMappingSchema, TemplateDocIRSchema } from "./ir";
import { canonicalSha256 } from "./canonical";
import { templateTwinMappingsSha256 } from "./mapping-hash";
import {
  customConceptSpecifications,
  fieldRequiresExplicitIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
} from "./field-intent";
import {
  TEMPLATE_CUSTOM_EXTRACTION_DEFAULT_MODEL,
  type CertifiedTemplateFieldSpecification,
} from "./custom-concepts";
import {
  evaluateTemplateTwinCustomExampleCoverage,
  executeTemplateTwinCustomExamples,
  templateTwinCustomSpecificationSetSha256,
  type PersistedTemplateTwinCustomExampleExecution,
  type TemplateTwinCustomExampleCoverage,
} from "./custom-concepts/example-coverage";
import { enqueueTemplateTwinAudit } from "./audit-outbox";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  lockAndAssertActiveTemplateTwinPractice,
  lockAndAssertCurrentTemplateTwinPhysician,
} from "./final-claim-authority";

export class TemplateTwinCustomExampleError extends Error {
  readonly code:
    | "NOT_FOUND"
    | "IMMUTABLE"
    | "NO_CUSTOM_FIELDS"
    | "STALE_CONFIGURATION"
    | "EXAMPLES_FAILED"
    | "BATCH_NOT_FOUND"
    | "ALREADY_ACKNOWLEDGED"
    | "ROLLOUT_CHANGED";

  constructor(code: TemplateTwinCustomExampleError["code"], message: string) {
    super(message);
    this.name = "TemplateTwinCustomExampleError";
    this.code = code;
  }
}

export interface TemplateTwinCustomExampleActor {
  readonly userId: string;
  readonly userEmail: string;
  readonly practiceId: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

interface CurrentCustomExampleState {
  readonly compiledVersionId: string;
  readonly noteTemplateVersion: number;
  readonly sourceArtifactId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly mappingsSha256: string;
  readonly fieldIntentsSha256: string;
  readonly specifications: readonly CertifiedTemplateFieldSpecification[];
  readonly specificationSetSha256: string;
  readonly decisionIdByFieldId: ReadonlyMap<string, string>;
  readonly definitionIdByFieldId: ReadonlyMap<string, string>;
}

interface CustomExampleStateFieldRow {
  id: string;
  fieldId: string;
  mapping: Record<string, unknown> | null;
  intentDecisions: Array<{
    id: string;
    version: number;
    intentKind: string;
    supportedConcept: string | null;
    customConceptId: string | null;
    customSpec: unknown;
    customSpecSha256: string | null;
    reason: string | null;
    decidedById: string;
    decidedAt: Date;
  }>;
}

type DbClient = Prisma.TransactionClient | typeof prisma;

function persistedMapping(fieldId: string, row: Record<string, unknown>) {
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
    status: String(row.mappingStatus).toLowerCase(),
  });
}

async function loadCurrentCustomExampleState(input: {
  db: DbClient;
  noteTemplateId: string;
  actor: Pick<TemplateTwinCustomExampleActor, "userId" | "practiceId">;
  requireMutable: boolean;
}): Promise<CurrentCustomExampleState> {
  const row = await input.db.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.actor.userId,
      templateKind: "template_twin_docx",
      doctor: {
        is: {
          id: input.actor.userId,
          practiceId: input.actor.practiceId,
          role: "DOCTOR",
          isActive: true,
          deactivatedAt: null,
          suspendedAt: null,
          softDeletedAt: null,
          products: { has: "TRANSCRIBE_MD" },
          practice: {
            is: { id: input.actor.practiceId, isActive: true },
          },
        },
      },
    },
    select: {
      status: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          certificationStatus: true,
          certification: { select: { id: true } },
          compiledDocumentIr: true,
          sourceArtifact: {
            select: {
              id: true,
              practiceId: true,
              lineageId: true,
              lineageVersion: true,
              sha256: true,
            },
          },
          fields: {
            select: {
              id: true,
              fieldId: true,
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
              intentDecisions: {
                orderBy: { version: "desc" as const },
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
    compiled.sourceArtifact.practiceId !== input.actor.practiceId
  ) {
    throw new TemplateTwinCustomExampleError(
      "NOT_FOUND",
      "This Template Twin version is stale or unavailable. Refresh the certification workspace.",
    );
  }
  if (
    input.requireMutable &&
    (row.status !== "draft" ||
      compiled.certification ||
      compiled.certificationStatus === "CERTIFIED")
  ) {
    throw new TemplateTwinCustomExampleError(
      "IMMUTABLE",
      "This template version is already immutable. Create a new version to change or rerun its custom-field examples.",
    );
  }
  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const persistedFields =
    compiled.fields as unknown as CustomExampleStateFieldRow[];
  const fieldById = new Map(
    persistedFields.map((field) => [field.fieldId, field]),
  );
  const mappings = ir.fields.map((field) => {
    const persisted = fieldById.get(field.fieldId);
    if (!persisted?.mapping) {
      throw new TemplateTwinCustomExampleError(
        "STALE_CONFIGURATION",
        "The custom-field mapping set is incomplete.",
      );
    }
    return persistedMapping(
      field.fieldId,
      persisted.mapping as unknown as Record<string, unknown>,
    );
  });
  const intents = ir.fields.filter(fieldRequiresExplicitIntent).map((field) => {
    const persisted = fieldById.get(field.fieldId);
    if (!persisted) {
      throw new TemplateTwinCustomExampleError(
        "STALE_CONFIGURATION",
        "The custom-field definition set is incomplete.",
      );
    }
    const decision = persisted.intentDecisions[0];
    return {
      fieldId: field.fieldId,
      definitionId: persisted.id,
      decisionId: decision?.id ?? null,
      intent: decision
        ? parsePersistedFieldIntent({
            ...decision,
            fieldDefinitionId: persisted.id,
            fieldId: field.fieldId,
          } satisfies PersistedTemplateTwinFieldIntent)
        : unresolvedFieldIntent(),
    };
  });
  const specifications = customConceptSpecifications(intents);
  if (specifications.length === 0) {
    throw new TemplateTwinCustomExampleError(
      "NO_CUSTOM_FIELDS",
      "No template-specific custom fields need example testing.",
    );
  }
  return {
    compiledVersionId: compiled.id,
    noteTemplateVersion: row.version,
    sourceArtifactId: compiled.sourceArtifact.id,
    sourceLineageId: compiled.sourceArtifact.lineageId,
    sourceLineageVersion: compiled.sourceArtifact.lineageVersion,
    sourceSha256: compiled.sourceArtifact.sha256,
    mappingsSha256: templateTwinMappingsSha256(mappings),
    fieldIntentsSha256: templateTwinFieldIntentsSha256(intents),
    specifications,
    specificationSetSha256:
      templateTwinCustomSpecificationSetSha256(specifications),
    decisionIdByFieldId: new Map(
      intents.flatMap((entry) =>
        entry.decisionId ? [[entry.fieldId, entry.decisionId] as const] : [],
      ),
    ),
    definitionIdByFieldId: new Map(
      intents.map((entry) => [entry.fieldId, entry.definitionId]),
    ),
  };
}

function persistedRow(
  row: Record<string, unknown>,
): PersistedTemplateTwinCustomExampleExecution {
  const resultValue =
    typeof row.resultValue === "object" &&
    row.resultValue !== null &&
    !Array.isArray(row.resultValue)
      ? (row.resultValue as Record<string, unknown>)
      : {};
  const scalar = resultValue.value;
  const parsedScalar =
    typeof scalar === "string" ||
    typeof scalar === "number" ||
    typeof scalar === "boolean"
      ? scalar
      : null;
  const resultSummary =
    typeof row.resultSummary === "object" &&
    row.resultSummary !== null &&
    !Array.isArray(row.resultSummary)
      ? (row.resultSummary as Record<string, unknown>)
      : {};
  return {
    id: String(row.id),
    batchId: String(row.batchId),
    fieldId: String(row.fieldId),
    conceptId: String(row.conceptId),
    exampleKind: String(row.exampleKind).toLowerCase(),
    exampleId: String(row.exampleId),
    exampleDefinitionSha256: String(row.exampleDefinitionSha256),
    specificationSha256: String(row.specificationSha256),
    specificationSetSha256: String(row.specificationSetSha256),
    mappingsSha256: String(row.mappingsSha256),
    fieldIntentsSha256: String(row.fieldIntentsSha256),
    contractVersion: String(row.contractVersion),
    extractionSchemaSha256: String(row.extractionSchemaSha256),
    extractorVersion: String(row.extractorVersion),
    extractionSchemaVersion: String(row.extractionSchemaVersion),
    provider: String(row.provider),
    providerSha256: String(row.providerSha256),
    model: String(row.model),
    modelSha256: String(row.modelSha256),
    resultStatus: String(row.resultStatus),
    resultValue: parsedScalar,
    resultUnit: typeof resultValue.unit === "string" ? resultValue.unit : null,
    resultFactCount:
      typeof row.resultFactCount === "number" ? row.resultFactCount : -1,
    resultSummary,
    resultSha256: String(row.resultSha256),
    passed: row.passed === true,
    failureCode: typeof row.failureCode === "string" ? row.failureCode : null,
    acknowledgedById:
      typeof row.acknowledgedById === "string" ? row.acknowledgedById : null,
    acknowledgedAt:
      row.acknowledgedAt instanceof Date ? row.acknowledgedAt : null,
  };
}

async function rowsForBatch(
  db: DbClient,
  compiledVersionId: string,
  batchId: string,
): Promise<PersistedTemplateTwinCustomExampleExecution[]> {
  const rows = await db.templateTwinCustomExampleExecution.findMany({
    where: { compiledVersionId, batchId },
    orderBy: [{ fieldId: "asc" }, { exampleKind: "asc" }, { exampleId: "asc" }],
  });
  return (rows as unknown[]).map((row) =>
    persistedRow(row as Record<string, unknown>),
  );
}

export async function readTemplateTwinCustomExampleCoverage(input: {
  noteTemplateId: string;
  doctorId: string;
  practiceId: string;
}): Promise<TemplateTwinCustomExampleCoverage | null> {
  return prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    // Canonical practice -> actor lock order. Both locks remain held until the
    // content-bearing template and execution projections are assembled, so a
    // practice deactivation cannot commit between those ReadCommitted
    // statements and leak post-revocation custom-example content.
    await lockAndAssertActiveTemplateTwinPractice({
      tx,
      practiceId: input.practiceId,
    });
    await lockAndAssertCurrentTemplateTwinPhysician({
      tx,
      actor: { userId: input.doctorId, practiceId: input.practiceId },
    });
    let state: CurrentCustomExampleState;
    try {
      state = await loadCurrentCustomExampleState({
        db: tx,
        noteTemplateId: input.noteTemplateId,
        actor: { userId: input.doctorId, practiceId: input.practiceId },
        requireMutable: false,
      });
    } catch (error) {
      if (
        error instanceof TemplateTwinCustomExampleError &&
        error.code === "NO_CUSTOM_FIELDS"
      ) {
        return null;
      }
      throw error;
    }
    const latest = await tx.templateTwinCustomExampleExecution.findFirst({
      where: { compiledVersionId: state.compiledVersionId },
      orderBy: { executedAt: "desc" },
      select: { batchId: true },
    });
    const rows = latest
      ? await rowsForBatch(tx, state.compiledVersionId, latest.batchId)
      : [];
    return evaluateTemplateTwinCustomExampleCoverage({
      specifications: state.specifications,
      mappingsSha256: state.mappingsSha256,
      fieldIntentsSha256: state.fieldIntentsSha256,
      physicianUserId: input.doctorId,
      rows,
    });
  });
}

export async function runTemplateTwinCustomExamples(input: {
  noteTemplateId: string;
  actor: TemplateTwinCustomExampleActor;
  model?: string;
  client?: Pick<ModelClient, "complete">;
  privacyClient?: Pick<ModelClient, "complete">;
}): Promise<TemplateTwinCustomExampleCoverage> {
  const before = await loadCurrentCustomExampleState({
    db: prisma,
    noteTemplateId: input.noteTemplateId,
    actor: input.actor,
    requireMutable: true,
  });
  const executions = await executeTemplateTwinCustomExamples({
    specifications: before.specifications,
    practiceId: input.actor.practiceId,
    userId: input.actor.userId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: before.noteTemplateVersion,
    sourceArtifactId: before.sourceArtifactId,
    compiledVersionId: before.compiledVersionId,
    sourceLineageId: before.sourceLineageId,
    sourceLineageVersion: before.sourceLineageVersion,
    sourceSha256: before.sourceSha256,
    rolloutToken: input.actor.rolloutToken,
    model: input.model ?? TEMPLATE_CUSTOM_EXTRACTION_DEFAULT_MODEL,
    client: input.client,
    privacyClient: input.privacyClient,
  });
  const batchId = executions[0]?.batchId;
  if (!batchId) {
    throw new TemplateTwinCustomExampleError(
      "NO_CUSTOM_FIELDS",
      "No template-specific custom examples were available.",
    );
  }

  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinCustomExampleError(
          "ROLLOUT_CHANGED",
          `${rollout.code}: Template Twin availability changed while the custom examples were running. Reload and try again.`,
        );
      }
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
      const current = await loadCurrentCustomExampleState({
        db: tx,
        noteTemplateId: input.noteTemplateId,
        actor: input.actor,
        requireMutable: true,
      });
      if (
        current.compiledVersionId !== before.compiledVersionId ||
        current.mappingsSha256 !== before.mappingsSha256 ||
        current.fieldIntentsSha256 !== before.fieldIntentsSha256 ||
        current.specificationSetSha256 !== before.specificationSetSha256
      ) {
        throw new TemplateTwinCustomExampleError(
          "STALE_CONFIGURATION",
          "A custom-field specification or mapping changed while examples were running. The stale results were not saved.",
        );
      }
      for (const execution of executions) {
        const fieldIntentDecisionId = current.decisionIdByFieldId.get(
          execution.definition.fieldId,
        );
        const fieldDefinitionId = current.definitionIdByFieldId.get(
          execution.definition.fieldId,
        );
        if (!fieldIntentDecisionId || !fieldDefinitionId) {
          throw new TemplateTwinCustomExampleError(
            "STALE_CONFIGURATION",
            "A custom-field decision changed before its example result could be saved.",
          );
        }
        await tx.templateTwinCustomExampleExecution.create({
          data: {
            id: execution.id,
            batchId: execution.batchId,
            practiceId: input.actor.practiceId,
            compiledVersionId: current.compiledVersionId,
            fieldDefinitionId,
            fieldIntentDecisionId,
            fieldId: execution.definition.fieldId,
            conceptId: execution.definition.conceptId,
            exampleKind: execution.definition.kind.toUpperCase(),
            exampleId: execution.definition.exampleId,
            exampleDefinitionSha256: execution.definition.definitionSha256,
            exampleEvidenceSha256: execution.definition.evidenceSha256,
            specificationSha256: execution.definition.specificationSha256,
            specificationSetSha256: execution.specificationSetSha256,
            mappingsSha256: current.mappingsSha256,
            fieldIntentsSha256: current.fieldIntentsSha256,
            contractVersion: execution.contractVersion,
            extractionSchemaSha256: execution.extractionSchemaSha256,
            extractorVersion: execution.extractorVersion,
            extractionSchemaVersion: execution.extractionSchemaVersion,
            provider: execution.provider,
            providerSha256: execution.providerSha256,
            model: execution.model,
            modelSha256: execution.modelSha256,
            resultStatus: execution.resultStatus,
            resultValue: {
              value: execution.resultValue,
              unit: execution.resultUnit,
            } as Prisma.InputJsonValue,
            resultFactCount: execution.resultFactCount,
            resultSummary: execution.resultSummary as Prisma.InputJsonValue,
            resultSha256: execution.resultSha256,
            passed: execution.passed,
            failureCode: execution.failureCode,
            executedById: input.actor.userId,
            providerOwnershipEvidence:
              execution.providerOwnershipReceipt?.evidence ?? Prisma.DbNull,
            providerOwnershipSha256:
              execution.providerOwnershipReceipt?.sha256 ?? null,
          },
        });
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:custom-example-executed:${execution.id}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: currentActor.email,
          action: "TEMPLATE_TWIN_CUSTOM_EXAMPLE_EXECUTED",
          targetType: "TemplateTwinCustomExampleExecution",
          targetId: execution.id,
          metadata: {
            compiledVersionId: current.compiledVersionId,
            fieldId: execution.definition.fieldId,
            conceptId: execution.definition.conceptId,
            exampleKind: execution.definition.kind,
            exampleIdSha256: canonicalSha256(execution.definition.exampleId),
            exampleDefinitionSha256: execution.definition.definitionSha256,
            specificationSha256: execution.definition.specificationSha256,
            extractionSchemaSha256: execution.extractionSchemaSha256,
            providerSha256: execution.providerSha256,
            modelSha256: execution.modelSha256,
            resultSha256: execution.resultSha256,
            passed: execution.passed,
            failureCode: execution.failureCode,
          },
        });
      }
      const rows = await rowsForBatch(tx, current.compiledVersionId, batchId);
      return evaluateTemplateTwinCustomExampleCoverage({
        specifications: current.specifications,
        mappingsSha256: current.mappingsSha256,
        fieldIntentsSha256: current.fieldIntentsSha256,
        physicianUserId: input.actor.userId,
        rows,
      });
    },
    { isolationLevel: "Serializable" },
  );
}

export async function acknowledgeTemplateTwinCustomExamples(input: {
  noteTemplateId: string;
  batchId: string;
  actor: TemplateTwinCustomExampleActor;
}): Promise<TemplateTwinCustomExampleCoverage> {
  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinCustomExampleError(
          "ROLLOUT_CHANGED",
          `${rollout.code}: Template Twin availability changed before example review was recorded. Reload and try again.`,
        );
      }
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
      const state = await loadCurrentCustomExampleState({
        db: tx,
        noteTemplateId: input.noteTemplateId,
        actor: input.actor,
        requireMutable: true,
      });
      const rows = await rowsForBatch(
        tx,
        state.compiledVersionId,
        input.batchId,
      );
      if (rows.length === 0) {
        throw new TemplateTwinCustomExampleError(
          "BATCH_NOT_FOUND",
          "The custom-field example run was not found.",
        );
      }
      const coverage = evaluateTemplateTwinCustomExampleCoverage({
        specifications: state.specifications,
        mappingsSha256: state.mappingsSha256,
        fieldIntentsSha256: state.fieldIntentsSha256,
        physicianUserId: input.actor.userId,
        rows,
      });
      if (coverage.stale || coverage.passedCount !== coverage.requiredCount) {
        throw new TemplateTwinCustomExampleError(
          "EXAMPLES_FAILED",
          "Every current positive, negative, and ambiguity example must pass before physician review can be recorded.",
        );
      }
      const acknowledgedAt = new Date();
      for (const row of rows) {
        if (row.acknowledgedAt !== null) {
          throw new TemplateTwinCustomExampleError(
            "ALREADY_ACKNOWLEDGED",
            "This immutable example result was already acknowledged.",
          );
        }
        const updated = await tx.templateTwinCustomExampleExecution.updateMany({
          where: { id: row.id, acknowledgedAt: null },
          data: {
            acknowledgedById: input.actor.userId,
            acknowledgedAt,
          },
        });
        if (updated.count !== 1) {
          throw new TemplateTwinCustomExampleError(
            "ALREADY_ACKNOWLEDGED",
            "The example review changed in another session. Reload before continuing.",
          );
        }
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:custom-example-acknowledged:${row.id}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: currentActor.email,
          action: "TEMPLATE_TWIN_CUSTOM_EXAMPLE_ACKNOWLEDGED",
          targetType: "TemplateTwinCustomExampleExecution",
          targetId: row.id,
          metadata: {
            compiledVersionId: state.compiledVersionId,
            batchId: input.batchId,
            fieldId: row.fieldId,
            conceptId: row.conceptId,
            exampleKind: row.exampleKind.toLowerCase(),
            exampleIdSha256: canonicalSha256(row.exampleId),
            resultSha256: row.resultSha256,
            mappingsSha256: state.mappingsSha256,
            fieldIntentsSha256: state.fieldIntentsSha256,
          },
        });
      }
      const acknowledgedRows = rows.map((row) => ({
        ...row,
        acknowledgedById: input.actor.userId,
        acknowledgedAt,
      }));
      return evaluateTemplateTwinCustomExampleCoverage({
        specifications: state.specifications,
        mappingsSha256: state.mappingsSha256,
        fieldIntentsSha256: state.fieldIntentsSha256,
        physicianUserId: input.actor.userId,
        rows: acknowledgedRows,
      });
    },
    { isolationLevel: "Serializable" },
  );
}

export async function assertTemplateTwinCustomExamplesReadyForCertification(input: {
  tx: DbClient;
  compiledVersionId: string;
  specifications: readonly CertifiedTemplateFieldSpecification[];
  mappingsSha256: string;
  fieldIntentsSha256: string;
  physicianUserId: string;
  expectedModel?: string;
}): Promise<string | null> {
  if (input.specifications.length === 0) return null;
  const latest = await input.tx.templateTwinCustomExampleExecution.findFirst({
    where: { compiledVersionId: input.compiledVersionId },
    orderBy: { executedAt: "desc" },
    select: { batchId: true },
  });
  const rows = latest
    ? await rowsForBatch(input.tx, input.compiledVersionId, latest.batchId)
    : [];
  const coverage = evaluateTemplateTwinCustomExampleCoverage({
    specifications: input.specifications,
    mappingsSha256: input.mappingsSha256,
    fieldIntentsSha256: input.fieldIntentsSha256,
    physicianUserId: input.physicianUserId,
    rows,
  });
  if (!coverage.ready || !coverage.proofSha256) {
    throw new TemplateTwinCustomExampleError(
      "EXAMPLES_FAILED",
      coverage.stale
        ? "TT_CUSTOM_EXAMPLE_PROOF_STALE: The custom-field examples no longer match this exact template version and mapping. Run and review them again."
        : "TT_CUSTOM_EXAMPLE_PROOF_REQUIRED: Run every custom-field positive, negative, and ambiguity example, then review the passing results before activation.",
    );
  }
  if (
    input.expectedModel !== undefined &&
    (input.expectedModel.trim().length === 0 ||
      rows.some((row) => row.model !== input.expectedModel))
  ) {
    throw new TemplateTwinCustomExampleError(
      "EXAMPLES_FAILED",
      "TT_CUSTOM_EXAMPLE_MODEL_STALE: The active extraction model does not match the physician-reviewed custom-field examples. Run and review the examples again with the current model.",
    );
  }
  return coverage.proofSha256;
}
