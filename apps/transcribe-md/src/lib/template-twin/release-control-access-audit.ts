import "server-only";

import { randomUUID } from "node:crypto";
import { isIP } from "node:net";

import { Prisma } from "@prisma/client";

import releaseControlDatabase from "./release-control-db";

interface TemplateTwinControlAccessInput {
  readonly actorId: string;
  readonly actorEmail: string | null;
  readonly practiceId: string;
  readonly routeKey: string;
  readonly request: Request;
}

function bounded(value: string | null, maximum: number): string | null {
  if (!value) return null;
  const normalized = value.trim();
  return normalized ? normalized.slice(0, maximum) : null;
}

function trustedClientAddress(request: Request): string | null {
  const forwarded = bounded(request.headers.get("x-real-ip"), 64);
  return forwarded && isIP(forwarded) !== 0 ? forwarded : null;
}

/**
 * Append the isolated control process's access receipt to the durable outbox.
 * This uses the release-control connection (which already has outbox INSERT)
 * and never gives the process raw audit-history or session-table privileges.
 */
export async function recordTemplateTwinControlAccess(
  input: TemplateTwinControlAccessInput,
): Promise<void> {
  if (
    !/^[a-z0-9:-]{3,96}$/u.test(input.routeKey) ||
    !["GET", "POST"].includes(input.request.method)
  ) {
    throw new Error("Template Twin control access identity is invalid.");
  }
  const path = new URL(input.request.url).pathname;
  if (!path.startsWith("/api/admin/template-twin/") || path.length > 160) {
    throw new Error("Template Twin control access path is invalid.");
  }
  const id = randomUUID();
  const eventKey = `template-twin:release-admin-access:${id}`;
  const ipAddress = trustedClientAddress(input.request);
  const userAgent = bounded(input.request.headers.get("user-agent"), 512);
  await releaseControlDatabase.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
      "action", "targetId", "targetType", "ipAddress", "userAgent",
      "metadata", "status", "attemptCount", "updatedAt"
    ) VALUES (
      ${id}, ${input.practiceId}, ${input.actorId}, ${input.actorEmail},
      ${eventKey}, 'ADMIN_API_ACCESS'::"AuditAction", ${input.routeKey},
      'TemplateTwinReleaseControl', ${ipAddress}::INET, ${userAgent},
      ${JSON.stringify({
        routeKey: input.routeKey,
        method: input.request.method,
        path,
      })}::JSONB,
      'PENDING', 0, CURRENT_TIMESTAMP
    )
  `);
}
