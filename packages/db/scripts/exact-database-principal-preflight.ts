#!/usr/bin/env tsx

// Read-only production preflight for a trusted application login. Output is
// deliberately fixed: connection strings, catalog identities, and drift
// details must never enter deployment logs.

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import { buildDatabaseConnectionString } from "../src/database-connection-string";
import { assertExactDatabasePrincipal } from "../src/exact-database-principal";

export const EXACT_DATABASE_PRINCIPAL_PROFILES = {
  runtime: {
    loginRole: "meddoc_runtime",
    boundaryRole: "quillmd_runtime",
  },
  "release-control": {
    loginRole: "meddoc_release_control",
    boundaryRole: "quillmd_release_control",
  },
  "release-security": {
    loginRole: "meddoc_release_security",
    boundaryRole: "quillmd_release_security",
  },
  "audit-dispatcher": {
    loginRole: "meddoc_audit_dispatcher",
    boundaryRole: "quillmd_audit_dispatcher",
  },
  "auth-email-dispatcher": {
    loginRole: "meddoc_auth_email_dispatcher",
    boundaryRole: "quillmd_auth_email_dispatcher",
  },
} as const;

export function exactDatabasePrincipalProfile(profile: string | undefined): {
  loginRole: string;
  boundaryRole: string;
} {
  const selected =
    EXACT_DATABASE_PRINCIPAL_PROFILES[
      profile as keyof typeof EXACT_DATABASE_PRINCIPAL_PROFILES
    ];
  if (!selected) {
    throw new Error("EXACT_DATABASE_PRINCIPAL_PROFILE_INVALID");
  }
  return selected;
}

export function buildExactDatabasePrincipalPreflightConnectionString(
  databaseUrl: string,
): string {
  // This intentionally is the same builder and default timeout used by the
  // production runtime. It rejects whitespace, duplicate query keys, target
  // overrides, and unreviewed startup GUCs before the driver can normalize
  // them. The catalog proof then verifies the resulting live session.
  return buildDatabaseConnectionString(databaseUrl);
}

async function run(): Promise<void> {
  let prisma: PrismaClient | null = null;
  try {
    const databaseUrl = process.env.EXACT_DATABASE_PRINCIPAL_DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("EXACT_DATABASE_PRINCIPAL_DATABASE_URL_REQUIRED");
    }
    const profile = exactDatabasePrincipalProfile(
      process.env.EXACT_DATABASE_PRINCIPAL_PROFILE,
    );
    prisma = new PrismaClient({
      adapter: new PrismaPg({
        connectionString:
          buildExactDatabasePrincipalPreflightConnectionString(databaseUrl),
        connectionTimeoutMillis: 10_000,
      }),
    });
    await assertExactDatabasePrincipal({ prisma, ...profile });
    process.stdout.write("EXACT_DATABASE_PRINCIPAL_PREFLIGHT_PASS\n");
  } catch {
    process.stderr.write("EXACT_DATABASE_PRINCIPAL_PREFLIGHT_FAIL\n");
    process.exitCode = 1;
  } finally {
    if (prisma) {
      try {
        await prisma.$disconnect();
      } catch {
        process.stderr.write("EXACT_DATABASE_PRINCIPAL_PREFLIGHT_FAIL\n");
        process.exitCode = 1;
      }
    }
  }
}

if (process.env.VITEST !== "true") {
  void run().catch(() => {
    process.stderr.write("EXACT_DATABASE_PRINCIPAL_PREFLIGHT_FAIL\n");
    process.exitCode = 1;
  });
}
