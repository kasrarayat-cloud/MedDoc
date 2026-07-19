import prisma from "@meddoc/db";

import { drainTemplateTwinAuditOutbox } from "@/lib/template-twin/audit-outbox";

const SERVICE_ROLE = "template-twin-audit-dispatcher";
const DEFAULT_INTERVAL_MS = 5_000;

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
