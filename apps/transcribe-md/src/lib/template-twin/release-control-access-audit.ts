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

interface TemplateTwinControlPageAccessInput {
  readonly actorId: string;
  readonly actorEmail: string | null;
  readonly practiceId: string;
  readonly headers: Pick<Headers, "get">;
}

interface TemplateTwinControlReceiptInput {
  readonly actorId: string;
  readonly actorEmail: string | null;
  readonly practiceId: string;
  readonly routeKey: string;
  readonly method: "GET" | "POST";
  readonly path: string;
  readonly headers: Pick<Headers, "get">;
}

const CONTROL_ID_MAX_LENGTH = 191;
const CONTROL_EMAIL_MAX_LENGTH = 320;
const CONTROL_ROUTE_KEY_MAX_LENGTH = 96;
const CONTROL_PATH_MAX_LENGTH = 160;
const CONTROL_IP_HEADER_MAX_LENGTH = 64;
const CONTROL_USER_AGENT_MAX_LENGTH = 512;

export const TEMPLATE_TWIN_RELEASE_PAGE_PATH =
  "/admin/template-twin-release";
export const TEMPLATE_TWIN_RELEASE_PAGE_ROUTE_KEY =
  "template-twin:release:page";

function boundedHeader(value: string | null, maximum: number): string | null {
  if (!value) return null;
  const normalized = value.trim();
  return normalized ? normalized.slice(0, maximum) : null;
}

function trustedClientAddress(headers: Pick<Headers, "get">): string | null {
  const raw = headers.get("x-real-ip");
  if (raw !== null && raw.trim().length > CONTROL_IP_HEADER_MAX_LENGTH) {
    return null;
  }
  const forwarded = boundedHeader(raw, CONTROL_IP_HEADER_MAX_LENGTH);
  return forwarded && isIP(forwarded) !== 0 ? forwarded : null;
}

function exactIdentity(value: string, maximum: number): string {
  if (
    value.length < 1 ||
    value.length > maximum ||
    value !== value.trim() ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new Error("Template Twin control access identity is invalid.");
  }
  return value;
}

function exactEmail(value: string | null): string | null {
  if (value === null) return null;
  return exactIdentity(value, CONTROL_EMAIL_MAX_LENGTH);
}

function exactRoute(input: TemplateTwinControlReceiptInput): void {
  if (
    !new RegExp(`^[a-z0-9:-]{3,${CONTROL_ROUTE_KEY_MAX_LENGTH}}$`, "u").test(
      input.routeKey,
    ) ||
    input.path.length > CONTROL_PATH_MAX_LENGTH
  ) {
    throw new Error("Template Twin control access identity is invalid.");
  }
  if (input.routeKey === TEMPLATE_TWIN_RELEASE_PAGE_ROUTE_KEY) {
    if (
      input.method !== "GET" ||
      input.path !== TEMPLATE_TWIN_RELEASE_PAGE_PATH
    ) {
      throw new Error("Template Twin control access path is invalid.");
    }
    return;
  }
  if (!input.path.startsWith("/api/admin/template-twin/")) {
    throw new Error("Template Twin control access path is invalid.");
  }
}

async function appendTemplateTwinControlAccess(
  input: TemplateTwinControlReceiptInput,
): Promise<void> {
  const actorId = exactIdentity(input.actorId, CONTROL_ID_MAX_LENGTH);
  const actorEmail = exactEmail(input.actorEmail);
  const practiceId = exactIdentity(input.practiceId, CONTROL_ID_MAX_LENGTH);
  exactRoute(input);

  const id = randomUUID();
  const eventKey = `template-twin:release-admin-access:${id}`;
  const ipAddress = trustedClientAddress(input.headers);
  const userAgent = boundedHeader(
    input.headers.get("user-agent"),
    CONTROL_USER_AGENT_MAX_LENGTH,
  );
  await releaseControlDatabase.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
      "action", "targetId", "targetType", "ipAddress", "userAgent",
      "metadata", "status", "attemptCount", "updatedAt"
    ) VALUES (
      ${id}, ${practiceId}, ${actorId}, ${actorEmail},
      ${eventKey}, 'ADMIN_API_ACCESS'::"AuditAction", ${input.routeKey},
      'TemplateTwinReleaseControl', ${ipAddress}::INET, ${userAgent},
      ${JSON.stringify({
        routeKey: input.routeKey,
        method: input.method,
        path: input.path,
      })}::JSONB,
      'PENDING', 0, CURRENT_TIMESTAMP
    )
  `);
}

/**
 * Append the isolated control process's access receipt to the durable outbox.
 * This uses the release-control connection (which already has outbox INSERT)
 * and never gives the process raw audit-history or session-table privileges.
 */
export async function recordTemplateTwinControlAccess(
  input: TemplateTwinControlAccessInput,
): Promise<void> {
  if (input.request.method !== "GET" && input.request.method !== "POST") {
    throw new Error("Template Twin control access identity is invalid.");
  }
  const path = new URL(input.request.url).pathname;
  await appendTemplateTwinControlAccess({
    actorId: input.actorId,
    actorEmail: input.actorEmail,
    practiceId: input.practiceId,
    routeKey: input.routeKey,
    method: input.request.method,
    path,
    headers: input.request.headers,
  });
}

/**
 * The release workbench is server rendered before any API request exists.
 * Record that sensitive read through an exact, non-caller-selectable route
 * identity and await durability before its control-plane query can begin.
 */
export async function recordTemplateTwinReleasePageAccess(
  input: TemplateTwinControlPageAccessInput,
): Promise<void> {
  await appendTemplateTwinControlAccess({
    actorId: input.actorId,
    actorEmail: input.actorEmail,
    practiceId: input.practiceId,
    routeKey: TEMPLATE_TWIN_RELEASE_PAGE_ROUTE_KEY,
    method: "GET",
    path: TEMPLATE_TWIN_RELEASE_PAGE_PATH,
    headers: input.headers,
  });
}
