import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TemplateTwinAuditMetadataError,
  drainTemplateTwinAuditOutbox,
  enqueueIdempotentTemplateTwinAudit,
  enqueueTemplateTwinAudit,
} from "../audit-outbox";

const create = vi.fn();
const createMany = vi.fn();
const findFirst = vi.fn();
const update = vi.fn();
const updateMany = vi.fn();
const auditCreate = vi.fn();
const transaction = vi.fn(
  async (callback: (tx: typeof db) => Promise<void>): Promise<void> => {
    await callback(db);
  },
);

const db = {
  templateTwinAuditOutbox: {
    create,
    createMany,
    findFirst,
    update,
    updateMany,
  },
  auditLog: { create: auditCreate },
  $transaction: transaction,
};

const event = {
  id: "outbox-1",
  practiceId: "practice-1",
  actorId: "doctor-1",
  actorEmailSnapshot: "doctor@example.test",
  ipAddress: null,
  userAgent: "synthetic-test",
  eventKey: "template:certified:compiled-1:sha-1",
  action: "TEMPLATE_TWIN_CERTIFIED",
  targetId: "compiled-1",
  targetType: "TemplateTwinCompiledVersion",
  metadata: { fieldCount: 4, mappingsSha256: "a".repeat(64) },
  status: "PENDING",
  attemptCount: 0,
  availableAt: new Date("2026-07-15T20:00:00.000Z"),
  deliveredAt: null,
  lastErrorCode: null,
  createdAt: new Date("2026-07-15T20:00:00.000Z"),
  updatedAt: new Date("2026-07-15T20:00:00.000Z"),
};

beforeEach(() => {
  vi.clearAllMocks();
  create.mockResolvedValue(event);
  createMany.mockResolvedValue({ count: 1 });
  findFirst.mockResolvedValue(null);
  updateMany.mockResolvedValue({ count: 1 });
  update.mockResolvedValue(event);
  auditCreate.mockResolvedValue({ id: "audit-1" });
});

describe("Template Twin durable audit outbox", () => {
  it("enqueues a PHI-safe event in the caller transaction", async () => {
    await enqueueTemplateTwinAudit(db, {
      eventKey: event.eventKey,
      practiceId: event.practiceId,
      actorId: event.actorId,
      actorEmailSnapshot: event.actorEmailSnapshot,
      action: event.action,
      targetId: event.targetId,
      targetType: event.targetType,
      metadata: event.metadata,
    });

    expect(create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: event.eventKey,
        status: "PENDING",
        metadata: event.metadata,
      }),
    });
  });

  it("makes a digest-keyed worker audit idempotent without swallowing failures", async () => {
    await expect(
      enqueueIdempotentTemplateTwinAudit(db, {
        eventKey: event.eventKey,
        practiceId: event.practiceId,
        actorId: event.actorId,
        action: event.action,
        targetId: event.targetId,
        targetType: event.targetType,
        metadata: event.metadata,
      }),
    ).resolves.toBe("CREATED");
    createMany.mockResolvedValueOnce({ count: 0 });
    await expect(
      enqueueIdempotentTemplateTwinAudit(db, {
        eventKey: event.eventKey,
        practiceId: event.practiceId,
        actorId: event.actorId,
        action: event.action,
        targetId: event.targetId,
        targetType: event.targetType,
        metadata: event.metadata,
      }),
    ).resolves.toBe("EXISTS");
    createMany.mockRejectedValueOnce(new Error("synthetic outbox unavailable"));
    await expect(
      enqueueIdempotentTemplateTwinAudit(db, {
        eventKey: "synthetic-worker-audit-failure",
        practiceId: event.practiceId,
        actorId: event.actorId,
        action: event.action,
      }),
    ).rejects.toThrow("synthetic outbox unavailable");
  });

  it.each([
    { fieldValue: "Synthetic clinical value" },
    { evidenceQuote: "Synthetic quote" },
    { soapText: "Synthetic SOAP" },
    { transcript: "Synthetic transcript" },
  ])("rejects raw clinical payload-shaped metadata %#", async (metadata) => {
    await expect(
      enqueueTemplateTwinAudit(db, {
        eventKey: `blocked-${Object.keys(metadata)[0]}`,
        practiceId: event.practiceId,
        actorId: event.actorId,
        action: event.action,
        metadata: metadata as unknown as Record<string, string>,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinAuditMetadataError);
    expect(create).not.toHaveBeenCalled();
  });

  it("atomically claims and delivers a pending event exactly once", async () => {
    findFirst.mockResolvedValueOnce(event).mockResolvedValueOnce(null);

    await expect(
      drainTemplateTwinAuditOutbox({
        prisma: db,
        now: new Date("2026-07-15T20:01:00.000Z"),
        limit: 4,
      }),
    ).resolves.toEqual({ delivered: 1, failed: 0, contended: 0 });

    expect(updateMany).toHaveBeenCalledWith({
      where: { id: event.id, status: "PENDING" },
      data: { status: "PROCESSING", attemptCount: { increment: 1 } },
    });
    expect(auditCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: event.action,
        practiceId: event.practiceId,
        metadata: event.metadata,
      }),
    });
    expect(update).toHaveBeenCalledWith({
      where: { id: event.id },
      data: expect.objectContaining({
        status: "DELIVERED",
        deliveredAt: new Date("2026-07-15T20:01:00.000Z"),
      }),
    });
  });

  it("releases a failed delivery for bounded retry without losing the event", async () => {
    findFirst.mockResolvedValueOnce(event).mockResolvedValueOnce(null);
    auditCreate.mockRejectedValueOnce(new Error("synthetic database failure"));

    await expect(
      drainTemplateTwinAuditOutbox({
        prisma: db,
        now: new Date("2026-07-15T20:01:00.000Z"),
        limit: 1,
      }),
    ).resolves.toEqual({ delivered: 0, failed: 1, contended: 0 });

    expect(update).toHaveBeenLastCalledWith({
      where: { id: event.id },
      data: {
        status: "PENDING",
        availableAt: new Date("2026-07-15T20:02:00.000Z"),
        lastErrorCode: "AUDIT_DELIVERY_FAILED",
      },
    });
  });

  it("reclaims an event whose PROCESSING lease was abandoned by a crashed worker", async () => {
    const stale = {
      ...event,
      status: "PROCESSING",
      attemptCount: 1,
      updatedAt: new Date("2026-07-15T19:50:00.000Z"),
    };
    findFirst.mockReset();
    findFirst.mockResolvedValueOnce(stale).mockResolvedValueOnce(null);

    await expect(
      drainTemplateTwinAuditOutbox({
        prisma: db,
        now: new Date("2026-07-15T20:01:00.000Z"),
        limit: 1,
      }),
    ).resolves.toEqual({ delivered: 1, failed: 0, contended: 0 });

    expect(updateMany).toHaveBeenCalledWith({
      where: {
        id: event.id,
        status: "PROCESSING",
        updatedAt: { lte: new Date("2026-07-15T19:56:00.000Z") },
      },
      data: { status: "PROCESSING", attemptCount: { increment: 1 } },
    });
    expect(auditCreate).toHaveBeenCalledTimes(1);
  });
});
