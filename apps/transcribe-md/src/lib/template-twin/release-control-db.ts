import "server-only";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

const globalForReleaseControl = globalThis as unknown as {
  templateTwinReleaseControlPrisma?: PrismaClient;
};

export const TEMPLATE_TWIN_RELEASE_CONTROL_SERVICE_ROLE =
  "template-twin-admin-control" as const;

export function templateTwinReleaseControlProcessEnabled(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  return (
    env.NODE_ENV !== "production" ||
    env.QUILLMD_SERVICE_ROLE?.trim() ===
      TEMPLATE_TWIN_RELEASE_CONTROL_SERVICE_ROLE
  );
}

function releaseControlConnectionString(): string {
  const dedicated = process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL;
  if (dedicated && templateTwinReleaseControlProcessEnabled()) return dedicated;

  // Disposable/in-process verification may reuse its isolated database. A
  // production process must never silently promote its ordinary runtime DSN
  // into the privileged release-control connection.
  if (process.env.NODE_ENV !== "production") {
    const disposable =
      process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL ??
      process.env.DATABASE_URL;
    if (disposable) return disposable;
  }

  return "postgresql://release-control-unconfigured@127.0.0.1:1/unavailable";
}

function buildReleaseControlPrisma(): PrismaClient {
  const adapter = new PrismaPg({
    connectionString: releaseControlConnectionString(),
    max: Number(process.env.TEMPLATE_TWIN_RELEASE_CONTROL_POOL_MAX ?? 3),
    connectionTimeoutMillis: Number(
      process.env.TEMPLATE_TWIN_RELEASE_CONTROL_POOL_TIMEOUT_MS ?? 5_000,
    ),
  });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });
}

const releaseControlDatabase =
  globalForReleaseControl.templateTwinReleaseControlPrisma ??
  buildReleaseControlPrisma();

if (process.env.NODE_ENV !== "production") {
  globalForReleaseControl.templateTwinReleaseControlPrisma =
    releaseControlDatabase;
}

export default releaseControlDatabase;
