import { Prisma, type AuditAction } from "@prisma/client";

const FORBIDDEN_METADATA_KEY =
  /(?:field.?value|corrected.?value|previous.?value|evidence.?quote|transcript|soap.?text|note.?text|patient.?name|date.?of.?birth|diagnosis|medication|allerg)/i;
const MAX_METADATA_BYTES = 16 * 1024;
const MAX_ATTEMPTS = 8;
const PROCESSING_LEASE_MS = 5 * 60 * 1000;

type SafeScalar = string | number | boolean | null;
export type TemplateTwinAuditMetadata = Record<
  string,
  SafeScalar | SafeScalar[] | Record<string, SafeScalar>
>;

interface OutboxCreateClient {
  templateTwinAuditOutbox: {
    create(args: { data: Record<string, unknown> }): Promise<unknown>;
  };
}

interface IdempotentOutboxCreateClient {
  templateTwinAuditOutbox: Pick<
    Prisma.TransactionClient["templateTwinAuditOutbox"],
    "createMany"
  >;
}

interface PendingOutboxRow {
  id: string;
  practiceId: string;
  actorId: string | null;
  actorEmailSnapshot: string | null;
  ipAddress: string | null;
  userAgent: string | null;
  eventKey: string;
  action: AuditAction | string;
  targetId: string | null;
  targetType: string | null;
  metadata: unknown;
  status: string;
  attemptCount: number;
  updatedAt: Date;
}

interface OutboxDrainClient {
  templateTwinAuditOutbox: {
    findFirst(args: Record<string, unknown>): Promise<PendingOutboxRow | null>;
    updateMany(args: Record<string, unknown>): Promise<{ count: number }>;
    update(args: Record<string, unknown>): Promise<unknown>;
  };
  auditLog: {
    create(args: { data: Record<string, unknown> }): Promise<unknown>;
  };
  $transaction(
    callback: (tx: OutboxDrainClient) => Promise<void>,
  ): Promise<void>;
}

export interface EnqueueTemplateTwinAuditInput {
  eventKey: string;
  practiceId: string;
  actorId?: string | null;
  actorEmailSnapshot?: string | null;
  ipAddress?: string | null;
  userAgent?: string | null;
  action: AuditAction | string;
  targetId?: string | null;
  targetType?: string | null;
  metadata?: TemplateTwinAuditMetadata;
}

export class TemplateTwinAuditMetadataError extends Error {
  readonly code = "TEMPLATE_TWIN_AUDIT_METADATA_UNSAFE";

  constructor() {
    super("Template Twin audit metadata contains clinical content.");
    this.name = "TemplateTwinAuditMetadataError";
  }
}

function assertSafeMetadataValue(value: unknown, depth: number): void {
  if (depth > 3) throw new TemplateTwinAuditMetadataError();
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    if (typeof value === "string" && value.length > 512) {
      throw new TemplateTwinAuditMetadataError();
    }
    return;
  }
  if (Array.isArray(value)) {
    if (value.length > 100) throw new TemplateTwinAuditMetadataError();
    for (const item of value) assertSafeMetadataValue(item, depth + 1);
    return;
  }
  if (!value || typeof value !== "object") {
    throw new TemplateTwinAuditMetadataError();
  }
  for (const [key, child] of Object.entries(value)) {
    if (FORBIDDEN_METADATA_KEY.test(key)) {
      throw new TemplateTwinAuditMetadataError();
    }
    assertSafeMetadataValue(child, depth + 1);
  }
}

export function assertTemplateTwinAuditMetadata(
  metadata: TemplateTwinAuditMetadata | undefined,
): void {
  if (metadata === undefined) return;
  assertSafeMetadataValue(metadata, 0);
  if (
    Buffer.byteLength(JSON.stringify(metadata), "utf8") > MAX_METADATA_BYTES
  ) {
    throw new TemplateTwinAuditMetadataError();
  }
}

export async function enqueueTemplateTwinAudit(
  tx: OutboxCreateClient,
  input: EnqueueTemplateTwinAuditInput,
): Promise<void> {
  assertTemplateTwinAuditMetadata(input.metadata);
  await tx.templateTwinAuditOutbox.create({
    data: {
      eventKey: input.eventKey,
      practiceId: input.practiceId,
      actorId: input.actorId ?? null,
      actorEmailSnapshot: input.actorEmailSnapshot ?? null,
      ipAddress: input.ipAddress ?? null,
      userAgent: input.userAgent ?? null,
      action: input.action,
      targetId: input.targetId ?? null,
      targetType: input.targetType ?? null,
      metadata: input.metadata ?? null,
      status: "PENDING",
      attemptCount: 0,
    },
  });
}

/**
 * Idempotent outbox enqueue for retryable worker telemetry. Callers must make
 * eventKey a digest of the complete PHI-safe event identity. A duplicate key
 * therefore means the exact logical event was already durably committed, not
 * that an audit failure may be ignored.
 */
export async function enqueueIdempotentTemplateTwinAudit(
  tx: IdempotentOutboxCreateClient,
  input: EnqueueTemplateTwinAuditInput,
): Promise<"CREATED" | "EXISTS"> {
  assertTemplateTwinAuditMetadata(input.metadata);
  const inserted = await tx.templateTwinAuditOutbox.createMany({
    data: [
      {
        eventKey: input.eventKey,
        practiceId: input.practiceId,
        actorId: input.actorId ?? null,
        actorEmailSnapshot: input.actorEmailSnapshot ?? null,
        ipAddress: input.ipAddress ?? null,
        userAgent: input.userAgent ?? null,
        action: input.action as AuditAction,
        targetId: input.targetId ?? null,
        targetType: input.targetType ?? null,
        metadata: input.metadata ?? Prisma.JsonNull,
        status: "PENDING",
        attemptCount: 0,
      },
    ],
    skipDuplicates: true,
  });
  return inserted.count === 1 ? "CREATED" : "EXISTS";
}

function retryAt(now: Date, attemptCount: number): Date {
  const delayMs = Math.min(60_000 * 2 ** Math.max(0, attemptCount), 3_600_000);
  return new Date(now.getTime() + delayMs);
}

export async function drainTemplateTwinAuditOutbox(input: {
  prisma: OutboxDrainClient;
  now?: Date;
  limit?: number;
}): Promise<{ delivered: number; failed: number; contended: number }> {
  const now = input.now ?? new Date();
  const staleProcessingCutoff = new Date(now.getTime() - PROCESSING_LEASE_MS);
  const limit = Math.max(1, Math.min(input.limit ?? 25, 100));
  let delivered = 0;
  let failed = 0;
  let contended = 0;

  for (let index = 0; index < limit; index += 1) {
    const row = await input.prisma.templateTwinAuditOutbox.findFirst({
      where: {
        OR: [
          { status: "PENDING", availableAt: { lte: now } },
          {
            status: "PROCESSING",
            updatedAt: { lte: staleProcessingCutoff },
          },
        ],
      },
      orderBy: [{ availableAt: "asc" }, { createdAt: "asc" }],
    });
    if (!row) break;

    const claim = await input.prisma.templateTwinAuditOutbox.updateMany({
      where:
        row.status === "PROCESSING"
          ? {
              id: row.id,
              status: "PROCESSING",
              updatedAt: { lte: staleProcessingCutoff },
            }
          : { id: row.id, status: "PENDING" },
      data: { status: "PROCESSING", attemptCount: { increment: 1 } },
    });
    if (claim.count !== 1) {
      contended += 1;
      continue;
    }

    try {
      await input.prisma.$transaction(async (tx) => {
        await tx.auditLog.create({
          data: {
            templateTwinOutboxEventKey: row.eventKey,
            userId: row.actorId,
            userEmailSnapshot: row.actorEmailSnapshot,
            action: row.action,
            targetId: row.targetId,
            targetType: row.targetType,
            ipAddress: row.ipAddress,
            userAgent: row.userAgent,
            metadata: row.metadata,
            success: true,
            errorCode: null,
            timestamp: now,
            practiceId: row.practiceId,
          },
        });
        await tx.templateTwinAuditOutbox.update({
          where: { id: row.id },
          data: {
            status: "DELIVERED",
            deliveredAt: now,
            lastErrorCode: null,
          },
        });
      });
      delivered += 1;
    } catch {
      failed += 1;
      const exhausted = row.attemptCount + 1 >= MAX_ATTEMPTS;
      await input.prisma.templateTwinAuditOutbox.update({
        where: { id: row.id },
        data: exhausted
          ? {
              status: "FAILED",
              lastErrorCode: "AUDIT_DELIVERY_FAILED",
            }
          : {
              status: "PENDING",
              availableAt: retryAt(now, row.attemptCount),
              lastErrorCode: "AUDIT_DELIVERY_FAILED",
            },
      });
    }
  }

  return { delivered, failed, contended };
}
