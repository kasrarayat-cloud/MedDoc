import { writeFile } from "node:fs/promises";

import prisma from "@meddoc/db";
import { assertPostgresHostAuthenticationContract } from "@meddoc/db/postgres-host-auth";
import { QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE } from "@meddoc/db/production-runtime-principal";

import { assertExactDatabasePrincipal } from "@/lib/exact-database-principal";
import { assertQuillmdRuntimeProtocol } from "@/lib/runtime-protocol";
import { drainTemplateTwinAuditOutbox } from "@/lib/template-twin/audit-outbox";

const SERVICE_ROLE = "template-twin-audit-dispatcher";
const DEFAULT_INTERVAL_MS = 5_000;
const HEARTBEAT_PATH = "/tmp/template-twin-audit-dispatcher-heartbeat";

async function writeHeartbeat(): Promise<void> {
  await writeFile(HEARTBEAT_PATH, new Date().toISOString(), {
    encoding: "utf8",
    mode: 0o600,
  });
}

function intervalMs(): number {
  const raw = process.env.TEMPLATE_TWIN_AUDIT_DISPATCH_INTERVAL_MS?.trim();
  if (!raw) return DEFAULT_INTERVAL_MS;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < 1_000 || parsed > 60_000) {
    throw new Error("Template Twin audit dispatcher interval is invalid.");
  }
  return parsed;
}

async function main(): Promise<void> {
  if (process.env.QUILLMD_SERVICE_ROLE !== SERVICE_ROLE) {
    throw new Error("Template Twin audit dispatcher service role is required.");
  }
  assertQuillmdRuntimeProtocol(process.env);
  if (
    process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE !==
    QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE
  ) {
    throw new Error("Exact production database-principal profile is required.");
  }
  await assertPostgresHostAuthenticationContract({ prisma });
  await assertExactDatabasePrincipal({
    prisma,
    loginRole: "meddoc_audit_dispatcher",
    boundaryRole: "quillmd_audit_dispatcher",
  });
  const delay = intervalMs();
  let stopping = false;
  const stop = () => {
    stopping = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  while (!stopping) {
    try {
      const result = await drainTemplateTwinAuditOutbox({
        prisma,
        limit: 100,
      });
      // This is deliberately after the full drain. Both an empty successful
      // census and a completed non-empty delivery pass prove database-backed
      // progress; a failed or wedged drain must let the heartbeat go stale.
      await writeHeartbeat();
      if (result.delivered > 0 || result.failed > 0) {
        process.stdout.write(
          `${JSON.stringify({
            service: SERVICE_ROLE,
            delivered: result.delivered,
            failed: result.failed,
            contended: result.contended,
          })}\n`,
        );
      }
    } catch {
      process.stderr.write(
        `${JSON.stringify({
          service: SERVICE_ROLE,
          code: "TEMPLATE_TWIN_AUDIT_DISPATCH_FAILED",
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
      code: "TEMPLATE_TWIN_AUDIT_DISPATCH_STARTUP_FAILED",
    })}\n`,
  );
  process.exitCode = 1;
});
