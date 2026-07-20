#!/usr/bin/env tsx

// Actual-PostgreSQL proof for transaction-final credential authority.
// Synthetic identifiers only; the target must be a disposable database.

import assert from "node:assert/strict";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.CREDENTIAL_SESSION_AUTHORITY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable credential-session test URL is required.");
}
assertNonProdDatabase(databaseUrl);

const practiceId = "synthetic-credential-authority-practice";
const userId = "synthetic-credential-authority-doctor";
const email = "synthetic-credential-authority-doctor@example.test";
const recoveryHash = "synthetic-one-time-recovery-hash";

async function main(): Promise<void> {
  process.env.DATABASE_URL = databaseUrl;
  const [dbModule, authorityModule] = await Promise.all([
    import("../src"),
    import("../../../apps/transcribe-md/src/lib/credential-session-authority"),
  ]);
  const prisma = dbModule.default;
  const {
    CredentialSessionAuthorityError,
    finalizeCredentialSession,
    recordCredentialFailure,
  } = authorityModule;

  async function cleanup(): Promise<void> {
    await prisma.userSession.deleteMany({ where: { userId } });
    await prisma.user.deleteMany({ where: { id: userId } });
    await prisma.practice.deleteMany({ where: { id: practiceId } });
  }

  try {
    await cleanup();
    await prisma.practice.create({
      data: {
        id: practiceId,
        name: "Synthetic Credential Authority Practice",
        slug: "synthetic-credential-authority-practice",
        isActive: true,
      },
    });
    const user = await prisma.user.create({
      data: {
        id: userId,
        email,
        name: "Synthetic Credential Authority Doctor",
        passwordHash: "synthetic-password-snapshot-v1",
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
        practiceId,
        emailVerified: new Date(Date.now() - 60_000),
        mfaEnabled: true,
        mfaSecret: "synthetic-mfa-secret",
        mfaVerifiedAt: new Date(Date.now() - 60_000),
        mfaBackupCodes: [recoveryHash],
      },
    });
    const snapshot = {
      id: user.id,
      email: user.email,
      name: user.name,
      practiceId: user.practiceId,
      passwordHash: user.passwordHash,
      role: user.role,
      products: user.products,
      emailVerified: user.emailVerified,
      mfaEnabled: user.mfaEnabled,
      mfaSecret: user.mfaSecret,
      mfaVerifiedAt: user.mfaVerifiedAt,
      mfaBackupCodes: user.mfaBackupCodes,
    };

    const sessionAttempts = 12;
    const recoveryResults = await Promise.allSettled(
      Array.from({ length: sessionAttempts }, (_, index) =>
        prisma.$transaction((tx) =>
          finalizeCredentialSession(tx, {
            snapshot,
            surface: "physician",
            secondFactor: { kind: "recovery", matchedHash: recoveryHash },
            requireVerifiedEmail: true,
            sessionToken: `synthetic-credential-session-${index}`,
            ttlMs: 60_000,
          }),
        ),
      ),
    );
    const sessionWinners = recoveryResults.filter(
      (result) => result.status === "fulfilled",
    );
    assert.equal(
      sessionWinners.length,
      1,
      "one recovery code must authorize exactly one concurrent session",
    );
    for (const result of recoveryResults) {
      if (result.status === "rejected") {
        assert.ok(
          result.reason instanceof CredentialSessionAuthorityError,
          "losing recovery-code requests must fail final authority",
        );
      }
    }
    const sessions = await prisma.userSession.findMany({
      where: { userId },
      select: { sessionToken: true },
    });
    assert.equal(sessions.length, 1);
    const afterRecovery = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: { mfaBackupCodes: true },
    });
    assert.deepEqual(afterRecovery.mfaBackupCodes, []);

    await prisma.userSession.deleteMany({ where: { userId } });
    await prisma.user.update({
      where: { id: userId },
      data: {
        mfaEnabled: false,
        mfaSecret: null,
        mfaVerifiedAt: null,
        mfaBackupCodes: [],
        failedLoginCount: 0,
        lockedUntil: null,
      },
    });
    const noMfaUser = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });
    const failureSnapshot = {
      id: noMfaUser.id,
      email: noMfaUser.email,
      name: noMfaUser.name,
      practiceId: noMfaUser.practiceId,
      passwordHash: noMfaUser.passwordHash,
      role: noMfaUser.role,
      products: noMfaUser.products,
      emailVerified: noMfaUser.emailVerified,
      mfaEnabled: noMfaUser.mfaEnabled,
      mfaSecret: noMfaUser.mfaSecret,
      mfaVerifiedAt: noMfaUser.mfaVerifiedAt,
      mfaBackupCodes: noMfaUser.mfaBackupCodes,
    };
    const failures = await Promise.all(
      Array.from({ length: 5 }, () =>
        prisma.$transaction((tx) =>
          recordCredentialFailure(tx, {
            snapshot: failureSnapshot,
            surface: "physician",
          }),
        ),
      ),
    );
    assert.deepEqual(
      failures.map((result) => result.failedLoginCount).sort((a, b) => a - b),
      [1, 2, 3, 4, 5],
      "concurrent failures must serialize without lost increments",
    );
    assert.equal(failures.filter((result) => result.locked).length, 1);
    const postThreshold = await prisma.$transaction((tx) =>
      recordCredentialFailure(tx, {
        snapshot: failureSnapshot,
        surface: "physician",
      }),
    );
    assert.equal(postThreshold.recorded, false);
    assert.equal(postThreshold.locked, true);

    await prisma.user.update({
      where: { id: userId },
      data: {
        failedLoginCount: 0,
        lockedUntil: null,
        passwordHash: "synthetic-password-snapshot-v2",
      },
    });
    const beforeStaleSessions = await prisma.userSession.count({
      where: { userId },
    });
    await assert.rejects(
      prisma.$transaction((tx) =>
        finalizeCredentialSession(tx, {
          snapshot: failureSnapshot,
          surface: "physician",
          secondFactor: { kind: "none" },
          requireVerifiedEmail: true,
          sessionToken: "synthetic-stale-credential-session",
          ttlMs: 60_000,
        }),
      ),
      CredentialSessionAuthorityError,
      "a stale password snapshot must not mint a session",
    );
    assert.equal(
      await prisma.userSession.count({ where: { userId } }),
      beforeStaleSessions,
    );

    process.stdout.write(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        concurrentRecoveryAttempts: sessionAttempts,
        successfulRecoverySessions: sessionWinners.length,
        remainingSessions: sessions.length,
        remainingRecoveryCodes: afterRecovery.mfaBackupCodes.length,
        concurrentFailureAttempts: failures.length,
        finalFailureCount: Math.max(
          ...failures.map((result) => result.failedLoginCount),
        ),
        lockoutReached: postThreshold.locked,
        staleCredentialSessionCreated: false,
      }) + "\n",
    );
  } finally {
    try {
      await cleanup();
    } finally {
      await prisma.$disconnect();
    }
  }
}

main().catch((error) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : "Credential-session PostgreSQL proof failed."}\n`,
  );
  process.exitCode = 1;
});
