#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the single-current-session invariant.
// Synthetic identifiers only; the target must be a disposable database.

import assert from "node:assert/strict";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.USER_SESSION_CONCURRENCY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable user-session test URL is required.");
}
assertNonProdDatabase(databaseUrl);

const practiceId = "synthetic-session-concurrency-practice";
const userId = "synthetic-session-concurrency-doctor";
const email = "synthetic-session-concurrency@example.test";
const recoveryHash = "synthetic-recovery-hash-never-a-real-credential";

async function main(): Promise<void> {
  // The test-specific, positively guarded URL is authoritative. Load both the
  // singleton database client and the session helpers only after aligning the
  // environment so an inherited DATABASE_URL cannot redirect test mutations.
  process.env.DATABASE_URL = databaseUrl;
  const [
    { default: prisma },
    {
      recordSessionLogin,
      revokeAllUserSessionsFromCurrentSession,
      validateSession,
    },
  ] = await Promise.all([
    import("../src"),
    import("../../auth/src/user-session"),
  ]);

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
        name: "Synthetic Session Concurrency Practice",
        slug: "synthetic-session-concurrency-practice",
        isActive: true,
      },
    });
    await prisma.user.create({
      data: {
        id: userId,
        email,
        name: "Synthetic Session Concurrency Doctor",
        passwordHash: "synthetic-not-a-credential",
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
        mfaBackupCodes: [recoveryHash],
        practiceId,
      },
    });

    const tokens = Array.from(
      { length: 16 },
      (_, index) =>
        `synthetic-session-token-${index.toString().padStart(2, "0")}`,
    );
    await Promise.all(
      tokens.map((sessionToken) =>
        recordSessionLogin({ userId, sessionToken, ttlMs: 60_000 }),
      ),
    );

    const rows = await prisma.userSession.findMany({ where: { userId } });
    assert.equal(
      rows.length,
      1,
      "concurrent logins must leave exactly one current session row",
    );
    const winner = rows[0];
    assert.ok(winner && tokens.includes(winner.sessionToken));

    const validationResults = await Promise.all(
      tokens.map((sessionToken) =>
        validateSession({
          sessionToken,
          expectedUserId: userId,
          expectedPracticeId: practiceId,
          allowedRoles: ["DOCTOR"],
          requiredProducts: ["TRANSCRIBE_MD"],
        }),
      ),
    );
    assert.equal(
      validationResults.filter(Boolean).length,
      1,
      "only the final serialized login token may validate",
    );

    const staleToken = tokens.find(
      (sessionToken) => sessionToken !== winner.sessionToken,
    );
    assert.ok(staleToken);
    assert.equal(
      await revokeAllUserSessionsFromCurrentSession({
        sessionToken: staleToken,
        userId,
      }),
      false,
      "a signed-but-revoked token must not revoke the newer session",
    );
    assert.equal(
      await prisma.userSession.count({ where: { userId } }),
      1,
      "the newer session must survive stale all-device revocation",
    );
    assert.equal(
      await revokeAllUserSessionsFromCurrentSession({
        sessionToken: winner.sessionToken,
        userId,
      }),
      true,
      "the exact current session may revoke all sessions",
    );
    assert.equal(await prisma.userSession.count({ where: { userId } }), 0);

    // This is the same conditional row mutation used by the credentials
    // provider after it matches a recovery-code hash. Concurrent requests may
    // all begin with a stale read, but PostgreSQL rechecks the WHERE predicate
    // after taking the row lock, so exactly one request can consume the hash.
    const recoveryConsumers = 16;
    const consumeCounts = await Promise.all(
      Array.from(
        { length: recoveryConsumers },
        () =>
          prisma.$executeRaw`
        UPDATE "users"
        SET "mfaBackupCodes" = array_remove("mfaBackupCodes", ${recoveryHash})
        WHERE "id" = ${userId}
          AND ${recoveryHash} = ANY("mfaBackupCodes")
      `,
      ),
    );
    assert.equal(
      consumeCounts.filter((count) => count === 1).length,
      1,
      "exactly one concurrent recovery-code consume may update the user row",
    );
    assert.equal(
      consumeCounts.filter((count) => count === 0).length,
      recoveryConsumers - 1,
      "every competing recovery-code consume must fail closed",
    );
    const recoveryState = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: { mfaBackupCodes: true },
    });
    assert.deepEqual(
      recoveryState.mfaBackupCodes,
      [],
      "the one-time recovery hash must be absent after the winning consume",
    );

    process.stdout.write(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        concurrentLogins: tokens.length,
        remainingSessions: rows.length,
        validSessions: validationResults.filter(Boolean).length,
        staleAllDeviceRevocationDenied: true,
        exactAllDeviceRevocationAccepted: true,
        concurrentRecoveryConsumers: recoveryConsumers,
        successfulRecoveryConsumes: consumeCounts.filter((count) => count === 1)
          .length,
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
    `${error instanceof Error ? error.message : "User-session concurrency proof failed."}\n`,
  );
  process.exitCode = 1;
});
