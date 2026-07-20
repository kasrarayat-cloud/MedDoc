import {
  createHash,
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";
import { inflateSync } from "node:zlib";

import {
  delimiterSystemSuffix,
  modelClient,
  wrapAsData,
  type ModelClient,
} from "@meddoc/ai";
import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import { detectStructuredPhi } from "@/lib/note-template-parse/phi-gate";
import { PhiScanSchema } from "@/lib/note-template-parse/note-template-schema";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import {
  buildTemplateTwinProviderOwnershipReceipt,
  runTemplateTwinOwnedModelComplete,
  runWithTemplateTwinProviderOwnershipContext,
  type TemplateTwinProviderOwnershipReceipt,
} from "./provider-ownership";

export const TEMPLATE_TWIN_STATIC_ASSET_SCANNER =
  "template-twin-static-png/1.0.0" as const;

const PNG_SIGNATURE = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);
const MAX_ASSET_BYTES = 5 * 1024 * 1024;
const MAX_DIMENSION = 4096;
const MAX_PIXELS = 16_777_216;
const MAX_OCR_CHARS = 10_000;
const REVIEW_RECEIPT_TTL_MS = 15 * 60 * 1000;
const SHA256_RE = /^[a-f0-9]{64}$/;
const PRIVACY_MODEL =
  process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-opus-4-8";

const STATIC_ASSET_PRIVACY_SYSTEM = [
  "You are a conservative PHI gate for OCR and metadata extracted locally from a reusable clinical-template image.",
  "Identify patient-specific names, dates, ages, identifiers, contact details, record numbers, or unique encounter content.",
  "A reusable practice name or generic logo wording is not patient PHI.",
  "Return phiFields using only `ocrText` or `metadataText`. If uncertain, set anyUncertain true.",
  delimiterSystemSuffix("transcript"),
].join("\n");

const SAFE_PNG_CHUNKS = new Set([
  "IHDR",
  "IDAT",
  "IEND",
  "pHYs",
  "sRGB",
  "gAMA",
  "cHRM",
  "tEXt",
  "iTXt",
]);

export class TemplateTwinStaticAssetError extends Error {
  constructor(
    readonly code:
      | "TT_STATIC_ASSET_ADMIN_REQUIRED"
      | "TT_STATIC_ASSET_INVALID_BYTES"
      | "TT_STATIC_ASSET_TYPE_UNSUPPORTED"
      | "TT_STATIC_ASSET_RESOURCE_LIMIT"
      | "TT_STATIC_ASSET_ANIMATION_OR_POLYGLOT"
      | "TT_STATIC_ASSET_METADATA_UNSCANNABLE"
      | "TT_STATIC_ASSET_OCR_UNAVAILABLE"
      | "TT_STATIC_ASSET_PRIVACY_SCAN_UNAVAILABLE"
      | "TT_STATIC_ASSET_PRIVACY_REJECTED"
      | "TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID"
      | "TT_STATIC_ASSET_PREVIEW_RECEIPT_UNAVAILABLE"
      | "TT_STATIC_ASSET_ROLLOUT_STALE"
      | "TT_STATIC_ASSET_ATTESTATION_REQUIRED"
      | "TT_STATIC_ASSET_NOT_FOUND"
      | "TT_STATIC_ASSET_NOT_APPROVED"
      | "TT_STATIC_ASSET_STALE_DIGEST"
      | "TT_STATIC_ASSET_DECISION_CONFLICT",
    message: string,
    options?: ErrorOptions,
  ) {
    super(`${code}: ${message}`, options);
    this.name = "TemplateTwinStaticAssetError";
  }
}

export interface TemplateTwinStaticAssetActor {
  readonly userId: string;
  readonly userEmail: string;
  readonly practiceId: string;
  readonly role: "ADMIN" | "SUPER_ADMIN" | string;
  /** Pinned at request admission; every state change revalidates it under lock. */
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface LocalStaticAssetOcr {
  scan(input: {
    bytes: Uint8Array;
    mimeType: "image/png";
    width: number;
    height: number;
    maxCharacters: number;
  }): Promise<{
    local: true;
    complete: true;
    engineVersion: string;
    text: string;
  }>;
}

export interface TemplateTwinStaticAssetInspectionEvidence {
  readonly profileVersion: typeof TEMPLATE_TWIN_STATIC_ASSET_SCANNER;
  readonly sha256: string;
  readonly mimeType: "image/png";
  readonly width: number;
  readonly height: number;
  readonly sizeBytes: number;
  readonly scannerVersion: typeof TEMPLATE_TWIN_STATIC_ASSET_SCANNER;
  readonly ocrEngineVersion: string;
  readonly ocrTextSha256: string;
  readonly metadataEvidenceSha256: string;
  readonly privacyEvidenceSha256: string;
  readonly privacyProvider: "anthropic";
  readonly privacyModel: string;
  readonly metadataKinds: readonly string[];
}

export interface TemplateTwinStaticAssetInspection {
  readonly evidence: TemplateTwinStaticAssetInspectionEvidence;
  /** Server-only durable provider authorization. Route responses deliberately
   * project explicit review fields and never serialize this receipt. */
  readonly providerOwnershipReceipt: TemplateTwinProviderOwnershipReceipt;
  /** Ephemeral, authorized-admin preview only. Never persisted by this module. */
  readonly previewBytes: Uint8Array;
}

export interface TemplateTwinStaticAssetReview
  extends TemplateTwinStaticAssetInspection {
  /** Opaque 256-bit, single-use bearer proof. Never persist or render it. */
  readonly previewReviewReceipt: string;
  readonly previewReviewExpiresAtIso: string;
}

export interface TemplateTwinStaticAssetApprovalBinding {
  readonly sha256: string;
  readonly assetId: string;
  readonly decisionId: string;
  readonly decisionVersion: number;
  readonly inspectionEvidenceSha256: string;
  readonly mimeType: "image/png";
  readonly width: number;
  readonly height: number;
  readonly sizeBytes: number;
  readonly scannerVersion: typeof TEMPLATE_TWIN_STATIC_ASSET_SCANNER;
  readonly privacyEvidenceSha256: string;
}

interface StaticAssetDecisionRow {
  id: string;
  version: number;
  decision: string;
  inspectionEvidenceSha256: string;
}

interface StaticAssetRow {
  id: string;
  practiceId: string;
  createdById: string;
  sha256: string;
  mimeType: string;
  width: number;
  height: number;
  sizeBytes: number;
  scannerVersion: string;
  ocrEngineVersion: string;
  ocrTextSha256: string;
  metadataEvidenceSha256: string;
  privacyEvidenceSha256: string;
  privacyScanProvider: string;
  privacyScanModel: string;
  inspectionEvidenceSha256: string;
  inspectionEvidence: unknown;
  providerOwnershipEvidence: unknown;
  providerOwnershipSha256: string | null;
  currentStatus: string;
  currentDecisionVersion: number;
  createdAt: Date;
  updatedAt: Date;
  decisions?: StaticAssetDecisionRow[];
}

function hasExactStaticAssetProviderOwnership(asset: StaticAssetRow): boolean {
  const evidence =
    asset.providerOwnershipEvidence !== null &&
    typeof asset.providerOwnershipEvidence === "object" &&
    !Array.isArray(asset.providerOwnershipEvidence)
      ? (asset.providerOwnershipEvidence as Record<string, unknown>)
      : null;
  const executions = Array.isArray(evidence?.executions)
    ? evidence.executions
    : [];
  const execution =
    executions.length === 1 &&
    executions[0] !== null &&
    typeof executions[0] === "object" &&
    !Array.isArray(executions[0])
      ? (executions[0] as Record<string, unknown>)
      : null;
  return Boolean(
    evidence &&
      asset.providerOwnershipSha256 &&
      SHA256_RE.test(asset.providerOwnershipSha256) &&
      canonicalSha256(evidence) === asset.providerOwnershipSha256 &&
      evidence.contractVersion ===
        "template-twin-provider-ownership-receipt-v2" &&
      evidence.practiceId === asset.practiceId &&
      evidence.actorUserId === asset.createdById &&
      evidence.providerMode === "LIVE" &&
      evidence.syntheticAdmissionId === null &&
      evidence.subjectId === asset.sha256 &&
      evidence.subjectSha256 === asset.sha256 &&
      evidence.visitId === null &&
      evidence.sourceArtifactId === null &&
      evidence.compiledVersionId === null &&
      evidence.noteTemplateId === null &&
      execution?.operation === "STATIC_ASSET_PRIVACY_SCAN" &&
      typeof execution.executionId === "string" &&
      typeof execution.resultSha256 === "string" &&
      SHA256_RE.test(execution.resultSha256),
  );
}

interface StaticAssetReviewReceiptRow {
  id: string;
  practiceId: string;
  reviewedById: string;
  tokenSha256: string;
  assetSha256: string;
  inspectionEvidenceSha256: string;
  scannerVersion: string;
  ocrEngineVersion: string;
  privacyEvidenceSha256: string;
  globalRolloutGeneration: bigint | number | string;
  practiceRolloutGeneration: bigint | number | string;
  expiresAt: Date;
  consumedAt: Date | null;
  notExpired?: boolean;
}

/**
 * PHI-safe practice-admin list item. Deliberately excludes OCR text, image
 * bytes, metadata text, model responses, decision reasons, and user identity.
 */
export interface TemplateTwinStaticAssetListItem {
  readonly sha256: string;
  readonly status: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "REVOKED";
  readonly mimeType: "image/png";
  readonly width: number;
  readonly height: number;
  readonly sizeBytes: number;
  readonly scannerVersion: string;
  readonly ocrEngineVersion: string;
  readonly decisionVersion: number;
  readonly createdAtIso: string;
  readonly updatedAtIso: string;
}

export interface TemplateTwinStaticAssetDb {
  templateTwinStaticAsset: {
    findUnique(args: Record<string, unknown>): Promise<StaticAssetRow | null>;
    findMany(args: Record<string, unknown>): Promise<StaticAssetRow[]>;
    create(args: Record<string, unknown>): Promise<StaticAssetRow>;
  };
  templateTwinStaticAssetDecision: {
    create(args: Record<string, unknown>): Promise<StaticAssetDecisionRow>;
  };
  templateTwinStaticAssetReviewReceipt: {
    create(args: Record<string, unknown>): Promise<StaticAssetReviewReceiptRow>;
  };
  templateTwinAuditOutbox: {
    create(args: { data: Record<string, unknown> }): Promise<unknown>;
  };
  $transaction<T>(
    callback: (tx: TemplateTwinStaticAssetDb) => Promise<T>,
    options?: Record<string, unknown>,
  ): Promise<T>;
  $queryRaw<T = unknown>(query: Prisma.Sql): Promise<T>;
}

export type TemplateTwinStaticAssetClaimDb = TemplateTwinStaticAssetDb;

interface PngInspection {
  width: number;
  height: number;
  metadataKinds: string[];
  metadataText: string;
}

export async function inspectTemplateTwinStaticAsset(input: {
  bytes: Uint8Array;
  claimedMimeType: string;
  actor: TemplateTwinStaticAssetActor;
  ocr: LocalStaticAssetOcr;
  client?: Pick<ModelClient, "complete">;
  ownershipOperationInstance?: "direct" | "review" | "decision";
}): Promise<TemplateTwinStaticAssetInspection> {
  assertPracticeAdmin(input.actor);
  if (input.claimedMimeType.toLowerCase() !== "image/png") {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_TYPE_UNSUPPORTED",
      "The safe-alpha asset workflow accepts non-animated PNG images only.",
    );
  }
  const bytes = Uint8Array.from(input.bytes);
  const png = inspectPng(bytes);
  let ocrResult: Awaited<ReturnType<LocalStaticAssetOcr["scan"]>>;
  try {
    ocrResult = await input.ocr.scan({
      bytes,
      mimeType: "image/png",
      width: png.width,
      height: png.height,
      maxCharacters: MAX_OCR_CHARS,
    });
  } catch (error) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_OCR_UNAVAILABLE",
      "The required bounded local image text inspection did not complete.",
      { cause: error },
    );
  }
  if (
    ocrResult.local !== true ||
    ocrResult.complete !== true ||
    !/^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$/.test(ocrResult.engineVersion) ||
    typeof ocrResult.text !== "string" ||
    ocrResult.text.length > MAX_OCR_CHARS
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_OCR_UNAVAILABLE",
      "The local OCR result was incomplete or exceeded its safety boundary.",
    );
  }
  const privacyText = [ocrResult.text, png.metadataText].join("\n");
  if (
    detectStructuredPhi(privacyText).length > 0 ||
    /<(?:transcript|system|assistant|tool)[_:\s-]/i.test(privacyText)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_PRIVACY_REJECTED",
      "The image or its metadata may contain patient-specific or instruction-like text.",
    );
  }
  const wrapped = wrapAsData(
    JSON.stringify({
      ocrText: ocrResult.text,
      metadataText: png.metadataText,
    }),
    "transcript",
  );
  if (wrapped.injectionAttemptDetected) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_PRIVACY_REJECTED",
      "The image text contains instruction-like content and cannot be approved as a static asset.",
    );
  }
  const sha256 = digest(bytes);
  let privacyScan: { phiFields: string[]; anyUncertain: boolean };
  let providerOwnershipReceipt: TemplateTwinProviderOwnershipReceipt;
  try {
    const owned = await runWithTemplateTwinProviderOwnershipContext(
      {
        practiceId: input.actor.practiceId,
        actorUserId: input.actor.userId,
        visitId: null,
        visitInputMode: null,
        scope: "STATIC_ASSET",
        logicalAttempt: 1,
        subjectId: sha256,
        subjectSha256: sha256,
        sourceArtifactId: null,
        compiledVersionId: null,
        noteTemplateId: null,
        noteTemplateVersion: null,
        sourceLineageId: null,
        sourceLineageVersion: null,
        sourceSha256: null,
        syntheticAdmissionId: null,
        rolloutToken: input.actor.rolloutToken,
      },
      async () => {
        const scan = await runTemplateTwinOwnedModelComplete({
          operation: "STATIC_ASSET_PRIVACY_SCAN",
          operationInstance:
            input.ownershipOperationInstance ?? "direct",
          operationVersion: "template-twin-static-asset-privacy-scan-v1",
          client: input.client ?? modelClient,
          args: {
            practiceId: input.actor.practiceId,
            visitId: null,
            userId: input.actor.userId,
            purpose: "tm_template_phi_scan",
            provider: "anthropic",
            model: PRIVACY_MODEL,
            system: STATIC_ASSET_PRIVACY_SYSTEM,
            user: [
              "Locally extracted static-image evidence:",
              wrapped.wrapped,
            ].join("\n"),
            schema: PhiScanSchema,
            maxTokens: 512,
            temperature: 0,
            retryOnSchemaFail: true,
            useToolUse: {
              name: "submit_template_twin_static_asset_phi_scan",
              description:
                "Report whether locally extracted OCR or metadata may contain patient-specific content.",
            },
          },
        });
        const receipt = buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: sha256,
            subjectSha256: sha256,
            visitId: null,
            sourceArtifactId: null,
            compiledVersionId: null,
            noteTemplateId: null,
          },
          expectedExecutionPlan: [
            {
              operation: "STATIC_ASSET_PRIVACY_SCAN",
              disposition: "EXECUTED",
            },
          ],
        });
        return { scan, receipt };
      },
    );
    privacyScan = owned.scan;
    providerOwnershipReceipt = owned.receipt;
  } catch (error) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_PRIVACY_SCAN_UNAVAILABLE",
      "The required independent privacy scan did not complete.",
      { cause: error },
    );
  }
  if (
    privacyScan.anyUncertain ||
    privacyScan.phiFields.length > 0 ||
    privacyScan.phiFields.some(
      (field) => field !== "ocrText" && field !== "metadataText",
    )
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_PRIVACY_REJECTED",
      "The image or its metadata may contain patient-specific information.",
    );
  }

  const ocrTextSha256 = digestText(ocrResult.text);
  const metadataEvidenceSha256 = canonicalSha256({
    kinds: png.metadataKinds,
    textSha256: digestText(png.metadataText),
  });
  const privacyEvidenceSha256 = canonicalSha256({
    scannerVersion: TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
    ocrEngineVersion: ocrResult.engineVersion,
    ocrTextSha256,
    metadataEvidenceSha256,
    deterministicFindingCount: 0,
    privacyProvider: "anthropic",
    privacyModel: PRIVACY_MODEL,
  });
  return {
    evidence: {
      profileVersion: TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
      sha256,
      mimeType: "image/png",
      width: png.width,
      height: png.height,
      sizeBytes: bytes.byteLength,
      scannerVersion: TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
      ocrEngineVersion: ocrResult.engineVersion,
      ocrTextSha256,
      metadataEvidenceSha256,
      privacyEvidenceSha256,
      privacyProvider: "anthropic",
      privacyModel: PRIVACY_MODEL,
      metadataKinds: png.metadataKinds,
    },
    providerOwnershipReceipt,
    previewBytes: bytes,
  };
}

export async function inspectTemplateTwinStaticAssetForReview(input: {
  bytes: Uint8Array;
  claimedMimeType: string;
  actor: TemplateTwinStaticAssetActor;
  ocr: LocalStaticAssetOcr;
  client?: Pick<ModelClient, "complete">;
  db?: TemplateTwinStaticAssetDb;
}): Promise<TemplateTwinStaticAssetReview> {
  try {
    const inspection = await inspectTemplateTwinStaticAsset({
      ...input,
      ownershipOperationInstance: "review",
    });
    const receiptId = randomUUID();
    const receiptSecret = randomBytes(32).toString("base64url");
    const previewReviewReceipt = `${receiptId}.${receiptSecret}`;
    const expiresAt = new Date(Date.now() + REVIEW_RECEIPT_TTL_MS);
    const inspectionEvidenceSha256 = canonicalSha256(inspection.evidence);
    const db = input.db ?? defaultDb();
    try {
      await db.templateTwinStaticAssetReviewReceipt.create({
        data: {
          id: receiptId,
          practiceId: input.actor.practiceId,
          reviewedById: input.actor.userId,
          tokenSha256: digestText(previewReviewReceipt),
          assetSha256: inspection.evidence.sha256,
          inspectionEvidenceSha256,
          scannerVersion: inspection.evidence.scannerVersion,
          ocrEngineVersion: inspection.evidence.ocrEngineVersion,
          privacyEvidenceSha256: inspection.evidence.privacyEvidenceSha256,
          globalRolloutGeneration:
            input.actor.rolloutToken.globalGeneration,
          practiceRolloutGeneration:
            input.actor.rolloutToken.practiceGeneration,
          expiresAt,
        },
      });
    } catch (error) {
      throw new TemplateTwinStaticAssetError(
        "TT_STATIC_ASSET_PREVIEW_RECEIPT_UNAVAILABLE",
        "The reviewed-image proof could not be stored. Review the image again before approval.",
        { cause: error },
      );
    }
    return {
      ...inspection,
      previewReviewReceipt,
      previewReviewExpiresAtIso: expiresAt.toISOString(),
    };
  } catch (error) {
    if (
      error instanceof TemplateTwinStaticAssetError &&
      error.code !== "TT_STATIC_ASSET_PREVIEW_RECEIPT_UNAVAILABLE"
    ) {
      await auditStaticAssetRejection({
        db: input.db,
        actor: input.actor,
        sha256: digest(input.bytes),
        sizeBytes: input.bytes.byteLength,
        reasonCode: error.code,
      });
    }
    throw error;
  }
}

async function inspectStaticAssetForDecision(input: {
  bytes: Uint8Array;
  claimedMimeType: string;
  actor: TemplateTwinStaticAssetActor;
  ocr: LocalStaticAssetOcr;
  client?: Pick<ModelClient, "complete">;
  db?: TemplateTwinStaticAssetDb;
}): Promise<TemplateTwinStaticAssetInspection> {
  try {
    return await inspectTemplateTwinStaticAsset({
      ...input,
      ownershipOperationInstance: "decision",
    });
  } catch (error) {
    if (error instanceof TemplateTwinStaticAssetError) {
      await auditStaticAssetRejection({
        db: input.db,
        actor: input.actor,
        sha256: digest(input.bytes),
        sizeBytes: input.bytes.byteLength,
        reasonCode: error.code,
      });
    }
    throw error;
  }
}

export async function approveTemplateTwinStaticAsset(input: {
  bytes: Uint8Array;
  claimedMimeType: string;
  actor: TemplateTwinStaticAssetActor;
  ocr: LocalStaticAssetOcr;
  client?: Pick<ModelClient, "complete">;
  attestedReusableBlankAsset: boolean;
  reason: string;
  previewReviewReceipt: string;
  expectedSha256?: string;
  db?: TemplateTwinStaticAssetDb;
}): Promise<TemplateTwinStaticAssetApprovalBinding> {
  if (!input.attestedReusableBlankAsset) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_ATTESTATION_REQUIRED",
      "Confirm that this is a reusable blank practice asset and not patient-specific content.",
    );
  }
  const reason = validReason(input.reason);
  const inspection = await inspectStaticAssetForDecision(input);
  if (
    input.expectedSha256 !== undefined &&
    input.expectedSha256 !== inspection.evidence.sha256
  ) {
    await auditStaticAssetRejection({
      db: input.db,
      actor: input.actor,
      sha256: inspection.evidence.sha256,
      sizeBytes: inspection.evidence.sizeBytes,
      reasonCode: "TT_STATIC_ASSET_STALE_DIGEST",
    });
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "The image bytes changed after review. Review the new image before approval.",
    );
  }
  const inspectionEvidenceSha256 = canonicalSha256(inspection.evidence);
  const db = input.db ?? defaultDb();
  return db.$transaction(
    async (tx) => {
      await lockAndAssertStaticAssetRollout({ tx, actor: input.actor });
      const reviewReceiptId = await lockAndConsumePreviewReviewReceipt({
        tx,
        actor: input.actor,
        token: input.previewReviewReceipt,
        evidence: inspection.evidence,
      });
      await lockExistingStaticAsset({
        tx,
        practiceId: input.actor.practiceId,
        sha256: inspection.evidence.sha256,
      });
      let asset = await tx.templateTwinStaticAsset.findUnique({
        where: {
          practiceId_sha256: {
            practiceId: input.actor.practiceId,
            sha256: inspection.evidence.sha256,
          },
        },
      });
      if (!asset) {
        asset = await tx.templateTwinStaticAsset.create({
          data: staticAssetCreateData(inspection, input.actor),
        });
      } else {
        assertSameInspection(asset, inspection.evidence);
      }
      const version = asset.currentDecisionVersion + 1;
      const decisionId = randomUUID();
      const auditEventKey =
        `template-twin:static-asset-approved:${decisionId}`;
      await enqueueTemplateTwinAudit(tx, {
        eventKey: auditEventKey,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
        targetType: "TemplateTwinStaticAsset",
        targetId: asset.id,
        metadata: {
          decisionId,
          sha256: asset.sha256,
          mimeType: asset.mimeType,
          width: asset.width,
          height: asset.height,
          sizeBytes: asset.sizeBytes,
          decisionVersion: version,
          scannerVersion: asset.scannerVersion,
          ocrEngineVersion: asset.ocrEngineVersion,
          inspectionEvidenceSha256,
        },
      });
      const decision = await tx.templateTwinStaticAssetDecision.create({
        data: {
          id: decisionId,
          assetId: asset.id,
          version,
          decision: "APPROVED",
          reason,
          attestedReusableBlankAsset: true,
          inspectionEvidenceSha256,
          reviewReceiptId,
          auditEventKey,
          decidedById: input.actor.userId,
        },
      });
      return binding(asset, decision);
    },
    { isolationLevel: "Serializable" },
  );
}

export async function rejectTemplateTwinStaticAsset(input: {
  bytes: Uint8Array;
  claimedMimeType: string;
  actor: TemplateTwinStaticAssetActor;
  ocr: LocalStaticAssetOcr;
  client?: Pick<ModelClient, "complete">;
  reason: string;
  expectedSha256?: string;
  db?: TemplateTwinStaticAssetDb;
}): Promise<void> {
  const reason = validReason(input.reason);
  const inspection = await inspectStaticAssetForDecision(input);
  if (
    input.expectedSha256 !== undefined &&
    input.expectedSha256 !== inspection.evidence.sha256
  ) {
    await auditStaticAssetRejection({
      db: input.db,
      actor: input.actor,
      sha256: inspection.evidence.sha256,
      sizeBytes: inspection.evidence.sizeBytes,
      reasonCode: "TT_STATIC_ASSET_STALE_DIGEST",
    });
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "The image bytes changed after review. Review the new image before rejecting it.",
    );
  }
  const inspectionEvidenceSha256 = canonicalSha256(inspection.evidence);
  const db = input.db ?? defaultDb();
  await db.$transaction(
    async (tx) => {
      await lockAndAssertStaticAssetRollout({ tx, actor: input.actor });
      await lockExistingStaticAsset({
        tx,
        practiceId: input.actor.practiceId,
        sha256: inspection.evidence.sha256,
      });
      let asset = await tx.templateTwinStaticAsset.findUnique({
        where: {
          practiceId_sha256: {
            practiceId: input.actor.practiceId,
            sha256: inspection.evidence.sha256,
          },
        },
      });
      if (!asset) {
        asset = await tx.templateTwinStaticAsset.create({
          data: staticAssetCreateData(inspection, input.actor),
        });
      } else {
        assertSameInspection(asset, inspection.evidence);
      }
      if (asset.currentStatus === "REJECTED") return;
      if (asset.currentStatus !== "PENDING_REVIEW") {
        throw new TemplateTwinStaticAssetError(
          "TT_STATIC_ASSET_DECISION_CONFLICT",
          "An approved or revoked asset must use the explicit revocation or reapproval workflow.",
        );
      }
      const version = asset.currentDecisionVersion + 1;
      const decisionId = randomUUID();
      const auditEventKey =
        `template-twin:static-asset-rejected:${decisionId}`;
      await enqueueTemplateTwinAudit(tx, {
        eventKey: auditEventKey,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_STATIC_ASSET_REJECTED",
        targetType: "TemplateTwinStaticAsset",
        targetId: asset.id,
        metadata: {
          decisionId,
          sha256: asset.sha256,
          decisionVersion: version,
          inspectionEvidenceSha256,
          reasonCode: "ADMIN_REJECTED_REUSABLE_ASSET",
        },
      });
      await tx.templateTwinStaticAssetDecision.create({
        data: {
          id: decisionId,
          assetId: asset.id,
          version,
          decision: "REJECTED",
          reason,
          attestedReusableBlankAsset: false,
          inspectionEvidenceSha256,
          auditEventKey,
          decidedById: input.actor.userId,
        },
      });
    },
    { isolationLevel: "Serializable" },
  );
}

export async function revokeTemplateTwinStaticAsset(input: {
  practiceId: string;
  sha256: string;
  actor: TemplateTwinStaticAssetActor;
  reason: string;
  db?: TemplateTwinStaticAssetDb;
}): Promise<void> {
  assertPracticeAdmin(input.actor);
  if (
    input.practiceId !== input.actor.practiceId ||
    !SHA256_RE.test(input.sha256)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_NOT_FOUND",
      "The practice asset was not found.",
    );
  }
  const reason = validReason(input.reason);
  const db = input.db ?? defaultDb();
  await db.$transaction(
    async (tx) => {
      await lockAndAssertStaticAssetRollout({ tx, actor: input.actor });
      await lockExistingStaticAsset({
        tx,
        practiceId: input.practiceId,
        sha256: input.sha256,
      });
      const asset = await tx.templateTwinStaticAsset.findUnique({
        where: {
          practiceId_sha256: {
            practiceId: input.practiceId,
            sha256: input.sha256,
          },
        },
      });
      if (!asset) {
        throw new TemplateTwinStaticAssetError(
          "TT_STATIC_ASSET_NOT_FOUND",
          "The practice asset was not found.",
        );
      }
      if (asset.currentStatus !== "APPROVED") {
        throw new TemplateTwinStaticAssetError(
          "TT_STATIC_ASSET_NOT_APPROVED",
          "Only a currently approved practice asset can be revoked.",
        );
      }
      const current = await currentDecision(tx, asset);
      const version = asset.currentDecisionVersion + 1;
      const decisionId = randomUUID();
      const auditEventKey =
        `template-twin:static-asset-revoked:${decisionId}`;
      await enqueueTemplateTwinAudit(tx, {
        eventKey: auditEventKey,
        practiceId: input.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_STATIC_ASSET_REVOKED",
        targetType: "TemplateTwinStaticAsset",
        targetId: asset.id,
        metadata: {
          decisionId,
          sha256: asset.sha256,
          decisionVersion: version,
          priorDecisionVersion: current.version,
          inspectionEvidenceSha256: current.inspectionEvidenceSha256,
        },
      });
      await tx.templateTwinStaticAssetDecision.create({
        data: {
          id: decisionId,
          assetId: asset.id,
          version,
          decision: "REVOKED",
          reason,
          attestedReusableBlankAsset: false,
          inspectionEvidenceSha256: current.inspectionEvidenceSha256,
          auditEventKey,
          decidedById: input.actor.userId,
        },
      });
    },
    { isolationLevel: "Serializable" },
  );
}

/**
 * Lists byte identities and decision state for the current practice only.
 * This is a management index, not an image or inspection-evidence endpoint.
 */
export async function listTemplateTwinStaticAssetsForPractice(input: {
  actor: TemplateTwinStaticAssetActor;
  db?: TemplateTwinStaticAssetDb;
}): Promise<readonly TemplateTwinStaticAssetListItem[]> {
  assertPracticeAdmin(input.actor);
  const db = input.db ?? defaultDb();
  const assets = await db.templateTwinStaticAsset.findMany({
    where: { practiceId: input.actor.practiceId },
    orderBy: [{ updatedAt: "desc" }, { sha256: "asc" }],
    take: 100,
  });

  return assets.map((asset) => {
    if (
      asset.practiceId !== input.actor.practiceId ||
      !SHA256_RE.test(asset.sha256) ||
      asset.mimeType !== "image/png" ||
      asset.width < 1 ||
      asset.height < 1 ||
      asset.sizeBytes < 1 ||
      !Number.isInteger(asset.currentDecisionVersion) ||
      asset.currentDecisionVersion < 0 ||
      !(asset.createdAt instanceof Date) ||
      !Number.isFinite(asset.createdAt.getTime()) ||
      !(asset.updatedAt instanceof Date) ||
      !Number.isFinite(asset.updatedAt.getTime()) ||
      !["PENDING_REVIEW", "APPROVED", "REJECTED", "REVOKED"].includes(
        asset.currentStatus,
      )
    ) {
      throw new TemplateTwinStaticAssetError(
        "TT_STATIC_ASSET_DECISION_CONFLICT",
        "The practice asset index is inconsistent and cannot be displayed safely.",
      );
    }
    return {
      sha256: asset.sha256,
      status: asset.currentStatus as TemplateTwinStaticAssetListItem["status"],
      mimeType: "image/png" as const,
      width: asset.width,
      height: asset.height,
      sizeBytes: asset.sizeBytes,
      scannerVersion: asset.scannerVersion,
      ocrEngineVersion: asset.ocrEngineVersion,
      decisionVersion: asset.currentDecisionVersion,
      createdAtIso: asset.createdAt.toISOString(),
      updatedAtIso: asset.updatedAt.toISOString(),
    };
  });
}

export async function resolveApprovedTemplateTwinStaticAssets(input: {
  practiceId: string;
  sha256: readonly string[];
  db?: TemplateTwinStaticAssetDb;
}): Promise<readonly TemplateTwinStaticAssetApprovalBinding[]> {
  const digests = [...new Set(input.sha256)].sort();
  if (digests.length > 100 || digests.some((value) => !SHA256_RE.test(value))) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_NOT_APPROVED",
      "The source contains an invalid or excessive static-asset set.",
    );
  }
  if (digests.length === 0) return [];
  const db = input.db ?? defaultDb();
  const assets = await db.templateTwinStaticAsset.findMany({
    where: {
      practiceId: input.practiceId,
      sha256: { in: digests },
      currentStatus: "APPROVED",
    },
    include: {
      decisions: { orderBy: { version: "desc" }, take: 1 },
    },
  });
  const byDigest = new Map(assets.map((asset) => [asset.sha256, asset]));
  return digests.map((sha256) => {
    const asset = byDigest.get(sha256);
    const decision = asset?.decisions?.[0];
    if (
      !asset ||
      asset.practiceId !== input.practiceId ||
      asset.currentStatus !== "APPROVED" ||
      !decision ||
      decision.decision !== "APPROVED" ||
      decision.version !== asset.currentDecisionVersion ||
      !hasExactStaticAssetProviderOwnership(asset) ||
      !SHA256_RE.test(decision.inspectionEvidenceSha256) ||
      decision.inspectionEvidenceSha256 !== asset.inspectionEvidenceSha256
    ) {
      throw new TemplateTwinStaticAssetError(
        "TT_STATIC_ASSET_NOT_APPROVED",
        "Every image must have a current byte-exact approval for this practice.",
      );
    }
    return binding(asset, decision);
  });
}

export async function assertTemplateTwinStaticAssetBindingsCurrent(input: {
  practiceId: string;
  bindings: readonly TemplateTwinStaticAssetApprovalBinding[];
  db?: TemplateTwinStaticAssetDb;
}): Promise<void> {
  const current = await resolveApprovedTemplateTwinStaticAssets({
    practiceId: input.practiceId,
    sha256: input.bindings.map((item) => item.sha256),
    db: input.db,
  });
  if (
    canonicalSha256(current) !==
    canonicalSha256([...input.bindings].sort(bindingOrder))
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "A static practice asset approval changed after the template was inspected.",
    );
  }
}

/**
 * Linearization boundary for a source-artifact claim or certification that
 * depends on approved static practice assets.
 *
 * Call this only from the caller's final database transaction. Asset rows are
 * locked in canonical primary-key order before their current decision is read.
 * The decision trigger uses `FOR UPDATE` on the same row, so a revocation either
 * commits first (this check sees REVOKED and fails) or waits until the earlier
 * claim commits. Serializable isolation by itself is insufficient because it
 * may legally serialize an unlocked stale read before a revocation that returns
 * first in wall-clock order.
 */
export async function lockAndAssertTemplateTwinStaticAssetBindingsCurrent(input: {
  practiceId: string;
  bindings: readonly TemplateTwinStaticAssetApprovalBinding[];
  db: TemplateTwinStaticAssetClaimDb;
}): Promise<void> {
  if (input.bindings.length === 0) return;
  if (input.bindings.length > 100) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "The source contains an excessive static-asset approval set.",
    );
  }

  const assetIds = [
    ...new Set(input.bindings.map((binding) => binding.assetId)),
  ].sort((left, right) => left.localeCompare(right));
  if (assetIds.length !== input.bindings.length) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "A static practice asset binding is duplicated or inconsistent.",
    );
  }

  const locked = await input.db.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT asset."id"
    FROM "template_twin_static_assets" asset
    WHERE asset."practiceId" = ${input.practiceId}
      AND asset."id" IN (${Prisma.join(assetIds)})
    ORDER BY asset."id"
    FOR SHARE
  `);
  const lockedIds = new Set(locked.map((row) => row.id));
  if (
    lockedIds.size !== assetIds.length ||
    assetIds.some((assetId) => !lockedIds.has(assetId))
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_NOT_APPROVED",
      "Every image must have a current byte-exact approval for this practice.",
    );
  }

  await assertTemplateTwinStaticAssetBindingsCurrent({
    practiceId: input.practiceId,
    bindings: input.bindings,
    db: input.db,
  });
}

export function assertTemplateTwinStaticAssetPackageMatchesApproval(input: {
  bytes: Uint8Array;
  binding: TemplateTwinStaticAssetApprovalBinding;
}): void {
  const inspected = inspectPng(input.bytes);
  if (
    input.binding.mimeType !== "image/png" ||
    input.binding.scannerVersion !== TEMPLATE_TWIN_STATIC_ASSET_SCANNER ||
    input.binding.sha256 !== digest(input.bytes) ||
    input.binding.sizeBytes !== input.bytes.byteLength ||
    input.binding.width !== inspected.width ||
    input.binding.height !== inspected.height ||
    !SHA256_RE.test(input.binding.privacyEvidenceSha256)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "The embedded image no longer matches its exact approved inspection identity.",
    );
  }
}

async function lockAndAssertStaticAssetRollout(input: {
  tx: TemplateTwinStaticAssetDb;
  actor: TemplateTwinStaticAssetActor;
}): Promise<void> {
  const decision = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.actor.practiceId,
    pinnedToken: input.actor.rolloutToken,
  });
  if (!decision.allowed) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_ROLLOUT_STALE",
      decision.reason,
    );
  }
}

/** Lock order is global rollout, practice rollout, review receipt, then asset. */
async function lockAndConsumePreviewReviewReceipt(input: {
  tx: TemplateTwinStaticAssetDb;
  actor: TemplateTwinStaticAssetActor;
  token: string;
  evidence: TemplateTwinStaticAssetInspectionEvidence;
}): Promise<string> {
  const parsed = parsePreviewReviewReceipt(input.token);
  const rows = await input.tx.$queryRaw<StaticAssetReviewReceiptRow[]>(Prisma.sql`
    SELECT receipt."id", receipt."practiceId", receipt."reviewedById",
      receipt."tokenSha256", receipt."assetSha256",
      receipt."inspectionEvidenceSha256", receipt."scannerVersion",
      receipt."ocrEngineVersion", receipt."privacyEvidenceSha256",
      receipt."globalRolloutGeneration", receipt."practiceRolloutGeneration",
      receipt."expiresAt", receipt."consumedAt",
      receipt."expiresAt" > CURRENT_TIMESTAMP AS "notExpired"
    FROM "template_twin_static_asset_review_receipts" receipt
    WHERE receipt."id" = ${parsed.id}
    FOR UPDATE
  `);
  const receipt = rows[0];
  const evidenceSha256 = canonicalSha256(input.evidence);
  if (
    !receipt ||
    receipt.practiceId !== input.actor.practiceId ||
    receipt.reviewedById !== input.actor.userId ||
    !timingSafeDigestEqual(receipt.tokenSha256, digestText(input.token)) ||
    receipt.assetSha256 !== input.evidence.sha256 ||
    receipt.inspectionEvidenceSha256 !== evidenceSha256 ||
    receipt.scannerVersion !== input.evidence.scannerVersion ||
    receipt.ocrEngineVersion !== input.evidence.ocrEngineVersion ||
    receipt.privacyEvidenceSha256 !== input.evidence.privacyEvidenceSha256 ||
    BigInt(receipt.globalRolloutGeneration) !==
      input.actor.rolloutToken.globalGeneration ||
    BigInt(receipt.practiceRolloutGeneration) !==
      input.actor.rolloutToken.practiceGeneration ||
    receipt.consumedAt !== null ||
    receipt.notExpired !== true
  ) {
    invalidPreviewReviewReceipt();
  }
  const consumed = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    UPDATE "template_twin_static_asset_review_receipts"
    SET "consumedAt" = CURRENT_TIMESTAMP
    WHERE "id" = ${receipt.id}
      AND "consumedAt" IS NULL
      AND "expiresAt" > CURRENT_TIMESTAMP
    RETURNING "id"
  `);
  if (consumed.length !== 1) invalidPreviewReviewReceipt();
  return receipt.id;
}

async function lockExistingStaticAsset(input: {
  tx: TemplateTwinStaticAssetDb;
  practiceId: string;
  sha256: string;
}): Promise<void> {
  await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT asset."id"
    FROM "template_twin_static_assets" asset
    WHERE asset."practiceId" = ${input.practiceId}
      AND asset."sha256" = ${input.sha256}
    FOR UPDATE
  `);
}

function parsePreviewReviewReceipt(token: string): {
  id: string;
} {
  if (typeof token !== "string") invalidPreviewReviewReceipt();
  const match =
    /^([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.([A-Za-z0-9_-]{43})$/.exec(
      token,
    );
  if (!match) invalidPreviewReviewReceipt();
  return { id: match[1]! };
}

function timingSafeDigestEqual(left: string, right: string): boolean {
  if (!SHA256_RE.test(left) || !SHA256_RE.test(right)) return false;
  return timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"));
}

function invalidPreviewReviewReceipt(): never {
  throw new TemplateTwinStaticAssetError(
    "TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID",
    "The image preview proof is missing, expired, already used, or no longer matches. Review the exact image again.",
  );
}

async function auditStaticAssetRejection(input: {
  db?: TemplateTwinStaticAssetDb;
  actor: TemplateTwinStaticAssetActor;
  sha256: string;
  sizeBytes: number;
  reasonCode: string;
}): Promise<void> {
  const db = input.db ?? defaultDb();
  await db.$transaction(async (tx) => {
    await enqueueTemplateTwinAudit(tx, {
      eventKey: `template-twin:static-asset-rejected:${input.sha256}:${randomUUID()}`,
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      actorEmailSnapshot: input.actor.userEmail,
      action: "TEMPLATE_TWIN_STATIC_ASSET_REJECTED",
      targetType: "TemplateTwinStaticAssetCandidate",
      targetId: input.sha256,
      metadata: {
        sha256: input.sha256,
        sizeBytes: input.sizeBytes,
        reasonCode: input.reasonCode,
        scannerVersion: TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
      },
    });
  });
}

function inspectPng(bytes: Uint8Array): PngInspection {
  if (
    bytes.byteLength < 8 ||
    !equalBytes(bytes.subarray(0, 8), PNG_SIGNATURE)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_INVALID_BYTES",
      "The file bytes are not a PNG image.",
    );
  }
  if (bytes.byteLength > MAX_ASSET_BYTES) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_RESOURCE_LIMIT",
      "The image exceeds the five-megabyte safe-alpha limit.",
    );
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let bytesPerPixel = 0;
  let sawIhdr = false;
  let sawIdat = false;
  let sawIend = false;
  let leftIdatSequence = false;
  const idat: Uint8Array[] = [];
  const metadataKinds: string[] = [];
  const metadataText: string[] = [];

  while (offset < bytes.byteLength) {
    if (offset + 12 > bytes.byteLength) invalidPng();
    const length = readU32(bytes, offset);
    const type = ascii(bytes.subarray(offset + 4, offset + 8));
    const end = offset + 12 + length;
    if (!/^[A-Za-z]{4}$/.test(type) || end > bytes.byteLength) invalidPng();
    const data = bytes.subarray(offset + 8, offset + 8 + length);
    const expectedCrc = readU32(bytes, offset + 8 + length);
    if (
      crc32(bytes.subarray(offset + 4, offset + 8 + length)) !== expectedCrc
    ) {
      invalidPng();
    }
    if (!SAFE_PNG_CHUNKS.has(type)) {
      throw new TemplateTwinStaticAssetError(
        type === "acTL" || type === "fcTL" || type === "fdAT"
          ? "TT_STATIC_ASSET_ANIMATION_OR_POLYGLOT"
          : "TT_STATIC_ASSET_METADATA_UNSCANNABLE",
        "The PNG contains an unsupported chunk.",
      );
    }
    if (!sawIhdr && type !== "IHDR") invalidPng();
    if (type === "IHDR") {
      if (sawIhdr || length !== 13) invalidPng();
      sawIhdr = true;
      width = readU32(data, 0);
      height = readU32(data, 4);
      const bitDepth = data[8];
      const colorType = data[9];
      if (
        bitDepth !== 8 ||
        (colorType !== 2 && colorType !== 6) ||
        data[10] !== 0 ||
        data[11] !== 0 ||
        data[12] !== 0
      ) {
        throw new TemplateTwinStaticAssetError(
          "TT_STATIC_ASSET_TYPE_UNSUPPORTED",
          "Use a non-interlaced 8-bit RGB or RGBA PNG.",
        );
      }
      bytesPerPixel = colorType === 2 ? 3 : 4;
      if (
        width < 1 ||
        height < 1 ||
        width > MAX_DIMENSION ||
        height > MAX_DIMENSION ||
        width * height > MAX_PIXELS
      ) {
        throw new TemplateTwinStaticAssetError(
          "TT_STATIC_ASSET_RESOURCE_LIMIT",
          "The image dimensions exceed the bounded preview profile.",
        );
      }
    } else if (type === "IDAT") {
      if (!sawIhdr || leftIdatSequence || sawIend) invalidPng();
      sawIdat = true;
      idat.push(Uint8Array.from(data));
    } else {
      if (sawIdat) leftIdatSequence = true;
      if (type === "IEND") {
        if (length !== 0 || sawIend || !sawIdat) invalidPng();
        sawIend = true;
        if (end !== bytes.byteLength) {
          throw new TemplateTwinStaticAssetError(
            "TT_STATIC_ASSET_ANIMATION_OR_POLYGLOT",
            "Trailing data after PNG IEND is not allowed.",
          );
        }
      } else if (type === "tEXt") {
        metadataKinds.push(type);
        metadataText.push(parsePngText(data));
      } else if (type === "iTXt") {
        metadataKinds.push(type);
        metadataText.push(parsePngInternationalText(data));
      } else {
        assertFixedMetadataChunk(type, data);
        metadataKinds.push(type);
      }
    }
    offset = end;
  }
  if (!sawIhdr || !sawIdat || !sawIend || offset !== bytes.byteLength)
    invalidPng();

  const expectedInflated = (width * bytesPerPixel + 1) * height;
  let inflated: Buffer;
  try {
    inflated = inflateSync(
      Buffer.concat(idat.map((item) => Buffer.from(item))),
      {
        maxOutputLength: expectedInflated + 1,
      },
    );
  } catch (error) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_INVALID_BYTES",
      "The PNG pixel stream is malformed or exceeds its declared dimensions.",
      { cause: error },
    );
  }
  if (inflated.byteLength !== expectedInflated) invalidPng();
  const scanlineBytes = width * bytesPerPixel + 1;
  for (let row = 0; row < height; row += 1) {
    if (inflated[row * scanlineBytes]! > 4) invalidPng();
  }
  return {
    width,
    height,
    metadataKinds: [...new Set(metadataKinds)].sort(),
    metadataText: metadataText.join("\n"),
  };
}

function parsePngText(data: Uint8Array): string {
  const separator = data.indexOf(0);
  if (separator < 1 || separator > 79) unscannableMetadata();
  return new TextDecoder("latin1").decode(data);
}

function parsePngInternationalText(data: Uint8Array): string {
  const first = data.indexOf(0);
  if (first < 1 || first > 79 || first + 2 >= data.length)
    unscannableMetadata();
  if (data[first + 1] !== 0 || data[first + 2] !== 0) unscannableMetadata();
  const languageEnd = data.indexOf(0, first + 3);
  const translatedEnd = languageEnd < 0 ? -1 : data.indexOf(0, languageEnd + 1);
  if (languageEnd < 0 || translatedEnd < 0) unscannableMetadata();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(data);
  } catch {
    unscannableMetadata();
  }
}

function assertFixedMetadataChunk(type: string, data: Uint8Array): void {
  const expected =
    type === "pHYs"
      ? 9
      : type === "sRGB"
        ? 1
        : type === "gAMA"
          ? 4
          : type === "cHRM"
            ? 32
            : -1;
  if (data.byteLength !== expected) unscannableMetadata();
}

function invalidPng(): never {
  throw new TemplateTwinStaticAssetError(
    "TT_STATIC_ASSET_INVALID_BYTES",
    "The PNG package is malformed.",
  );
}

function unscannableMetadata(): never {
  throw new TemplateTwinStaticAssetError(
    "TT_STATIC_ASSET_METADATA_UNSCANNABLE",
    "The PNG contains metadata that cannot be fully inspected.",
  );
}

function assertSameInspection(
  asset: StaticAssetRow,
  evidence: TemplateTwinStaticAssetInspectionEvidence,
): void {
  const persisted = {
    profileVersion: TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
    sha256: asset.sha256,
    mimeType: asset.mimeType,
    width: asset.width,
    height: asset.height,
    sizeBytes: asset.sizeBytes,
    scannerVersion: asset.scannerVersion,
    ocrEngineVersion: asset.ocrEngineVersion,
    ocrTextSha256: asset.ocrTextSha256,
    metadataEvidenceSha256: asset.metadataEvidenceSha256,
    privacyEvidenceSha256: asset.privacyEvidenceSha256,
    privacyProvider: asset.privacyScanProvider,
    privacyModel: asset.privacyScanModel,
    metadataKinds:
      typeof asset.inspectionEvidence === "object" &&
      asset.inspectionEvidence !== null &&
      Array.isArray(
        (asset.inspectionEvidence as Record<string, unknown>).metadataKinds,
      )
        ? (asset.inspectionEvidence as { metadataKinds: string[] })
            .metadataKinds
        : [],
  };
  const evidenceSha256 = canonicalSha256(evidence);
  if (
    canonicalSha256(persisted) !== evidenceSha256 ||
    asset.inspectionEvidenceSha256 !== evidenceSha256 ||
    !hasExactStaticAssetProviderOwnership(asset)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_STALE_DIGEST",
      "The stored inspection evidence does not match the reviewed image.",
    );
  }
}

function staticAssetCreateData(
  inspection: TemplateTwinStaticAssetInspection,
  actor: TemplateTwinStaticAssetActor,
): Record<string, unknown> {
  const evidence = inspection.evidence;
  return {
    id: randomUUID(),
    practiceId: actor.practiceId,
    createdById: actor.userId,
    sha256: evidence.sha256,
    mimeType: evidence.mimeType,
    width: evidence.width,
    height: evidence.height,
    sizeBytes: evidence.sizeBytes,
    scannerVersion: evidence.scannerVersion,
    ocrEngineVersion: evidence.ocrEngineVersion,
    ocrTextSha256: evidence.ocrTextSha256,
    metadataEvidenceSha256: evidence.metadataEvidenceSha256,
    privacyEvidenceSha256: evidence.privacyEvidenceSha256,
    privacyScanProvider: evidence.privacyProvider,
    privacyScanModel: evidence.privacyModel,
    inspectionEvidence: evidence,
    inspectionEvidenceSha256: canonicalSha256(evidence),
    providerOwnershipEvidence: inspection.providerOwnershipReceipt.evidence,
    providerOwnershipSha256: inspection.providerOwnershipReceipt.sha256,
    currentStatus: "PENDING_REVIEW",
    currentDecisionVersion: 0,
  };
}

async function currentDecision(
  db: TemplateTwinStaticAssetDb,
  asset: StaticAssetRow,
): Promise<StaticAssetDecisionRow> {
  const refreshed = await db.templateTwinStaticAsset.findUnique({
    where: {
      practiceId_sha256: {
        practiceId: asset.practiceId,
        sha256: asset.sha256,
      },
    },
    include: { decisions: { orderBy: { version: "desc" }, take: 1 } },
  });
  const decision = refreshed?.decisions?.[0];
  if (!decision || decision.version !== refreshed?.currentDecisionVersion) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_DECISION_CONFLICT",
      "The append-only asset decision history is inconsistent.",
    );
  }
  return decision;
}

function binding(
  asset: StaticAssetRow,
  decision: StaticAssetDecisionRow,
): TemplateTwinStaticAssetApprovalBinding {
  return {
    sha256: asset.sha256,
    assetId: asset.id,
    decisionId: decision.id,
    decisionVersion: decision.version,
    inspectionEvidenceSha256: decision.inspectionEvidenceSha256,
    mimeType: asset.mimeType as "image/png",
    width: asset.width,
    height: asset.height,
    sizeBytes: asset.sizeBytes,
    scannerVersion:
      asset.scannerVersion as typeof TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
    privacyEvidenceSha256: asset.privacyEvidenceSha256,
  };
}

function bindingOrder(
  left: TemplateTwinStaticAssetApprovalBinding,
  right: TemplateTwinStaticAssetApprovalBinding,
): number {
  return left.sha256.localeCompare(right.sha256);
}

function assertPracticeAdmin(actor: TemplateTwinStaticAssetActor): void {
  if (
    !actor.userId ||
    !actor.practiceId ||
    !actor.userEmail ||
    (actor.role !== "ADMIN" && actor.role !== "SUPER_ADMIN")
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_ADMIN_REQUIRED",
      "A practice administrator must review reusable document images.",
    );
  }
  if (
    actor.rolloutToken?.practiceId !== actor.practiceId ||
    actor.rolloutToken.globalGeneration < BigInt(1) ||
    actor.rolloutToken.practiceGeneration < BigInt(1)
  ) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_ROLLOUT_STALE",
      "The Template Twin rollout admission is missing or stale. Start the review again.",
    );
  }
}

function validReason(value: string): string {
  const reason = value.trim();
  if (reason.length < 8 || reason.length > 1000) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_ATTESTATION_REQUIRED",
      "Provide an approval or revocation reason between 8 and 1,000 characters.",
    );
  }
  if (detectStructuredPhi(reason).length > 0) {
    throw new TemplateTwinStaticAssetError(
      "TT_STATIC_ASSET_PRIVACY_REJECTED",
      "Do not include patient-specific information in an asset review reason.",
    );
  }
  return reason;
}

function defaultDb(): TemplateTwinStaticAssetDb {
  return prisma as unknown as TemplateTwinStaticAssetDb;
}

function digest(value: Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

function digestText(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function readU32(bytes: Uint8Array, offset: number): number {
  return (
    bytes[offset]! * 0x1000000 +
    bytes[offset + 1]! * 0x10000 +
    bytes[offset + 2]! * 0x100 +
    bytes[offset + 3]!
  );
}

function ascii(bytes: Uint8Array): string {
  return String.fromCharCode(...bytes);
}

function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
  return (
    left.byteLength === right.byteLength &&
    left.every((value, index) => value === right[index])
  );
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
