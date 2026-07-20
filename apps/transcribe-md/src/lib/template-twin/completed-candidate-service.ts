import {
  createHash,
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";

import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import {
  compileTemplateDocx,
  TemplateDocxError,
} from "@/lib/note-template-docx";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  CompletedCandidateComparisonSchema,
  CompletedCandidateIdentitySchema,
  CompletedCandidatePrivacyEvidenceSchema,
  CompletedCandidateReviewProjectionSchema,
  CompletedCandidateReviewPayloadSchema,
  type CompletedCandidateReviewPreviewDto,
  type CompletedCandidateReviewDto,
  type CompletedCandidateReviewProjection,
} from "./completed-candidate-contract";
import {
  COMPLETED_CANDIDATE_CONVERTER_VERSION,
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
import { lockAndAssertCurrentTemplateTwinPhysician } from "./final-claim-authority";
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
  | "REVIEW_PREVIEW_REQUIRED"
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
  readonly partName: string;
  readonly tableIndex: number;
  readonly rowIndex: number;
  readonly cellIndex: number;
  readonly candidateTag: string;
  readonly candidateSdtId: string;
  readonly sourceEvidenceSha256: string;
  readonly decision: string;
}

interface CompletedCandidateExampleRow {
  readonly ordinal: number;
  readonly minimizedSha256: string;
  readonly documentStructureSha256: string;
}

interface CompletedCandidateReviewReceiptRow {
  readonly id: string;
  readonly candidateId: string;
  readonly practiceId: string;
  readonly reviewedById: string;
  readonly tokenSha256: string;
  readonly candidateSha256: string;
  readonly candidateStructureSha256: string;
  readonly inventorySha256: string;
  readonly reviewProjectionSha256: string;
  readonly converterVersion: string;
  readonly globalRolloutGeneration: bigint | number | string;
  readonly practiceRolloutGeneration: bigint | number | string;
  readonly expiresAt: Date;
  readonly consumedAt: Date | null;
  readonly notExpired: boolean;
}

export interface CompletedCandidateActor extends TemplateTwinIntakeActor {
  readonly rolloutToken: TemplateTwinRolloutToken;
}

function currentCompletedCandidateOwnerWhere(actor: {
  userId: string;
  practiceId: string;
}) {
  return {
    createdById: actor.userId,
    createdBy: {
      is: {
        id: actor.userId,
        practiceId: actor.practiceId,
        role: "DOCTOR" as const,
        isActive: true,
        deactivatedAt: null,
        suspendedAt: null,
        softDeletedAt: null,
        products: { has: "TRANSCRIBE_MD" as const },
        practice: { is: { id: actor.practiceId, isActive: true } },
      },
    },
    practice: { is: { id: actor.practiceId, isActive: true } },
  };
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

const REVIEW_RECEIPT_TTL_MS = 15 * 60 * 1000;

function sha256(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function secureDigestEqual(left: string, right: string): boolean {
  return (
    /^[a-f0-9]{64}$/u.test(left) &&
    /^[a-f0-9]{64}$/u.test(right) &&
    timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"))
  );
}

function invalidProjection(): never {
  throw new CompletedCandidateServiceError(
    "PERSISTENCE_FAILED",
    "The candidate structural comparison evidence is invalid. Recreate the candidate from synthetic examples.",
  );
}

function requireProjectionBinding(input: {
  projection: unknown;
  projectionSha256: string | null;
  converterVersion: string;
  candidateSha256: string;
  candidateStructureSha256: string;
  inventorySha256: string;
  examples: readonly CompletedCandidateExampleRow[];
  regions: readonly CompletedCandidateRegionRow[];
  candidateDocument?: Uint8Array;
}): CompletedCandidateReviewProjection {
  const parsed = CompletedCandidateReviewProjectionSchema.safeParse(
    input.projection,
  );
  if (
    !parsed.success ||
    input.converterVersion !== COMPLETED_CANDIDATE_CONVERTER_VERSION ||
    !input.projectionSha256 ||
    canonicalSha256(parsed.data) !== input.projectionSha256 ||
    parsed.data.candidateSha256 !== input.candidateSha256 ||
    parsed.data.candidateStructureSha256 !== input.candidateStructureSha256 ||
    parsed.data.inventorySha256 !== input.inventorySha256 ||
    parsed.data.regionCount !== input.regions.length
  ) {
    invalidProjection();
  }
  const examples = [...input.examples].sort(
    (left, right) => left.ordinal - right.ordinal,
  );
  if (
    examples.length < 2 ||
    examples.length > 3 ||
    examples.some((example, index) => example.ordinal !== index + 1) ||
    new Set(examples.map((example) => example.documentStructureSha256)).size !==
      1 ||
    parsed.data.sourceStructureSha256 !==
      examples[0]?.documentStructureSha256 ||
    parsed.data.sourceExampleSha256s.length !== examples.length ||
    parsed.data.sourceExampleSha256s.some(
      (digest, index) => digest !== examples[index]?.minimizedSha256,
    )
  ) {
    invalidProjection();
  }

  const candidateCells = new Map<
    string,
    {
      tag: string;
      tableIndex: number;
      rowIndex: number;
      cellIndex: number;
      displayOrder: number;
    }
  >();
  const labelCells = new Map<
    string,
    { label: string; tableIndex: number; rowIndex: number; cellIndex: number }
  >();
  let displayOrder = 0;
  for (const block of parsed.data.blocks) {
    if (block.kind !== "table") continue;
    for (const row of block.rows) {
      for (const cell of row.cells) {
        if (cell.role.kind === "candidate_region") {
          if (candidateCells.has(cell.role.regionId)) invalidProjection();
          candidateCells.set(cell.role.regionId, {
            tag: cell.role.candidateTag,
            tableIndex: block.tableIndex,
            rowIndex: row.rowIndex,
            cellIndex: cell.cellIndex,
            displayOrder,
          });
          displayOrder += 1;
        } else if (cell.role.kind === "stable_label") {
          if (labelCells.has(cell.role.forRegionId)) invalidProjection();
          labelCells.set(cell.role.forRegionId, {
            label: cell.role.label,
            tableIndex: block.tableIndex,
            rowIndex: row.rowIndex,
            cellIndex: cell.cellIndex,
          });
        }
      }
    }
  }
  if (
    candidateCells.size !== input.regions.length ||
    labelCells.size !== input.regions.length
  ) {
    invalidProjection();
  }
  const relationalRegionIds = new Set(input.regions.map((row) => row.regionId));
  for (const region of input.regions) {
    const candidate = candidateCells.get(region.regionId);
    const label = labelCells.get(region.regionId);
    if (
      region.partName !== "word/document.xml" ||
      !candidate ||
      !label ||
      candidate.tag !== region.candidateTag ||
      candidate.tableIndex !== region.tableIndex ||
      candidate.rowIndex !== region.rowIndex ||
      candidate.cellIndex !== region.cellIndex ||
      candidate.displayOrder !== region.displayOrder ||
      label.label !== region.label ||
      label.tableIndex !== region.tableIndex ||
      label.rowIndex !== region.rowIndex ||
      label.cellIndex !== region.cellIndex - 1
    ) {
      invalidProjection();
    }
  }
  if (
    [...candidateCells.keys()].some(
      (regionId) => !relationalRegionIds.has(regionId),
    ) ||
    [...labelCells.keys()].some(
      (regionId) => !relationalRegionIds.has(regionId),
    )
  ) {
    invalidProjection();
  }

  if (input.candidateDocument) {
    if (sha256(input.candidateDocument) !== input.candidateSha256) {
      invalidProjection();
    }
    let compiled: ReturnType<typeof compileTemplateDocx>;
    try {
      compiled = compileTemplateDocx(input.candidateDocument);
    } catch {
      invalidProjection();
    }
    const regionByTag = new Map(
      input.regions.map((region) => [region.candidateTag, region]),
    );
    const compiledTags = compiled.fields.map(
      (field) => field.rendererBinding.tag,
    );
    if (
      compiled.structureSha256 !== input.candidateStructureSha256 ||
      compiled.stats.blockingUnsupported !== 0 ||
      compiled.fields.length !== input.regions.length ||
      new Set(compiledTags).size !== input.regions.length ||
      compiled.fields.some((field) => {
        const tag = field.rendererBinding.tag;
        const region = tag ? regionByTag.get(tag) : undefined;
        return (
          field.rendererBinding.bindingType !== "content_control" ||
          !region ||
          field.rendererBinding.sdtId !== region.candidateSdtId
        );
      })
    ) {
      invalidProjection();
    }
  }
  return parsed.data;
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

  let comparison: ReturnType<typeof requireComparison>;
  let privacyEvidence: ReturnType<typeof requirePrivacy>;
  let reviewProjection: CompletedCandidateReviewProjection;
  try {
    comparison = requireComparison(converted.comparison);
    privacyEvidence = requirePrivacy(converted.privacyEvidence);
    if (
      comparison.exampleCount !== prepared.length ||
      comparison.candidateFieldCount !== converted.regions.length ||
      privacyEvidence.exampleCount !== prepared.length ||
      converted.inventorySha256 !== canonicalSha256(converted.regions)
    ) {
      invalidProjection();
    }
    reviewProjection = requireProjectionBinding({
      projection: converted.reviewProjection,
      projectionSha256: converted.reviewProjectionSha256,
      converterVersion: converted.converterVersion,
      candidateSha256: converted.candidateSha256,
      candidateStructureSha256: converted.candidateStructureSha256,
      inventorySha256: converted.inventorySha256,
      examples: prepared.map((example, index) => ({
        ordinal: index + 1,
        minimizedSha256: example.metadataEvidence.minimizedSha256,
        documentStructureSha256: converted.exampleStructureSha256,
      })),
      regions: converted.regions.map((region) => ({
        ...region,
        decision: "PENDING",
      })),
      candidateDocument: converted.document,
    });
  } catch (error) {
    await rejectPrepared(
      prepared,
      input.actor,
      "COMPLETED_CANDIDATE_PROJECTION_INVALID",
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
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
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
          comparisonEvidence: asJson(comparison),
          privacyEvidence: asJson(privacyEvidence),
          reviewProjection: asJson(reviewProjection),
          reviewProjectionSha256: converted.reviewProjectionSha256,
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
        actorEmailSnapshot: currentActor.email,
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_CREATED",
        targetType: "TemplateTwinCompletedCandidate",
        targetId: candidateId,
        metadata: {
          candidateSha256: converted.candidateSha256,
          candidateStructureSha256: converted.candidateStructureSha256,
          inventorySha256: converted.inventorySha256,
          reviewProjectionSha256: converted.reviewProjectionSha256,
          reviewProjectionProfileVersion: reviewProjection.profileVersion,
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
  return prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    await lockAndAssertCurrentTemplateTwinPhysician({
      tx,
      actor: input.actor,
    });
    const row = await tx.templateTwinCompletedCandidate.findFirst({
      where: {
        id: input.candidateId,
        practiceId: input.actor.practiceId,
        ...currentCompletedCandidateOwnerWhere(input.actor),
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
        candidateStructureSha256: true,
        inventorySha256: true,
        converterVersion: true,
        comparisonEvidence: true,
        privacyEvidence: true,
        reviewProjection: true,
        reviewProjectionSha256: true,
        examples: {
          orderBy: { ordinal: "asc" },
          select: {
            ordinal: true,
            minimizedSha256: true,
            documentStructureSha256: true,
          },
        },
        regions: {
          orderBy: { displayOrder: "asc" },
          select: {
            regionId: true,
            displayOrder: true,
            label: true,
            evidenceType: true,
            partName: true,
            tableIndex: true,
            rowIndex: true,
            cellIndex: true,
            candidateTag: true,
            candidateSdtId: true,
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
    requireProjectionBinding({
      projection: row.reviewProjection,
      projectionSha256: row.reviewProjectionSha256,
      converterVersion: row.converterVersion,
      candidateSha256: row.candidateSha256,
      candidateStructureSha256: row.candidateStructureSha256,
      inventorySha256: row.inventorySha256,
      examples: row.examples,
      regions: row.regions,
    });
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
  });
}

export async function issueCompletedCandidateReviewPreview(input: {
  candidateId: string;
  actor: CompletedCandidateActor;
}): Promise<CompletedCandidateReviewPreviewDto> {
  const receiptId = randomUUID();
  const receiptSecret = randomBytes(32).toString("base64url");
  const reviewReceipt = `${receiptId}.${receiptSecret}`;

  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      // Load-bearing order: global rollout, practice rollout, candidate, then
      // the newly created receipt. Terminal review repeats this order and
      // locks the receipt before consuming it.
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed) {
        throw new CompletedCandidateServiceError(
          "ROLLOUT_CHANGED",
          `${rollout.code}: Template Twin availability changed before the comparison was opened.`,
        );
      }
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
      await tx.$queryRaw(Prisma.sql`
        SELECT candidate."id"
        FROM "template_twin_completed_candidates" candidate
        WHERE candidate."id" = ${input.candidateId}
          AND candidate."practiceId" = ${input.actor.practiceId}
          AND candidate."createdById" = ${input.actor.userId}
        FOR UPDATE
      `);
      const candidate = await tx.templateTwinCompletedCandidate.findFirst({
        where: {
          id: input.candidateId,
          practiceId: input.actor.practiceId,
          ...currentCompletedCandidateOwnerWhere(input.actor),
        },
        select: {
          id: true,
          practiceId: true,
          createdById: true,
          status: true,
          candidateSha256: true,
          candidateStructureSha256: true,
          inventorySha256: true,
          converterVersion: true,
          reviewProjection: true,
          reviewProjectionSha256: true,
          examples: {
            orderBy: { ordinal: "asc" },
            select: {
              ordinal: true,
              minimizedSha256: true,
              documentStructureSha256: true,
            },
          },
          regions: {
            orderBy: { displayOrder: "asc" },
            select: {
              regionId: true,
              displayOrder: true,
              label: true,
              evidenceType: true,
              partName: true,
              tableIndex: true,
              rowIndex: true,
              cellIndex: true,
              candidateTag: true,
              candidateSdtId: true,
              sourceEvidenceSha256: true,
              decision: true,
            },
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
      if (
        candidate.status !== "PENDING_REVIEW" ||
        candidate.regions.some((region) => region.decision !== "PENDING")
      ) {
        throw new CompletedCandidateServiceError(
          "REVIEW_CONFLICT",
          "This candidate no longer has a pending physician review.",
        );
      }
      const projection = requireProjectionBinding({
        projection: candidate.reviewProjection,
        projectionSha256: candidate.reviewProjectionSha256,
        converterVersion: candidate.converterVersion,
        candidateSha256: candidate.candidateSha256,
        candidateStructureSha256: candidate.candidateStructureSha256,
        inventorySha256: candidate.inventorySha256,
        examples: candidate.examples,
        regions: candidate.regions,
      });
      const createdAt = new Date();
      const expiresAt = new Date(createdAt.getTime() + REVIEW_RECEIPT_TTL_MS);
      await tx.templateTwinCompletedCandidateReviewReceipt.create({
        data: {
          id: receiptId,
          candidateId: candidate.id,
          practiceId: candidate.practiceId,
          reviewedById: input.actor.userId,
          tokenSha256: sha256(reviewReceipt),
          candidateSha256: candidate.candidateSha256,
          candidateStructureSha256: candidate.candidateStructureSha256,
          inventorySha256: candidate.inventorySha256,
          reviewProjectionSha256: candidate.reviewProjectionSha256!,
          converterVersion: candidate.converterVersion,
          globalRolloutGeneration: input.actor.rolloutToken.globalGeneration,
          practiceRolloutGeneration:
            input.actor.rolloutToken.practiceGeneration,
          createdAt,
          expiresAt,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:completed-candidate-review-previewed:${candidate.id}:${receiptId}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: currentActor.email,
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEW_PREVIEWED",
        targetType: "TemplateTwinCompletedCandidate",
        targetId: candidate.id,
        metadata: {
          receiptId,
          candidateSha256: candidate.candidateSha256,
          inventorySha256: candidate.inventorySha256,
          reviewProjectionSha256: candidate.reviewProjectionSha256,
          projectionProfileVersion: projection.profileVersion,
          regionCount: projection.regionCount,
          valuesRedacted: true,
          providerEgress: false,
          expiresAtIso: expiresAt.toISOString(),
          gateOutcome: "terminal_review_receipt_issued",
        },
      });
      return {
        projection,
        reviewReceipt,
        expiresAtIso: expiresAt.toISOString(),
      };
    },
    { isolationLevel: "Serializable" },
  );
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

  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
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
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
      await tx.$queryRaw(Prisma.sql`
        SELECT candidate."id"
        FROM "template_twin_completed_candidates" candidate
        WHERE candidate."id" = ${input.candidateId}
          AND candidate."practiceId" = ${input.actor.practiceId}
          AND candidate."createdById" = ${input.actor.userId}
        FOR UPDATE
      `);
      const candidate = await tx.templateTwinCompletedCandidate.findFirst({
        where: {
          id: input.candidateId,
          practiceId: input.actor.practiceId,
          ...currentCompletedCandidateOwnerWhere(input.actor),
        },
        select: {
          id: true,
          practiceId: true,
          createdById: true,
          status: true,
          candidateSha256: true,
          candidateStructureSha256: true,
          inventorySha256: true,
          converterVersion: true,
          reviewProjection: true,
          reviewProjectionSha256: true,
          examples: {
            orderBy: { ordinal: "asc" },
            select: {
              ordinal: true,
              minimizedSha256: true,
              documentStructureSha256: true,
            },
          },
          regions: {
            orderBy: { displayOrder: "asc" },
            select: {
              id: true,
              regionId: true,
              displayOrder: true,
              label: true,
              evidenceType: true,
              partName: true,
              tableIndex: true,
              rowIndex: true,
              cellIndex: true,
              candidateTag: true,
              candidateSdtId: true,
              sourceEvidenceSha256: true,
              decision: true,
            },
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
      requireProjectionBinding({
        projection: candidate.reviewProjection,
        projectionSha256: candidate.reviewProjectionSha256,
        converterVersion: candidate.converterVersion,
        candidateSha256: candidate.candidateSha256,
        candidateStructureSha256: candidate.candidateStructureSha256,
        inventorySha256: candidate.inventorySha256,
        examples: candidate.examples,
        regions: candidate.regions,
      });

      const receiptId = payload.data.reviewReceipt.slice(
        0,
        payload.data.reviewReceipt.indexOf("."),
      );
      const receiptRows = await tx.$queryRaw<
        CompletedCandidateReviewReceiptRow[]
      >(Prisma.sql`
        SELECT receipt."id", receipt."candidateId", receipt."practiceId",
          receipt."reviewedById", receipt."tokenSha256",
          receipt."candidateSha256", receipt."candidateStructureSha256",
          receipt."inventorySha256", receipt."reviewProjectionSha256",
          receipt."converterVersion", receipt."globalRolloutGeneration",
          receipt."practiceRolloutGeneration", receipt."expiresAt",
          receipt."consumedAt",
          receipt."expiresAt" > clock_timestamp() AS "notExpired"
        FROM "template_twin_completed_candidate_review_receipts" receipt
        WHERE receipt."id" = ${receiptId}
          AND receipt."candidateId" = ${candidate.id}
          AND receipt."practiceId" = ${input.actor.practiceId}
          AND receipt."reviewedById" = ${input.actor.userId}
        FOR UPDATE
      `);
      const receipt = receiptRows[0];
      if (
        !receipt ||
        receipt.candidateId !== candidate.id ||
        receipt.practiceId !== input.actor.practiceId ||
        receipt.reviewedById !== input.actor.userId ||
        !secureDigestEqual(
          receipt.tokenSha256,
          sha256(payload.data.reviewReceipt),
        ) ||
        receipt.candidateSha256 !== candidate.candidateSha256 ||
        receipt.candidateStructureSha256 !==
          candidate.candidateStructureSha256 ||
        receipt.inventorySha256 !== candidate.inventorySha256 ||
        receipt.reviewProjectionSha256 !== candidate.reviewProjectionSha256 ||
        receipt.converterVersion !== COMPLETED_CANDIDATE_CONVERTER_VERSION ||
        BigInt(receipt.globalRolloutGeneration) !==
          input.actor.rolloutToken.globalGeneration ||
        BigInt(receipt.practiceRolloutGeneration) !==
          input.actor.rolloutToken.practiceGeneration ||
        receipt.consumedAt !== null ||
        receipt.notExpired !== true
      ) {
        throw new CompletedCandidateServiceError(
          "REVIEW_PREVIEW_REQUIRED",
          "The protected comparison expired, was already used, or no longer matches. Review the exact redacted structure again.",
        );
      }

      const reviewedAt = new Date();
      const consumed = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        UPDATE "template_twin_completed_candidate_review_receipts"
        SET "consumedAt" = ${reviewedAt}
        WHERE "id" = ${receipt.id}
          AND "consumedAt" IS NULL
          AND "expiresAt" > clock_timestamp()
        RETURNING "id"
      `);
      if (consumed.length !== 1) {
        throw new CompletedCandidateServiceError(
          "REVIEW_PREVIEW_REQUIRED",
          "The protected comparison expired or was already used. Review the exact redacted structure again.",
        );
      }
      for (const region of candidate.regions) {
        const decision = decisionById.get(region.regionId)!;
        const updated =
          await tx.templateTwinCompletedCandidateRegion.updateMany({
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
        data: { status, reviewedAt, reviewReceiptId: receipt.id },
      });
      if (updated.count !== 1) {
        throw new CompletedCandidateServiceError(
          "REVIEW_CONFLICT",
          "The candidate changed while it was being reviewed.",
        );
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:completed-candidate-reviewed:${candidate.id}:${receipt.id}:${status}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: currentActor.email,
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED",
        targetType: "TemplateTwinCompletedCandidate",
        targetId: candidate.id,
        metadata: {
          reviewReceiptId: receipt.id,
          inventorySha256: candidate.inventorySha256,
          reviewProjectionSha256: candidate.reviewProjectionSha256,
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
    },
    { isolationLevel: "Serializable" },
  );
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
      ...currentCompletedCandidateOwnerWhere(input.actor),
      status: "APPROVED",
      converterVersion: COMPLETED_CANDIDATE_CONVERTER_VERSION,
      reviewProjectionSha256: { not: null },
      reviewReceiptId: { not: null },
      regions: { every: { decision: "APPROVED" } },
      reviewReceipt: {
        is: {
          practiceId: input.actor.practiceId,
          reviewedById: input.actor.userId,
          consumedAt: { not: null },
        },
      },
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
      candidateStructureSha256: true,
      inventorySha256: true,
      converterVersion: true,
      reviewProjection: true,
      reviewProjectionSha256: true,
      reviewReceiptId: true,
      reviewedAt: true,
      examples: {
        orderBy: { ordinal: "asc" },
        select: {
          ordinal: true,
          minimizedSha256: true,
          documentStructureSha256: true,
        },
      },
      regions: {
        orderBy: { displayOrder: "asc" },
        select: {
          regionId: true,
          displayOrder: true,
          label: true,
          evidenceType: true,
          partName: true,
          tableIndex: true,
          rowIndex: true,
          cellIndex: true,
          candidateTag: true,
          candidateSdtId: true,
          sourceEvidenceSha256: true,
          decision: true,
        },
      },
      reviewReceipt: {
        select: {
          id: true,
          candidateId: true,
          practiceId: true,
          reviewedById: true,
          tokenSha256: true,
          candidateSha256: true,
          candidateStructureSha256: true,
          inventorySha256: true,
          reviewProjectionSha256: true,
          converterVersion: true,
          globalRolloutGeneration: true,
          practiceRolloutGeneration: true,
          createdAt: true,
          expiresAt: true,
          consumedAt: true,
        },
      },
    },
  });
  if (!candidate || candidate.regions.length < 1) {
    throw new CompletedCandidateServiceError(
      "NOT_FOUND",
      "Candidate not found.",
    );
  }
  assertTemplateTwinRecordOwner(input.actor, {
    practiceId: candidate.practiceId,
    uploadedById: candidate.createdById,
  });
  requireProjectionBinding({
    projection: candidate.reviewProjection,
    projectionSha256: candidate.reviewProjectionSha256,
    converterVersion: candidate.converterVersion,
    candidateSha256: candidate.candidateSha256,
    candidateStructureSha256: candidate.candidateStructureSha256,
    inventorySha256: candidate.inventorySha256,
    examples: candidate.examples,
    regions: candidate.regions,
  });
  const receipt = candidate.reviewReceipt;
  const consumedAtMs = receipt?.consumedAt?.getTime();
  if (
    candidate.converterVersion !== COMPLETED_CANDIDATE_CONVERTER_VERSION ||
    !candidate.reviewProjectionSha256 ||
    !candidate.reviewReceiptId ||
    !candidate.reviewedAt ||
    !receipt ||
    receipt.id !== candidate.reviewReceiptId ||
    receipt.candidateId !== candidate.id ||
    receipt.practiceId !== candidate.practiceId ||
    receipt.reviewedById !== input.actor.userId ||
    !/^[a-f0-9]{64}$/u.test(receipt.tokenSha256) ||
    receipt.candidateSha256 !== candidate.candidateSha256 ||
    receipt.candidateStructureSha256 !== candidate.candidateStructureSha256 ||
    receipt.inventorySha256 !== candidate.inventorySha256 ||
    receipt.reviewProjectionSha256 !== candidate.reviewProjectionSha256 ||
    receipt.converterVersion !== COMPLETED_CANDIDATE_CONVERTER_VERSION ||
    receipt.globalRolloutGeneration < BigInt(1) ||
    receipt.practiceRolloutGeneration < BigInt(1) ||
    receipt.expiresAt.getTime() - receipt.createdAt.getTime() !==
      REVIEW_RECEIPT_TTL_MS ||
    consumedAtMs === undefined ||
    consumedAtMs !== candidate.reviewedAt.getTime() ||
    consumedAtMs < receipt.createdAt.getTime() ||
    consumedAtMs > receipt.expiresAt.getTime()
  ) {
    throw new CompletedCandidateServiceError(
      "PERSISTENCE_FAILED",
      "The approved candidate has no valid redacted comparison proof. Recreate it from synthetic examples.",
    );
  }
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const bytes = await storage.readCandidateArtifact({
    practiceId: candidate.practiceId,
    objectKey: candidate.candidateObjectKey,
    expectedObjectVersionId: candidate.candidateObjectVersionId,
    expectedObjectEtag: candidate.candidateObjectEtag,
    expectedSha256: candidate.candidateSha256,
    expectedSizeBytes: candidate.candidateSizeBytes,
  });
  requireProjectionBinding({
    projection: candidate.reviewProjection,
    projectionSha256: candidate.reviewProjectionSha256,
    converterVersion: candidate.converterVersion,
    candidateSha256: candidate.candidateSha256,
    candidateStructureSha256: candidate.candidateStructureSha256,
    inventorySha256: candidate.inventorySha256,
    examples: candidate.examples,
    regions: candidate.regions,
    candidateDocument: bytes,
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
    const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
      tx,
      actor: input.actor,
    });
    const current = await tx.templateTwinCompletedCandidate.findFirst({
      where: {
        id: candidate.id,
        practiceId: input.actor.practiceId,
        ...currentCompletedCandidateOwnerWhere(input.actor),
        status: "APPROVED",
        candidateSha256: candidate.candidateSha256,
        converterVersion: COMPLETED_CANDIDATE_CONVERTER_VERSION,
        reviewProjectionSha256: candidate.reviewProjectionSha256,
        reviewReceiptId: candidate.reviewReceiptId,
        reviewedAt: candidate.reviewedAt,
        regions: { every: { decision: "APPROVED" } },
        reviewReceipt: {
          is: {
            id: receipt.id,
            practiceId: input.actor.practiceId,
            reviewedById: input.actor.userId,
            consumedAt: receipt.consumedAt,
          },
        },
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
      actorEmailSnapshot: currentActor.email,
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
