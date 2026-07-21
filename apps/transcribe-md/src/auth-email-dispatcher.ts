import { writeFile } from "node:fs/promises";

import prisma from "@meddoc/db";
import { QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE } from "@meddoc/db/production-runtime-principal";

import { drainAuthEmailOutbox } from "@/lib/auth-email-delivery";
import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import { APP_URL } from "@/lib/constants";
import { assertExactDatabasePrincipal } from "@/lib/exact-database-principal";
import { assertQuillmdRuntimeProtocol } from "@/lib/runtime-protocol";

const SERVICE_ROLE = "auth-email-dispatcher";
const DEFAULT_INTERVAL_MS = 1_000;
const HEARTBEAT_PATH = "/tmp/auth-email-dispatcher-heartbeat";
const PRODUCTION_APP_URL = "https://app.quillmd.com";

async function writeHeartbeat(): Promise<void> {
  await writeFile(HEARTBEAT_PATH, new Date().toISOString(), {
    encoding: "utf8",
    mode: 0o600,
  });
}

function intervalMs(): number {
  const raw = process.env.AUTH_EMAIL_DISPATCH_INTERVAL_MS?.trim();
  if (!raw) return DEFAULT_INTERVAL_MS;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < 500 || parsed > 60_000) {
    throw new Error("Auth email dispatcher interval is invalid.");
  }
  return parsed;
}

async function main(): Promise<void> {
  if (process.env.QUILLMD_SERVICE_ROLE !== SERVICE_ROLE) {
    throw new Error("Auth email dispatcher service role is required.");
  }
  assertQuillmdRuntimeProtocol(process.env);
  if (
    process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE !==
    QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE
  ) {
    throw new Error("Exact production database-principal profile is required.");
  }
  if (APP_URL !== PRODUCTION_APP_URL) {
    throw new Error("Exact production physician origin is required.");
  }
  if (!isEmailDeliveryEnabled()) {
    throw new Error("Verified auth email delivery is required.");
  }
  await assertExactDatabasePrincipal({
    prisma,
    loginRole: "meddoc_auth_email_dispatcher",
    boundaryRole: "quillmd_auth_email_dispatcher",
  });
  const delay = intervalMs();
  let stopping = false;
  let lastHealthLogAt = 0;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  while (!stopping) {
    try {
      const result = await drainAuthEmailOutbox({
        // Claim only immediate worker capacity. A row's lease starts at claim,
        // so pre-claiming a serial backlog could expire later rows untouched.
        limit: 1,
        onProgress: writeHeartbeat,
      });
      // Keep the empty-queue case explicit: a completed health census is
      // database-backed progress even when there was nothing to claim.
      await writeHeartbeat();
      if (
        result.delivered > 0 ||
        result.noop > 0 ||
        result.ambiguous > 0 ||
        result.purged > 0
      ) {
        process.stdout.write(
          `${JSON.stringify({ service: SERVICE_ROLE, ...result })}\n`,
        );
      }
      if (result.ambiguous > 0) {
        process.stderr.write(
          `${JSON.stringify({
            service: SERVICE_ROLE,
            code: "AUTH_EMAIL_PROVIDER_OUTCOME_AMBIGUOUS",
            count: result.ambiguous,
          })}\n`,
        );
      }
      const now = Date.now();
      if (now - lastHealthLogAt >= 60_000) {
        process.stdout.write(
          `${JSON.stringify({
            service: SERVICE_ROLE,
            code: "AUTH_EMAIL_HEALTH",
            ...result.health,
          })}\n`,
        );
        if (
          result.health.ambiguous > 0 ||
          result.health.oldestPendingSeconds > 120
        ) {
          process.stderr.write(
            `${JSON.stringify({
              service: SERVICE_ROLE,
              code: "AUTH_EMAIL_OPERATOR_REVIEW_REQUIRED",
              ...result.health,
            })}\n`,
          );
        }
        lastHealthLogAt = now;
      }
    } catch {
      process.stderr.write(
        `${JSON.stringify({
          service: SERVICE_ROLE,
          code: "AUTH_EMAIL_DISPATCH_FAILED",
        })}\n`,
      );
    }
    if (!stopping) {
      await new Promise<void>((resolve) => setTimeout(resolve, delay));
    }
  }
  await prisma.$disconnect();
}

void main().catch(() => {
  process.stderr.write(
    `${JSON.stringify({
      service: SERVICE_ROLE,
      code: "AUTH_EMAIL_DISPATCH_STARTUP_FAILED",
    })}\n`,
  );
  process.exitCode = 1;
});
