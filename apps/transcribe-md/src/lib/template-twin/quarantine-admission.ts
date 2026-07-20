import { randomUUID } from "node:crypto";

import type { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import {
  assertTemplateTwinMalwareFree,
  TemplateTwinMalwareRejectedError,
  TemplateTwinMalwareScanUnavailableError,
  type TemplateTwinMalwareScanEvidence,
  type TemplateTwinMalwareScanner,
} from "./malware-scan";
import type { TemplateTwinMetadataEvidence } from "./source-metadata";
import {
  claimTemplateTwinObject,
  createTemplateTwinArtifactStore,
  DOCX_MIME_TYPE,
  type StoredTemplateTwinArtifact,
  type TemplateTwinArtifactStore,
} from "./storage";
import { lockAndAssertCurrentTemplateTwinPhysician } from "./final-claim-authority";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";

export type TemplateTwinIntakeMode = "NATIVE_TEMPLATE" | "COMPLETED_EXAMPLE";

export interface TemplateTwinIntakeActor {
  readonly userId: string;
  readonly userEmail: string;
  readonly practiceId: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface TemplateTwinQuarantineReceipt {
  readonly id: string;
  readonly lineageId: string;
  readonly lineageVersion: number;
  readonly intakeMode: TemplateTwinIntakeMode;
  readonly stored: StoredTemplateTwinArtifact;
}

export class TemplateTwinQuarantineError extends Error {
  readonly code:
    | "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED"
    | "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT";

  constructor(
    code: TemplateTwinQuarantineError["code"],
    message: string,
    cause?: unknown,
  ) {
    super(message, { cause });
    this.name = "TemplateTwinQuarantineError";
    this.code = code;
  }
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

function safeCode(value: string): string {
  const normalized = value
    .trim()
    .replace(/[^A-Z0-9_:-]/gi, "_")
    .slice(0, 80);
  return normalized || "TEMPLATE_TWIN_INTAKE_REJECTED";
}

export async function beginTemplateTwinQuarantine(input: {
  source: Uint8Array;
  actor: TemplateTwinIntakeActor;
  intakeMode: TemplateTwinIntakeMode;
  lineageId?: string;
  lineageVersion?: number;
  storage?: TemplateTwinArtifactStore;
}): Promise<TemplateTwinQuarantineReceipt> {
  const id = randomUUID();
  const lineageId = input.lineageId ?? randomUUID();
  const lineageVersion = input.lineageVersion ?? 1;
  const storage = input.storage ?? createTemplateTwinArtifactStore();

  // This immutable write is the first operation over the upload bytes. No ZIP
  // parser, malware provider, model, metadata transformer, or compiler may run
  // before it. A failed relational claim remains WRITTEN_UNCLAIMED for the
  // object reconciler; the request never attempts an unsafe delete.
  const stored = await storage.storeQuarantineArtifact({
    practiceId: input.actor.practiceId,
    lineageId,
    lineageVersion,
    bytes: input.source,
  });

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinQuarantineError(
          "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
          "Template Twin availability changed before the upload could be captured in quarantine.",
        );
      }
      const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: input.actor,
      });
      await tx.templateTwinQuarantineArtifact.create({
        data: {
          id,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          lineageId,
          lineageVersion,
          intakeMode: input.intakeMode,
          objectKey: stored.objectKey,
          objectVersionId: stored.objectVersionId,
          objectEtag: stored.objectEtag,
          sha256: stored.sha256,
          mimeType: DOCX_MIME_TYPE,
          sizeBytes: stored.sizeBytes,
          status: "QUARANTINED",
          rejectionCodes: [],
        },
      });
      await claimTemplateTwinObject(tx, {
        objectKey: stored.objectKey,
        practiceId: input.actor.practiceId,
        claimType: "quarantine_artifact",
        claimId: id,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:quarantine-captured:${id}:${stored.sha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: currentActor.email,
        action: "TEMPLATE_TWIN_QUARANTINED",
        targetType: "TemplateTwinQuarantineArtifact",
        targetId: id,
        metadata: {
          sha256: stored.sha256,
          sizeBytes: stored.sizeBytes,
          objectVersionId: stored.objectVersionId,
          objectEtag: stored.objectEtag,
          lineageId,
          lineageVersion,
          intakeMode: input.intakeMode,
          gateOutcome: "pending_malware_scan",
        },
      });
    });
  } catch (error) {
    if (error instanceof TemplateTwinQuarantineError) throw error;
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
      "The upload could not be captured in private quarantine and was not admitted.",
      error,
    );
  }

  return Object.freeze({
    id,
    lineageId,
    lineageVersion,
    intakeMode: input.intakeMode,
    stored,
  });
}

async function recordScanUnavailable(input: {
  receipt: TemplateTwinQuarantineReceipt;
  actor: TemplateTwinIntakeActor;
  code: string;
}): Promise<void> {
  const code = safeCode(input.code);
  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const updated = await tx.templateTwinQuarantineArtifact.updateMany({
        where: {
          id: input.receipt.id,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          status: "QUARANTINED",
          sha256: input.receipt.stored.sha256,
        },
        data: { rejectionCodes: [code] },
      });
      if (updated.count !== 1) {
        throw new TemplateTwinQuarantineError(
          "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
          "The quarantined upload changed while its malware scan was running.",
        );
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:malware-scan-blocked:${input.receipt.id}:${code}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        // Safety bookkeeping may finish after lifecycle revocation. The row
        // predicate above proves the persisted owner; never trust a stale
        // request-start email when recording that terminal outcome.
        actorEmailSnapshot: null,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TemplateTwinQuarantineArtifact",
        targetId: input.receipt.id,
        metadata: {
          sourceSha256: input.receipt.stored.sha256,
          code,
          gate: "malware_scan",
          gateOutcome: "blocked",
        },
      });
    });
  } catch (error) {
    if (error instanceof TemplateTwinQuarantineError) throw error;
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
      "The malware-scan failure could not be recorded. The upload was not admitted.",
      error,
    );
  }
}

export async function scanTemplateTwinQuarantine(input: {
  source: Uint8Array;
  receipt: TemplateTwinQuarantineReceipt;
  actor: TemplateTwinIntakeActor;
  scanner?: TemplateTwinMalwareScanner;
}): Promise<TemplateTwinMalwareScanEvidence> {
  let evidence: TemplateTwinMalwareScanEvidence;
  try {
    evidence = await assertTemplateTwinMalwareFree({
      source: input.source,
      ...(input.scanner ? { scanner: input.scanner } : {}),
    });
  } catch (error) {
    if (error instanceof TemplateTwinMalwareRejectedError) {
      try {
        await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
          const updated = await tx.templateTwinQuarantineArtifact.updateMany({
            where: {
              id: input.receipt.id,
              practiceId: input.actor.practiceId,
              createdById: input.actor.userId,
              status: "QUARANTINED",
              sha256: input.receipt.stored.sha256,
            },
            data: {
              status: "REJECTED",
              malwareScanEvidence: asJson(error.evidence),
              scannedAt: new Date(error.evidence.scannedAt),
              rejectionCodes: [error.code],
            },
          });
          if (updated.count !== 1) {
            throw new TemplateTwinQuarantineError(
              "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
              "The quarantined upload changed while its malware scan was running.",
            );
          }
          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin:malware-rejected:${input.receipt.id}:${error.evidence.attestationSha256}`,
            practiceId: input.actor.practiceId,
            actorId: input.actor.userId,
            actorEmailSnapshot: null,
            action: "TEMPLATE_TWIN_MALWARE_SCANNED",
            targetType: "TemplateTwinQuarantineArtifact",
            targetId: input.receipt.id,
            metadata: {
              sourceSha256: error.evidence.sourceSha256,
              scanner: error.evidence.scanner,
              engineVersion: error.evidence.engineVersion,
              signatureVersion: error.evidence.signatureVersion,
              attestationSha256: error.evidence.attestationSha256,
              verdict: "infected",
              threatNameSha256: error.evidence.threatNameSha256,
              gateOutcome: "blocked",
            },
          });
        });
      } catch (persistenceError) {
        if (persistenceError instanceof TemplateTwinQuarantineError) {
          throw persistenceError;
        }
        throw new TemplateTwinQuarantineError(
          "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
          "The malware rejection could not be recorded. The upload was not admitted.",
          persistenceError,
        );
      }
      throw error;
    }
    if (error instanceof TemplateTwinMalwareScanUnavailableError) {
      await recordScanUnavailable({
        receipt: input.receipt,
        actor: input.actor,
        code: error.code,
      });
    }
    throw error;
  }

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const updated = await tx.templateTwinQuarantineArtifact.updateMany({
        where: {
          id: input.receipt.id,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          status: "QUARANTINED",
          sha256: input.receipt.stored.sha256,
        },
        data: {
          status: "MALWARE_CLEAN",
          malwareScanEvidence: asJson(evidence),
          scannedAt: new Date(evidence.scannedAt),
          rejectionCodes: [],
        },
      });
      if (updated.count !== 1) {
        throw new TemplateTwinQuarantineError(
          "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
          "The quarantined upload changed while its malware scan was running.",
        );
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:malware-clean:${input.receipt.id}:${evidence.attestationSha256}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: null,
        action: "TEMPLATE_TWIN_MALWARE_SCANNED",
        targetType: "TemplateTwinQuarantineArtifact",
        targetId: input.receipt.id,
        metadata: {
          sourceSha256: evidence.sourceSha256,
          scanner: evidence.scanner,
          engineVersion: evidence.engineVersion,
          signatureVersion: evidence.signatureVersion,
          attestationSha256: evidence.attestationSha256,
          verdict: "clean",
          gateOutcome: "passed",
        },
      });
    });
  } catch (error) {
    if (error instanceof TemplateTwinQuarantineError) throw error;
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
      "The clean malware receipt could not be recorded. The upload was not admitted.",
      error,
    );
  }
  return evidence;
}

export async function rejectTemplateTwinQuarantine(input: {
  receipt: TemplateTwinQuarantineReceipt;
  actor: TemplateTwinIntakeActor;
  rejectionCode: string;
  metadataEvidence?: TemplateTwinMetadataEvidence;
}): Promise<void> {
  const rejectionCode = safeCode(input.rejectionCode);
  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      const updated = await tx.templateTwinQuarantineArtifact.updateMany({
        where: {
          id: input.receipt.id,
          practiceId: input.actor.practiceId,
          createdById: input.actor.userId,
          status: { in: ["QUARANTINED", "MALWARE_CLEAN"] },
          sha256: input.receipt.stored.sha256,
        },
        data: {
          status: "REJECTED",
          rejectionCodes: [rejectionCode],
          ...(input.metadataEvidence
            ? { metadataMinimizationEvidence: asJson(input.metadataEvidence) }
            : {}),
        },
      });
      if (updated.count !== 1) {
        throw new TemplateTwinQuarantineError(
          "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
          "The quarantined upload changed before its rejection was recorded.",
        );
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:intake-rejected:${input.receipt.id}:${rejectionCode}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: null,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TemplateTwinQuarantineArtifact",
        targetId: input.receipt.id,
        metadata: {
          sourceSha256: input.receipt.stored.sha256,
          rejectionCode,
          intakeMode: input.receipt.intakeMode,
          gateOutcome: "blocked",
        },
      });
    });
  } catch (error) {
    if (error instanceof TemplateTwinQuarantineError) throw error;
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_PERSISTENCE_FAILED",
      "The quarantine rejection could not be recorded. The upload was not admitted.",
      error,
    );
  }
}

/** Called inside the same transaction that creates the admitted source row. */
export async function admitTemplateTwinQuarantine(input: {
  tx: Prisma.TransactionClient;
  receipt: TemplateTwinQuarantineReceipt;
  actor: TemplateTwinIntakeActor;
  sourceArtifactId: string;
  metadataEvidence: TemplateTwinMetadataEvidence;
}): Promise<void> {
  const rollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.actor.practiceId,
    pinnedToken: input.actor.rolloutToken,
  });
  if (!rollout.allowed) {
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
      "Template Twin availability changed before quarantine admission completed.",
    );
  }
  const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
    tx: input.tx,
    actor: input.actor,
  });
  const admittedAt = new Date();
  const updated = await input.tx.templateTwinQuarantineArtifact.updateMany({
    where: {
      id: input.receipt.id,
      practiceId: input.actor.practiceId,
      createdById: input.actor.userId,
      status: "MALWARE_CLEAN",
      sha256: input.receipt.stored.sha256,
    },
    data: {
      status: "ADMITTED",
      metadataMinimizationEvidence: asJson(input.metadataEvidence),
      admittedAt,
      rejectionCodes: [],
    },
  });
  if (updated.count !== 1) {
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
      "The quarantined upload changed before admission completed.",
    );
  }
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey: `template-twin:metadata-minimized:${input.receipt.id}:${input.metadataEvidence.minimizedSha256}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: currentActor.email,
    action: "TEMPLATE_TWIN_METADATA_MINIMIZED",
    targetType: "TemplateTwinQuarantineArtifact",
    targetId: input.receipt.id,
    metadata: {
      sourceArtifactId: input.sourceArtifactId,
      originalSha256: input.metadataEvidence.originalSha256,
      minimizedSha256: input.metadataEvidence.minimizedSha256,
      profileVersion: input.metadataEvidence.profileVersion,
      replacedParts: [...input.metadataEvidence.replacedParts],
      zipEntryTimestampsNormalized:
        input.metadataEvidence.zipEntryTimestampsNormalized,
      gateOutcome: "admitted",
    },
  });
}

/**
 * Terminally isolates a completed-document example without admitting it as a
 * reusable source. The immutable raw object remains in quarantine; only the
 * metadata-minimized digest and PHI-safe structural receipts are linked to a
 * newly generated candidate.
 */
export async function isolateCompletedExampleQuarantine(input: {
  tx: Prisma.TransactionClient;
  receipt: TemplateTwinQuarantineReceipt;
  actor: TemplateTwinIntakeActor;
  candidateId: string;
  metadataEvidence: TemplateTwinMetadataEvidence;
}): Promise<void> {
  if (input.receipt.intakeMode !== "COMPLETED_EXAMPLE") {
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
      "Only a completed-document example can enter candidate isolation.",
    );
  }
  const rollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.actor.practiceId,
    pinnedToken: input.actor.rolloutToken,
  });
  if (!rollout.allowed) {
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
      "Template Twin availability changed before completed-example isolation.",
    );
  }
  const currentActor = await lockAndAssertCurrentTemplateTwinPhysician({
    tx: input.tx,
    actor: input.actor,
  });
  const isolatedAt = new Date();
  const updated = await input.tx.templateTwinQuarantineArtifact.updateMany({
    where: {
      id: input.receipt.id,
      practiceId: input.actor.practiceId,
      createdById: input.actor.userId,
      status: "MALWARE_CLEAN",
      intakeMode: "COMPLETED_EXAMPLE",
      sha256: input.receipt.stored.sha256,
    },
    data: {
      status: "ISOLATED",
      metadataMinimizationEvidence: asJson(input.metadataEvidence),
      isolatedAt,
      rejectionCodes: [],
    },
  });
  if (updated.count !== 1) {
    throw new TemplateTwinQuarantineError(
      "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT",
      "The completed-document example changed before isolation completed.",
    );
  }
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey: `template-twin:completed-example-isolated:${input.receipt.id}:${input.metadataEvidence.minimizedSha256}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: currentActor.email,
    action: "TEMPLATE_TWIN_METADATA_MINIMIZED",
    targetType: "TemplateTwinQuarantineArtifact",
    targetId: input.receipt.id,
    metadata: {
      candidateId: input.candidateId,
      originalSha256: input.metadataEvidence.originalSha256,
      minimizedSha256: input.metadataEvidence.minimizedSha256,
      profileVersion: input.metadataEvidence.profileVersion,
      replacedParts: [...input.metadataEvidence.replacedParts],
      zipEntryTimestampsNormalized:
        input.metadataEvidence.zipEntryTimestampsNormalized,
      gateOutcome: "isolated_completed_example",
    },
  });
}
