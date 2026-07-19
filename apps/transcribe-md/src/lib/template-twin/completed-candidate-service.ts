import { randomUUID } from "node:crypto";

import type { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import { TemplateDocxError } from "@/lib/note-template-docx";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  CompletedCandidateComparisonSchema,
  CompletedCandidateIdentitySchema,
  CompletedCandidatePrivacyEvidenceSchema,
  CompletedCandidateReviewPayloadSchema,
  type CompletedCandidateReviewDto,
} from "./completed-candidate-contract";
import {
  CompletedCandidateConversionError,
  convertCompletedDocumentsToCandidate,
} from "./completed-candidate-converter";
import type { TemplateTwinMalwareScanner } from "./malware-scan";
import {
  beginTemplateTwinQuarantine,
  isolateCompletedExampleQuarantine,
  rejectTemplateTwinQuarantine,
  scanTemplateTwinQuarantine,
  type TemplateTwinIntakeActor,
  type TemplateTwinQuarantineReceipt,
} from "./quarantine-admission";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import { minimizeTemplateTwinSourceMetadata } from "./source-metadata";
import {
  assertTemplateTwinRecordOwner,
  claimTemplateTwinObject,
  createTemplateTwinArtifactStore,
  type StoredTemplateTwinArtifact,
  type TemplateTwinArtifactStore,
} from "./storage";

export type CompletedCandidateServiceErrorCode =
  | "INVALID_INPUT"
  | "NOT_FOUND"
  | "REVIEW_CONFLICT"
  | "ROLLOUT_CHANGED"
  | "PERSISTENCE_FAILED";

export class CompletedCandidateServiceError extends Error {
  readonly code: CompletedCandidateServiceErrorCode;

  constructor(
    code: CompletedCandidateServiceErrorCode,
    message: string,
    cause?: unknown,
  ) {
    super(message, { cause });
    this.name = "CompletedCandidateServiceError";
    this.code = code;
  }
}

interface PreparedExample {
  readonly receipt: TemplateTwinQuarantineReceipt;
  readonly document: Buffer;
  readonly metadataEvidence: Awaited<
    ReturnType<typeof minimizeTemplateTwinSourceMetadata>
  >["evidence"];
}

interface CompletedCandidateRegionRow {
  readonly regionId: string;
  readonly displayOrder: number;
  readonly label: string;
  readonly evidenceType: string;
  readonly tableIndex: number;
  readonly rowIndex: number;
  readonly cellIndex: number;
  readonly candidateTag: string;
  readonly sourceEvidenceSha256: string;
  readonly decision: string;
}

export interface CompletedCandidateActor extends TemplateTwinIntakeActor {
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface CreateCompletedCandidateInput {
  readonly examples: readonly Uint8Array[];
  readonly identity: {
    readonly name: string;
    readonly encounterScope: string;
    readonly versionDescription: string;
  };
  readonly actor: CompletedCandidateActor;
  readonly storage?: TemplateTwinArtifactStore;
  /** Explicit unit/integration seam. Runtime callers require local ClamAV. */
  readonly malwareScanner?: TemplateTwinMalwareScanner;
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

async function rejectPrepared(
  prepared: readonly PreparedExample[],
  actor: CompletedCandidateActor,
  code: string,
): Promise<void> {
  for (const example of prepared) {
    await rejectTemplateTwinQuarantine({
      receipt: example.receipt,
      actor,
      rejectionCode: code,
      metadataEvidence: example.metadataEvidence,
    });
  }
}

export async function createCompletedCandidate(
  input: CreateCompletedCandidateInput,
): Promise<{ candidateId: string; reviewUrl: string }> {
  const identity = CompletedCandidateIdentitySchema.safeParse(input.identity);
  if (
    !identity.success ||
    input.examples.length < 2 ||
    input.examples.length > 3
  ) {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "Provide two or three synthetic Word examples and complete the candidate details.",
    );
  }
  const candidateId = randomUUID();
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const prepared: PreparedExample[] = [];

  for (const [index, source] of input.examples.entries()) {
    let receipt: TemplateTwinQuarantineReceipt | null = null;
    let scanCompleted = false;
    try {
      receipt = await beginTemplateTwinQuarantine({
        source,
        actor: input.actor,
        intakeMode: "COMPLETED_EXAMPLE",
        lineageId: candidateId,
        lineageVersion: index + 1,
        storage,
      });
      await scanTemplateTwinQuarantine({
        source,
        receipt,
        actor: input.actor,
        ...(input.malwareScanner ? { scanner: input.malwareScanner } : {}),
      });
      scanCompleted = true;
      const minimized = await minimizeTemplateTwinSourceMetadata(source);
      prepared.push({
        receipt,
        document: minimized.document,
        metadataEvidence: minimized.evidence,
      });
    } catch (error) {
      if (
        receipt &&
        scanCompleted &&
        !prepared.some((item) => item.receipt.id === receipt!.id)
      ) {
        // A post-scan package/minimization failure is terminal. Malware
        // failures already recorded their own terminal/unavailable state.
        await rejectTemplateTwinQuarantine({
          receipt,
          actor: input.actor,
          rejectionCode:
            error instanceof TemplateDocxError
              ? error.code
              : "COMPLETED_CANDIDATE_METADATA_MINIMIZATION_FAILED",
        });
      }
      await rejectPrepared(
        prepared,
        input.actor,
        "COMPLETED_CANDIDATE_INTAKE_ABORTED",
      );
      throw error;
    }
  }

  let converted: Awaited<
    ReturnType<typeof convertCompletedDocumentsToCandidate>
  >;
  try {
    converted = await convertCompletedDocumentsToCandidate(
      prepared.map((example) => ({
        document: example.document,
        minimizedSha256: example.metadataEvidence.minimizedSha256,
      })),
    );
  } catch (error) {
    await rejectPrepared(
      prepared,
      input.actor,
      error instanceof CompletedCandidateConversionError
        ? error.code
        : "COMPLETED_CANDIDATE_CONVERSION_FAILED",
    );
    throw error;
  }

  let stored: StoredTemplateTwinArtifact;
  try {
    stored = await storage.storeCandidateArtifact({
      practiceId: input.actor.practiceId,
      candidateId,
      candidateVersion: 1,
      bytes: converted.document,
    });
  } catch (error) {
    await rejectPrepared(
      prepared,
      input.actor,
      "COMPLETED_CANDIDATE_STORAGE_FAILED",
    );
    throw error;
  }
  if (stored.sha256 !== converted.candidateSha256) {
    await rejectPrepared(
      prepared,
      input.actor,
      "COMPLETED_CANDIDATE_STORAGE_IDENTITY_MISMATCH",
    );
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The generated candidate failed its immutable storage identity check.",
    );
  }

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed) {
        throw new CompletedCandidateServiceError(
          "ROLLOUT_CHANGED",
          `${rollout.code}: Template Twin availability changed while the candidate was being generated.`,
        );
      }
      await tx.templateTwinCompletedCandidate.create({
        data: {
          id: candidateId,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          name: identity.data.name,
          encounterScope: identity.data.encounterScope,
          versionDescription: identity.data.versionDescription,
          status: "PENDING_REVIEW",
          candidateObjectKey: stored.objectKey,
          candidateObjectVersionId: stored.objectVersionId,
          candidateObjectEtag: stored.objectEtag,
          candidateSha256: stored.sha256,
          candidateSizeBytes: stored.sizeBytes,
          candidateStructureSha256: converted.candidateStructureSha256,
          inventorySha256: converted.inventorySha256,
          converterVersion: converted.converterVersion,
          comparisonEvidence: asJson(converted.comparison),
          privacyEvidence: asJson(converted.privacyEvidence),
          examples: {
            create: prepared.map((example, index) => ({
              quarantineArtifactId: example.receipt.id,
              ordinal: index + 1,
              minimizedSha256: example.metadataEvidence.minimizedSha256,
              documentStructureSha256: converted.exampleStructureSha256,
              localPrivacyEvidenceSha256:
                converted.privacyEvidence.exampleEvidenceSha256s[index]!,
            })),
          },
          regions: {
            create: converted.regions.map((region) => ({
              regionId: region.regionId,
              displayOrder: region.displayOrder,
              label: region.label,
              evidenceType: region.evidenceType,
              partName: region.partName,
              tableIndex: region.tableIndex,
              rowIndex: region.rowIndex,
              cellIndex: region.cellIndex,
              candidateTag: region.candidateTag,
              candidateSdtId: region.candidateSdtId,
              sourceEvidenceSha256: region.sourceEvidenceSha256,
              decision: "PENDING",
            })),
          },
        },
      });
      for (const example of prepared) {
        await isolateCompletedExampleQuarantine({
          tx,
          receipt: example.receipt,
          actor: input.actor,
          candidateId,
          metadataEvidence: example.metadataEvidence,
        });
      }
      await claimTemplateTwinObject(tx, {
        objectKey: stored.objectKey,
        practiceId: input.actor.practiceId,
        claimType: "completed_candidate",
        claimId: candidateId,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:completed-candidate-created:${candidateId}:${converted.inventorySha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_CREATED",
        targetType: "TemplateTwinCompletedCandidate",
        targetId: candidateId,
        metadata: {
          candidateSha256: converted.candidateSha256,
          candidateStructureSha256: converted.candidateStructureSha256,
          inventorySha256: converted.inventorySha256,
          exampleCount: prepared.length,
          regionCount: converted.regions.length,
          converterVersion: converted.converterVersion,
          providerEgress: false,
          gateOutcome: "pending_physician_review",
        },
      });
    });
  } catch (error) {
    await rejectPrepared(
      prepared,
      input.actor,
      error instanceof CompletedCandidateServiceError
        ? error.code
        : "COMPLETED_CANDIDATE_PERSISTENCE_FAILED",
    );
    if (error instanceof CompletedCandidateServiceError) throw error;
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The generated candidate could not be claimed for physician review.",
      error,
    );
  }

  return {
    candidateId,
    reviewUrl: `/settings/note-format/completed-candidate/${encodeURIComponent(candidateId)}`,
  };
}

function requireComparison(value: unknown) {
  const parsed = CompletedCandidateComparisonSchema.safeParse(value);
  if (!parsed.success) {
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The candidate comparison evidence is invalid.",
    );
  }
  return parsed.data;
}

function requirePrivacy(value: unknown) {
  const parsed = CompletedCandidatePrivacyEvidenceSchema.safeParse(value);
  if (!parsed.success) {
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The candidate privacy evidence is invalid.",
    );
  }
  const { evidenceSha256, ...receipt } = parsed.data;
  if (canonicalSha256(receipt) !== evidenceSha256) {
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The candidate privacy evidence digest is invalid.",
    );
  }
  return parsed.data;
}

export async function getCompletedCandidateReview(input: {
  candidateId: string;
  actor: { userId: string; practiceId: string };
}): Promise<CompletedCandidateReviewDto> {
  const row = await prisma.templateTwinCompletedCandidate.findFirst({
    where: {
      id: input.candidateId,
      practiceId: input.actor.practiceId,
      createdById: input.actor.userId,
    },
    select: {
      id: true,
      practiceId: true,
      createdById: true,
      name: true,
      encounterScope: true,
      versionDescription: true,
      status: true,
      candidateSha256: true,
      inventorySha256: true,
      comparisonEvidence: true,
      privacyEvidence: true,
      regions: {
        orderBy: { displayOrder: "asc" },
        select: {
          regionId: true,
          displayOrder: true,
          label: true,
          evidenceType: true,
          tableIndex: true,
          rowIndex: true,
          cellIndex: true,
          candidateTag: true,
          sourceEvidenceSha256: true,
          decision: true,
        },
      },
    },
  });
  if (!row) {
    throw new CompletedCandidateServiceError(
      "NOT_FOUND",
      "Candidate not found.",
    );
  }
  assertTemplateTwinRecordOwner(input.actor, {
    practiceId: row.practiceId,
    uploadedById: row.createdById,
  });
  if (
    !["PENDING_REVIEW", "APPROVED", "REJECTED"].includes(row.status) ||
    row.regions.length < 1 ||
    row.regions.some(
      (region: CompletedCandidateRegionRow) =>
        region.evidenceType !== "stable_label_changed_scalar_cell" ||
        !["PENDING", "APPROVED", "REJECTED"].includes(region.decision),
    )
  ) {
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The candidate field inventory is invalid.",
    );
  }
  return {
    id: row.id,
    name: row.name,
    encounterScope: row.encounterScope,
    versionDescription: row.versionDescription,
    status: row.status as CompletedCandidateReviewDto["status"],
    candidateSha256: row.candidateSha256,
    inventorySha256: row.inventorySha256,
    comparison: requireComparison(row.comparisonEvidence),
    privacy: requirePrivacy(row.privacyEvidence),
    regions: row.regions.map((region: CompletedCandidateRegionRow) => ({
      regionId: region.regionId,
      displayOrder: region.displayOrder,
      label: region.label,
      evidenceType: region.evidenceType as "stable_label_changed_scalar_cell",
      location: `Table ${region.tableIndex + 1}, row ${region.rowIndex + 1}, column ${region.cellIndex + 1}`,
      candidateTag: region.candidateTag,
      sourceEvidenceSha256: region.sourceEvidenceSha256,
      sourceDescription:
        "Values changed beside this stable label; example values are withheld and hash-bound.",
      candidateDescription:
        "Blank Word text control with a stable QuillMD binding.",
      decision: region.decision as "PENDING" | "APPROVED" | "REJECTED",
    })),
  };
}

export async function reviewCompletedCandidate(input: {
  candidateId: string;
  payload: unknown;
  actor: CompletedCandidateActor;
}): Promise<{ status: "APPROVED" | "REJECTED" }> {
  const payload = CompletedCandidateReviewPayloadSchema.safeParse(
    input.payload,
  );
  if (!payload.success) {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "Review every candidate region and acknowledge the physician decision.",
    );
  }
  const decisionById = new Map(
    payload.data.decisions.map((decision) => [
      decision.regionId,
      decision.decision,
    ]),
  );
  if (decisionById.size !== payload.data.decisions.length) {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "Each candidate region must have exactly one decision.",
    );
  }

  return prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    await tx.$queryRaw`SELECT "id" FROM "template_twin_completed_candidates" WHERE "id" = ${input.candidateId} FOR UPDATE`;
    const candidate = await tx.templateTwinCompletedCandidate.findFirst({
      where: {
        id: input.candidateId,
        practiceId: input.actor.practiceId,
        createdById: input.actor.userId,
      },
      select: {
        id: true,
        practiceId: true,
        createdById: true,
        status: true,
        inventorySha256: true,
        regions: {
          orderBy: { displayOrder: "asc" },
          select: { id: true, regionId: true, decision: true },
        },
      },
    });
    if (!candidate) {
      throw new CompletedCandidateServiceError(
        "NOT_FOUND",
        "Candidate not found.",
      );
    }
    assertTemplateTwinRecordOwner(input.actor, {
      practiceId: candidate.practiceId,
      uploadedById: candidate.createdById,
    });
    if (candidate.status !== "PENDING_REVIEW") {
      throw new CompletedCandidateServiceError(
        "REVIEW_CONFLICT",
        "This candidate already has a terminal physician review.",
      );
    }
    if (
      candidate.regions.length < 1 ||
      candidate.regions.some(
        (region) =>
          region.decision !== "PENDING" || !decisionById.has(region.regionId),
      ) ||
      decisionById.size !== candidate.regions.length
    ) {
      throw new CompletedCandidateServiceError(
        "INVALID_INPUT",
        "Review every visible candidate region exactly once.",
      );
    }
    const rollout = await lockTemplateTwinRolloutForFinalClaim({
      tx,
      practiceId: input.actor.practiceId,
      pinnedToken: input.actor.rolloutToken,
    });
    if (!rollout.allowed) {
      throw new CompletedCandidateServiceError(
        "ROLLOUT_CHANGED",
        `${rollout.code}: Template Twin availability changed before review was saved.`,
      );
    }
    const reviewedAt = new Date();
    for (const region of candidate.regions) {
      const decision = decisionById.get(region.regionId)!;
      const updated = await tx.templateTwinCompletedCandidateRegion.updateMany({
        where: {
          id: region.id,
          candidateId: candidate.id,
          decision: "PENDING",
        },
        data: {
          decision,
          decidedById: input.actor.userId,
          decidedAt: reviewedAt,
        },
      });
      if (updated.count !== 1) {
        throw new CompletedCandidateServiceError(
          "REVIEW_CONFLICT",
          "The candidate changed while it was being reviewed.",
        );
      }
    }
    const status = [...decisionById.values()].every(
      (decision) => decision === "APPROVED",
    )
      ? "APPROVED"
      : "REJECTED";
    const updated = await tx.templateTwinCompletedCandidate.updateMany({
      where: { id: candidate.id, status: "PENDING_REVIEW" },
      data: { status, reviewedAt },
    });
    if (updated.count !== 1) {
      throw new CompletedCandidateServiceError(
        "REVIEW_CONFLICT",
        "The candidate changed while it was being reviewed.",
      );
    }
    await enqueueTemplateTwinAudit(tx, {
      eventKey: `template-twin:completed-candidate-reviewed:${candidate.id}:${candidate.inventorySha256}:${status}`,
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      actorEmailSnapshot: input.actor.userEmail,
      action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED",
      targetType: "TemplateTwinCompletedCandidate",
      targetId: candidate.id,
      metadata: {
        inventorySha256: candidate.inventorySha256,
        regionCount: candidate.regions.length,
        approvedCount: [...decisionById.values()].filter(
          (decision) => decision === "APPROVED",
        ).length,
        rejectedCount: [...decisionById.values()].filter(
          (decision) => decision === "REJECTED",
        ).length,
        gateOutcome: status.toLowerCase(),
      },
    });
    return { status };
  });
}

export async function readApprovedCompletedCandidate(input: {
  candidateId: string;
  actor: CompletedCandidateActor;
  storage?: TemplateTwinArtifactStore;
}): Promise<Buffer> {
  const candidate = await prisma.templateTwinCompletedCandidate.findFirst({
    where: {
      id: input.candidateId,
      practiceId: input.actor.practiceId,
      createdById: input.actor.userId,
      status: "APPROVED",
      regions: { every: { decision: "APPROVED" } },
    },
    select: {
      id: true,
      practiceId: true,
      createdById: true,
      candidateObjectKey: true,
      candidateObjectVersionId: true,
      candidateObjectEtag: true,
      candidateSha256: true,
      candidateSizeBytes: true,
      inventorySha256: true,
      _count: { select: { regions: true } },
    },
  });
  if (!candidate || candidate._count.regions < 1) {
    throw new CompletedCandidateServiceError(
      "NOT_FOUND",
      "Candidate not found.",
    );
  }
  assertTemplateTwinRecordOwner(input.actor, {
    practiceId: candidate.practiceId,
    uploadedById: candidate.createdById,
  });
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const bytes = await storage.readCandidateArtifact({
    practiceId: candidate.practiceId,
    objectKey: candidate.candidateObjectKey,
    expectedObjectVersionId: candidate.candidateObjectVersionId,
    expectedObjectEtag: candidate.candidateObjectEtag,
    expectedSha256: candidate.candidateSha256,
    expectedSizeBytes: candidate.candidateSizeBytes,
  });
  await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    // The object read is deliberately outside the transaction. Take the same
    // global -> practice rollout locks used by other final claims afterwards,
    // then re-check the candidate while those locks remain held. A disable can
    // therefore never commit before this response is authorized and still let
    // the bytes escape under a stale session token.
    const rollout = await lockTemplateTwinRolloutForFinalClaim({
      tx,
      practiceId: input.actor.practiceId,
      pinnedToken: input.actor.rolloutToken,
    });
    if (!rollout.allowed) {
      throw new CompletedCandidateServiceError(
        "ROLLOUT_CHANGED",
        `${rollout.code}: Template Twin availability changed before the candidate download was authorized.`,
      );
    }
    const current = await tx.templateTwinCompletedCandidate.findFirst({
      where: {
        id: candidate.id,
        practiceId: input.actor.practiceId,
        createdById: input.actor.userId,
        status: "APPROVED",
        candidateSha256: candidate.candidateSha256,
      },
      select: { id: true },
    });
    if (!current) {
      throw new CompletedCandidateServiceError(
        "NOT_FOUND",
        "Candidate not found.",
      );
    }
    await enqueueTemplateTwinAudit(tx, {
      eventKey: `template-twin:completed-candidate-downloaded:${candidate.id}:${randomUUID()}`,
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      actorEmailSnapshot: input.actor.userEmail,
      action: "EXPORT_TEMPLATE_TWIN_CANDIDATE_DOCX_DOWNLOADED",
      targetType: "TemplateTwinCompletedCandidate",
      targetId: candidate.id,
      metadata: {
        candidateSha256: candidate.candidateSha256,
        inventorySha256: candidate.inventorySha256,
        sizeBytes: candidate.candidateSizeBytes,
        gateOutcome: "approved_candidate_downloaded",
      },
    });
  });
  return bytes;
}
