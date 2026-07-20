#!/usr/bin/env tsx

/**
 * Dry-run-by-default MFA secret/recovery-verifier migration utility.
 *
 * It never prints user identifiers, secrets, ciphertext, key IDs, file paths,
 * or database diagnostics. Apply mode requires a reviewed exact candidate
 * census and an explicit attestation. Each row is re-read under a bounded
 * lock, compared with its dry-run snapshot, and updated only if unchanged.
 */

import type { Prisma } from "@prisma/client";

import {
  assertMfaSecretRuntimeConfiguration,
  decryptMfaSecretForUser,
  encryptMfaSecretForUser,
  isLegacyPlaintextMfaSecret,
  isMfaSecretEnvelope,
} from "../src/lib/mfa-secret-envelope";
import { isCurrentRecoveryCodeVerifier } from "../src/lib/mfa";
import {
  buildMfaSecretBackfillCandidateManifest,
  type MfaSecretBackfillManifestEntry,
} from "../src/lib/mfa-secret-backfill-manifest";
import { isIncompleteEnabledMfaEnrollment } from "../src/lib/mfa-secret-migration-state";

const APPLY_ATTESTATION = "accepted-reviewed-mfa-secret-backfill-v1";
const DEFAULT_BATCH_SIZE = 25;
const MAX_BATCH_SIZE = 50;
const DATABASE_CONFIGURATION_ERROR =
  "MFA secret backfill database configuration rejected.";
const KEYRING_CONFIGURATION_ERROR =
  "MFA secret backfill keyring configuration rejected.";

interface UserMfaSnapshot {
  id: string;
  practiceId: string;
  mfaEnabled: boolean;
  mfaSecret: string | null;
  mfaBackupCodes: string[];
  mfaVerifiedAt: Date | null;
  mfaVerifiedAtCanonical: string | null;
}

interface LockedUserMfaSnapshot extends UserMfaSnapshot {
  email: string;
}

interface CandidateUpdateResult {
  outcome: "updated" | "changed" | "skipped";
  sessionsRevoked: number;
}

interface Census {
  snapshots: UserMfaSnapshot[];
  usersScanned: number;
  encryptedSecrets: number;
  legacyPlaintextSecrets: number;
  invalidStoredSecrets: number;
  incompleteEnabledEnrollments: number;
  legacyRecoveryVerifierUsers: number;
  legacyRecoveryVerifiers: number;
  candidates: number;
  candidateManifestSha256: string;
}

function boundedInteger(
  value: string | undefined,
  fallback: number,
  maximum: number,
): number {
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > maximum) {
    throw new Error("MFA secret backfill configuration rejected.");
  }
  return parsed;
}

function requiredNonnegativeInteger(
  value: string | undefined,
  maximum: number,
): number {
  if (value === undefined || !/^\d+$/u.test(value)) {
    throw new Error("MFA secret backfill configuration rejected.");
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > maximum) {
    throw new Error("MFA secret backfill configuration rejected.");
  }
  return parsed;
}

function requiredSha256(value: string | undefined): string {
  if (!value || !/^[0-9a-f]{64}$/u.test(value)) {
    throw new Error("MFA secret backfill configuration rejected.");
  }
  return value;
}

function configureDedicatedDatabaseTarget(): void {
  const dedicated = process.env.MFA_SECRET_BACKFILL_DATABASE_URL;
  const ambient = process.env.DATABASE_URL;
  if (!dedicated || dedicated.trim() !== dedicated) {
    throw new Error(DATABASE_CONFIGURATION_ERROR);
  }
  if (ambient !== undefined && ambient !== dedicated) {
    throw new Error(DATABASE_CONFIGURATION_ERROR);
  }
  try {
    const parsed = new URL(dedicated);
    if (
      !["postgres:", "postgresql:"].includes(parsed.protocol) ||
      parsed.pathname.replace(/^\//u, "").length === 0
    ) {
      throw new Error(DATABASE_CONFIGURATION_ERROR);
    }
  } catch {
    throw new Error(DATABASE_CONFIGURATION_ERROR);
  }

  // @meddoc/db constructs its pool at module evaluation. Assign the reviewed,
  // dedicated target before the first dynamic import so an unrelated ambient
  // DATABASE_URL can never select the backfill database implicitly.
  process.env.DATABASE_URL = dedicated;
}

function requireExternalBackfillKeyring(): void {
  const activeKeyId = process.env.MFA_SECRET_ACTIVE_KEY_ID;
  const keyringFile = process.env.MFA_SECRET_KEYRING_FILE;
  if (!activeKeyId || !keyringFile) {
    throw new Error(KEYRING_CONFIGURATION_ERROR);
  }

  // Force the CLI onto the production consumer contract even in a developer
  // shell where NODE_ENV is absent. This both validates root:1001/0440 and
  // makes runtime encryption unable to reach the non-production ephemeral-key
  // fallback. No database module has been imported at this point.
  const runtimeEnvironment = process.env as unknown as Record<
    string,
    string | undefined
  >;
  runtimeEnvironment.NODE_ENV = "production";
  runtimeEnvironment.QUILLMD_SERVICE_ROLE = "physician-app";
  try {
    assertMfaSecretRuntimeConfiguration(runtimeEnvironment);
  } catch {
    throw new Error(KEYRING_CONFIGURATION_ERROR);
  }
}

function sameStrings(left: readonly string[], right: readonly string[]) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

function legacyRecoveryVerifiers(values: readonly string[]) {
  return values.filter((value) => !isCurrentRecoveryCodeVerifier(value));
}

function secretState(
  snapshot: UserMfaSnapshot,
): "none" | "encrypted" | "legacy" | "invalid" {
  if (snapshot.mfaSecret === null) return "none";
  if (isLegacyPlaintextMfaSecret(snapshot.mfaSecret)) return "legacy";
  if (!isMfaSecretEnvelope(snapshot.mfaSecret)) return "invalid";
  try {
    void decryptMfaSecretForUser({
      userId: snapshot.id,
      encryptedSecret: snapshot.mfaSecret,
    });
    return "encrypted";
  } catch {
    return "invalid";
  }
}

function verifiedTimestamp(snapshot: UserMfaSnapshot): string {
  if (
    snapshot.mfaVerifiedAt === null &&
    snapshot.mfaVerifiedAtCanonical === null
  ) {
    return "null";
  }
  if (
    snapshot.mfaVerifiedAt === null ||
    snapshot.mfaVerifiedAtCanonical === null ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/u.test(
      snapshot.mfaVerifiedAtCanonical,
    )
  ) {
    return "invalid";
  }
  return snapshot.mfaVerifiedAtCanonical;
}

async function census(
  prisma: typeof import("@meddoc/db").default,
  batchSize: number,
): Promise<Census> {
  const censusAt = new Date();
  const snapshots: UserMfaSnapshot[] = [];
  let cursor: string | undefined;
  while (true) {
    const rows = cursor
      ? await prisma.$queryRaw<UserMfaSnapshot[]>`
          SELECT "id", "practiceId", "mfaEnabled", "mfaSecret",
            "mfaBackupCodes", "mfaVerifiedAt",
            to_char(
              "mfaVerifiedAt" AT TIME ZONE 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            ) AS "mfaVerifiedAtCanonical"
          FROM "users"
          WHERE (
            "mfaSecret" IS NOT NULL
            OR cardinality("mfaBackupCodes") > 0
            OR "mfaEnabled" = TRUE
          )
            AND "id" > ${cursor}
          ORDER BY "id" ASC
          LIMIT ${batchSize}
        `
      : await prisma.$queryRaw<UserMfaSnapshot[]>`
          SELECT "id", "practiceId", "mfaEnabled", "mfaSecret",
            "mfaBackupCodes", "mfaVerifiedAt",
            to_char(
              "mfaVerifiedAt" AT TIME ZONE 'UTC',
              'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            ) AS "mfaVerifiedAtCanonical"
          FROM "users"
          WHERE "mfaSecret" IS NOT NULL
            OR cardinality("mfaBackupCodes") > 0
            OR "mfaEnabled" = TRUE
          ORDER BY "id" ASC
          LIMIT ${batchSize}
        `;
    if (rows.length === 0) break;
    snapshots.push(...rows);
    cursor = rows.at(-1)?.id;
    if (rows.length < batchSize) break;
  }

  let encryptedSecrets = 0;
  let legacyPlaintextSecrets = 0;
  let invalidStoredSecrets = 0;
  let incompleteEnabledEnrollments = 0;
  let legacyRecoveryVerifierUsers = 0;
  let legacyRecoveryVerifierCount = 0;
  let candidates = 0;
  const manifestEntries: MfaSecretBackfillManifestEntry[] = [];
  for (const snapshot of snapshots) {
    const state = secretState(snapshot);
    if (state === "encrypted") encryptedSecrets += 1;
    if (state === "legacy") legacyPlaintextSecrets += 1;
    if (state === "invalid") invalidStoredSecrets += 1;
    if (
      isIncompleteEnabledMfaEnrollment(
        {
          mfaEnabled: snapshot.mfaEnabled,
          mfaVerifiedAt: snapshot.mfaVerifiedAt,
          hasAuthenticStoredSecret: state === "encrypted" || state === "legacy",
        },
        censusAt,
      )
    ) {
      incompleteEnabledEnrollments += 1;
    }
    const legacyRecovery = legacyRecoveryVerifiers(snapshot.mfaBackupCodes);
    if (legacyRecovery.length > 0) {
      legacyRecoveryVerifierUsers += 1;
      legacyRecoveryVerifierCount += legacyRecovery.length;
    }
    if (state === "legacy" || legacyRecovery.length > 0) {
      candidates += 1;
      manifestEntries.push({
        id: snapshot.id,
        practiceId: snapshot.practiceId,
        mfaEnabled: snapshot.mfaEnabled,
        verifiedTimestamp: verifiedTimestamp(snapshot),
        secretState: state,
        totalRecoveryVerifierCount: snapshot.mfaBackupCodes.length,
        currentRecoveryVerifierCount:
          snapshot.mfaBackupCodes.length - legacyRecovery.length,
        legacyRecoveryVerifierCount: legacyRecovery.length,
      });
    }
  }
  return {
    snapshots,
    usersScanned: snapshots.length,
    encryptedSecrets,
    legacyPlaintextSecrets,
    invalidStoredSecrets,
    incompleteEnabledEnrollments,
    legacyRecoveryVerifierUsers,
    legacyRecoveryVerifiers: legacyRecoveryVerifierCount,
    candidates,
    candidateManifestSha256:
      buildMfaSecretBackfillCandidateManifest(manifestEntries),
  };
}

async function updateCandidate(
  prisma: typeof import("@meddoc/db").default,
  snapshot: UserMfaSnapshot,
): Promise<CandidateUpdateResult> {
  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      await tx.$executeRaw`SET LOCAL lock_timeout = '2s'`;
      await tx.$executeRaw`SET LOCAL statement_timeout = '10s'`;
      // Match every live account/Template Twin mutation: global lifecycle
      // advisory lock -> practice -> user. The user UPDATE trigger acquires
      // the same advisory lock, so taking it after FOR UPDATE would invert the
      // order and permit a deadlock under production contention.
      await tx.$queryRaw`
        SELECT pg_advisory_xact_lock(73119, 20260719)::text AS "lockAcquired"
      `;
      const practices = await tx.$queryRaw<Array<{ id: string }>>`
        SELECT "id"
        FROM "practices"
        WHERE "id" = ${snapshot.practiceId}
        FOR UPDATE
      `;
      if (practices.length !== 1 || practices[0]?.id !== snapshot.practiceId) {
        return { outcome: "changed", sessionsRevoked: 0 };
      }
      const rows = await tx.$queryRaw<LockedUserMfaSnapshot[]>`
        SELECT "id", "email", "practiceId", "mfaEnabled", "mfaSecret",
          "mfaBackupCodes", "mfaVerifiedAt",
          to_char(
            "mfaVerifiedAt" AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
          ) AS "mfaVerifiedAtCanonical"
        FROM "users"
        WHERE "id" = ${snapshot.id}
        FOR UPDATE
      `;
      const current = rows[0];
      if (
        rows.length !== 1 ||
        !current ||
        current.practiceId !== snapshot.practiceId ||
        current.mfaEnabled !== snapshot.mfaEnabled ||
        current.mfaSecret !== snapshot.mfaSecret ||
        current.mfaVerifiedAtCanonical !== snapshot.mfaVerifiedAtCanonical ||
        !sameStrings(current.mfaBackupCodes, snapshot.mfaBackupCodes)
      ) {
        return { outcome: "changed", sessionsRevoked: 0 };
      }

      const state = secretState(current);
      const currentRecoveryCodes = current.mfaBackupCodes.filter(
        isCurrentRecoveryCodeVerifier,
      );
      if (
        state !== "legacy" &&
        sameStrings(currentRecoveryCodes, current.mfaBackupCodes)
      ) {
        return { outcome: "skipped", sessionsRevoked: 0 };
      }
      if (state === "invalid") {
        return { outcome: "changed", sessionsRevoked: 0 };
      }

      const data: Prisma.UserUpdateManyMutationInput = {};
      if (state === "legacy" && current.mfaSecret !== null) {
        data.mfaSecret = encryptMfaSecretForUser({
          userId: current.id,
          plaintextSecret: current.mfaSecret,
        });
      }
      if (!sameStrings(currentRecoveryCodes, current.mfaBackupCodes)) {
        data.mfaBackupCodes = currentRecoveryCodes;
      }
      // The exact row was compared while held FOR UPDATE. Keep the write on
      // that locked identity; rebinding TIMESTAMPTZ(6) through a JavaScript
      // Date would truncate microseconds and reject an otherwise unchanged row.
      const updated = await tx.user.updateMany({
        where: {
          id: current.id,
        },
        data,
      });
      if (updated.count !== 1) {
        return { outcome: "changed", sessionsRevoked: 0 };
      }

      // The migration changes authentication credentials. Revoke every
      // database-backed session in the same transaction so no pre-migration
      // JWT can remain authoritative. Only the aggregate count is reported.
      const revoked = await tx.userSession.deleteMany({
        where: { userId: current.id },
      });
      await tx.auditLog.create({
        data: {
          userId: current.id,
          userEmailSnapshot: current.email,
          action: "MFA_CREDENTIALS_MIGRATED",
          targetId: current.id,
          targetType: "User",
          practiceId: current.practiceId,
          success: true,
          metadata: {
            envelopeVersion: "qmfa:v1",
            secretReencrypted: state === "legacy",
            legacyRecoveryVerifiersRetired:
              current.mfaBackupCodes.length - currentRecoveryCodes.length,
            sessionsRevoked: revoked.count,
          },
          timestamp: new Date(),
        },
      });
      return { outcome: "updated", sessionsRevoked: revoked.count };
    },
    { maxWait: 5_000, timeout: 15_000 },
  );
}

function safeReport(
  mode: "DRY_RUN" | "APPLY",
  before: Census,
  changes: {
    updated: number;
    changed: number;
    skipped: number;
    sessionsRevoked: number;
  },
  after?: Census,
) {
  return {
    verdict:
      mode === "DRY_RUN"
        ? before.invalidStoredSecrets === 0
          ? before.incompleteEnabledEnrollments === 0
            ? "REVIEW_REQUIRED"
            : "BLOCKED_INCOMPLETE_ENABLED_ENROLLMENT"
          : "BLOCKED_INVALID_STORED_SECRET"
        : after &&
            after.legacyPlaintextSecrets === 0 &&
            after.invalidStoredSecrets === 0 &&
            after.incompleteEnabledEnrollments === 0 &&
            after.legacyRecoveryVerifiers === 0 &&
            changes.changed === 0
          ? "PASS"
          : "FAIL",
    mode,
    usersScanned: before.usersScanned,
    before: {
      encryptedSecrets: before.encryptedSecrets,
      legacyPlaintextSecrets: before.legacyPlaintextSecrets,
      invalidStoredSecrets: before.invalidStoredSecrets,
      incompleteEnabledEnrollments: before.incompleteEnabledEnrollments,
      legacyRecoveryVerifierUsers: before.legacyRecoveryVerifierUsers,
      legacyRecoveryVerifiers: before.legacyRecoveryVerifiers,
      candidates: before.candidates,
      candidateManifestSha256: before.candidateManifestSha256,
    },
    changes,
    ...(after
      ? {
          after: {
            encryptedSecrets: after.encryptedSecrets,
            legacyPlaintextSecrets: after.legacyPlaintextSecrets,
            invalidStoredSecrets: after.invalidStoredSecrets,
            incompleteEnabledEnrollments: after.incompleteEnabledEnrollments,
            legacyRecoveryVerifierUsers: after.legacyRecoveryVerifierUsers,
            legacyRecoveryVerifiers: after.legacyRecoveryVerifiers,
            candidates: after.candidates,
            candidateManifestSha256: after.candidateManifestSha256,
          },
        }
      : {}),
  };
}

async function main(): Promise<void> {
  requireExternalBackfillKeyring();
  configureDedicatedDatabaseTarget();
  const applyValue = process.env.MFA_SECRET_BACKFILL_APPLY ?? "false";
  if (applyValue !== "false" && applyValue !== "true") {
    throw new Error("MFA secret backfill configuration rejected.");
  }
  const apply = applyValue === "true";
  const batchSize = boundedInteger(
    process.env.MFA_SECRET_BACKFILL_BATCH_SIZE,
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
  );
  const { default: prisma } = await import("@meddoc/db");
  try {
    const before = await census(prisma, batchSize);
    const changes = {
      updated: 0,
      changed: 0,
      skipped: 0,
      sessionsRevoked: 0,
    };
    if (!apply) {
      process.stdout.write(
        `${JSON.stringify(safeReport("DRY_RUN", before, changes))}\n`,
      );
      return;
    }

    const expectedCandidates = requiredNonnegativeInteger(
      process.env.MFA_SECRET_BACKFILL_EXPECTED_CANDIDATES,
      Number.MAX_SAFE_INTEGER,
    );
    const expectedManifestSha256 = requiredSha256(
      process.env.MFA_SECRET_BACKFILL_EXPECTED_MANIFEST_SHA256,
    );
    if (
      process.env.MFA_SECRET_BACKFILL_APPLY_ATTESTATION !== APPLY_ATTESTATION ||
      expectedCandidates !== before.candidates ||
      expectedManifestSha256 !== before.candidateManifestSha256 ||
      before.invalidStoredSecrets !== 0 ||
      before.incompleteEnabledEnrollments !== 0
    ) {
      throw new Error("MFA secret backfill apply gate rejected.");
    }

    for (const snapshot of before.snapshots) {
      const state = secretState(snapshot);
      if (
        state !== "legacy" &&
        legacyRecoveryVerifiers(snapshot.mfaBackupCodes).length === 0
      ) {
        continue;
      }
      const result = await updateCandidate(prisma, snapshot);
      changes[result.outcome] += 1;
      changes.sessionsRevoked += result.sessionsRevoked;
    }

    const after = await census(prisma, batchSize);
    const report = safeReport("APPLY", before, changes, after);
    process.stdout.write(`${JSON.stringify(report)}\n`);
    if (report.verdict !== "PASS") process.exitCode = 1;
  } finally {
    await prisma.$disconnect();
  }
}

main().catch(() => {
  process.stderr.write("MFA secret backfill failed closed.\n");
  process.exitCode = 1;
});
