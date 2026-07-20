#!/usr/bin/env tsx

// Actual-PostgreSQL contention proof for the MFA credential backfill lock
// order. Synthetic identifiers only; the target must be disposable.

import assert from "node:assert/strict";

import { Pool, type PoolClient } from "pg";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.MFA_SECRET_BACKFILL_LOCK_ORDER_TEST_DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable MFA backfill lock-order test URL is required.");
}
if (
  process.env.DATABASE_URL !== undefined &&
  process.env.DATABASE_URL !== databaseUrl
) {
  throw new Error("MFA backfill lock-order test database mismatch.");
}
assertNonProdDatabase(databaseUrl);

const practiceId = "synthetic-mfa-backfill-lock-practice";
const userId = "synthetic-mfa-backfill-lock-doctor";

async function acquireOrderedCredentialLocks(client: PoolClient) {
  await client.query("SELECT pg_advisory_xact_lock(73119, 20260719)");
  await client.query(
    'SELECT "id" FROM "practices" WHERE "id" = $1 FOR UPDATE',
    [practiceId],
  );
  await client.query('SELECT "id" FROM "users" WHERE "id" = $1 FOR UPDATE', [
    userId,
  ]);
}

async function waitForAdvisoryWaiter(
  observer: PoolClient,
  processId: number,
): Promise<void> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const result = await observer.query<{ waiting: boolean }>(
      `SELECT EXISTS (
         SELECT 1
         FROM pg_locks
         WHERE pid = $1
           AND locktype = 'advisory'
           AND granted = false
       ) AS waiting`,
      [processId],
    );
    if (result.rows[0]?.waiting) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(
    "Ordered MFA backfill contender did not reach advisory wait.",
  );
}

async function main(): Promise<void> {
  process.env.DATABASE_URL = databaseUrl;
  const { default: prisma } = await import("../src");
  const pool = new Pool({ connectionString: databaseUrl, max: 3 });

  async function cleanup() {
    await prisma.userSession.deleteMany({ where: { userId } });
    await prisma.auditLog.deleteMany({ where: { userId } });
    await prisma.user.deleteMany({ where: { id: userId } });
    await prisma.practice.deleteMany({ where: { id: practiceId } });
  }

  try {
    await cleanup();
    await prisma.practice.create({
      data: {
        id: practiceId,
        name: "Synthetic MFA Backfill Lock Practice",
        slug: "synthetic-mfa-backfill-lock-practice",
        isActive: true,
      },
    });
    await prisma.user.create({
      data: {
        id: userId,
        email: "synthetic-mfa-backfill-lock@example.test",
        name: "Synthetic MFA Backfill Lock Doctor",
        passwordHash: "synthetic-not-a-password",
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
        practiceId,
        mfaEnabled: true,
        mfaSecret: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        mfaVerifiedAt: new Date(Date.now() - 60_000),
        mfaBackupCodes: ["synthetic-legacy-verifier"],
      },
    });

    const live = await pool.connect();
    const backfill = await pool.connect();
    const observer = await pool.connect();
    let backfillAcquired = false;
    try {
      await live.query("BEGIN");
      await live.query("SET LOCAL lock_timeout = '2s'");
      await live.query("SET LOCAL statement_timeout = '10s'");
      await acquireOrderedCredentialLocks(live);

      const competingBackfill = (async () => {
        await backfill.query("BEGIN");
        await backfill.query("SET LOCAL lock_timeout = '2s'");
        await backfill.query("SET LOCAL statement_timeout = '10s'");
        try {
          await acquireOrderedCredentialLocks(backfill);
          backfillAcquired = true;
          await backfill.query(
            `UPDATE "users"
             SET "mfaSecret" = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ',
                 "mfaBackupCodes" = ARRAY[]::text[]
             WHERE "id" = $1`,
            [userId],
          );
          await backfill.query("COMMIT");
        } catch (error) {
          await backfill.query("ROLLBACK").catch(() => undefined);
          throw error;
        }
      })();

      await waitForAdvisoryWaiter(observer, backfill.processID);
      assert.equal(
        backfillAcquired,
        false,
        "contender must wait before taking practice or user locks",
      );
      await live.query("COMMIT");
      await competingBackfill;
      assert.equal(backfillAcquired, true);
    } finally {
      await live.query("ROLLBACK").catch(() => undefined);
      await backfill.query("ROLLBACK").catch(() => undefined);
      live.release();
      backfill.release();
      observer.release();
    }

    const user = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: { mfaSecret: true, mfaBackupCodes: true },
    });
    assert.equal(user.mfaSecret, "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ");
    assert.deepEqual(user.mfaBackupCodes, []);
    process.stdout.write(
      `${JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        lockOrder: ["advisory", "practice", "user"],
        advisoryContentionObserved: true,
        deadlock: false,
      })}\n`,
    );
  } finally {
    try {
      await cleanup();
    } finally {
      await Promise.all([pool.end(), prisma.$disconnect()]);
    }
  }
}

main().catch((error) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : "MFA backfill lock-order PostgreSQL proof failed."}\n`,
  );
  process.exitCode = 1;
});
