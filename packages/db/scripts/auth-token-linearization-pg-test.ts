#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the online one-current-token transition and the
// final atomic issuance/redemption boundary. Synthetic identifiers only; the
// target must be a disposable database migrated through v4 (pre-v5).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";

import { Client, Pool } from "pg";

import {
  AUTH_TOKEN_INDEX,
  AUTH_TOKEN_TRANSITION_FUNCTION,
  AUTH_TOKEN_TRANSITION_TRIGGER,
  buildAuthTokenUniqueIndex,
  readAuthTokenLinearizationStatus,
  reconcileAuthTokenDuplicateBatch,
} from "../src/auth-token-linearization-online";
import { acquireAuthTokenOperatorSessionLock } from "../src/auth-token-linearization-session-lock";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.AUTH_TOKEN_LINEARIZATION_TEST_DATABASE_URL?.trim();
if (!databaseUrl) throw new Error("Disposable auth-token test URL is required");
const target = assertNonProdDatabase(databaseUrl);
if (!/^meddoc_auth_token_online_test_[a-z0-9_]+$/u.test(target.database)) {
  throw new Error(
    "Exact disposable auth-token online database name is required",
  );
}

const practiceId = "synthetic-auth-token-online-practice";
const userId = "synthetic-auth-token-online-doctor";
const raceUserId = "synthetic-auth-token-online-race-doctor";
const isolationUserId = "synthetic-auth-token-online-isolation-doctor";
const userIds = [userId, raceUserId, isolationUserId];
const email = "auth-token-online-doctor@synthetic.invalid";
const migrationSql = readFileSync(
  fileURLToPath(
    new URL(
      "../prisma/migrations/20260720150000_auth_token_linearization_v5/migration.sql",
      import.meta.url,
    ),
  ),
  "utf8",
);

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function client(applicationName: string): Client {
  return new Client({
    connectionString: databaseUrl,
    application_name: applicationName,
  });
}

async function insertToken(
  connection: Client,
  input: {
    id: string;
    userId: string;
    purpose: "PASSWORD_RESET" | "EMAIL_VERIFICATION" | "EMAIL_CHANGE";
    used?: boolean;
    ageMinutes?: number;
  },
): Promise<void> {
  await connection.query(
    `INSERT INTO public."auth_tokens" (
       "id", "userId", "purpose", "tokenHash", "expiresAt", "usedAt",
       "createdAt"
     ) VALUES (
       $1, $2, $3::"AuthTokenPurpose", $4,
       CURRENT_TIMESTAMP + INTERVAL '1 hour',
       CASE WHEN $5::boolean THEN CURRENT_TIMESTAMP ELSE NULL END,
       CURRENT_TIMESTAMP - ($6::integer * INTERVAL '1 minute')
     )`,
    [
      input.id,
      input.userId,
      input.purpose,
      `synthetic-hash-${input.id}`,
      input.used ?? false,
      input.ageMinutes ?? 0,
    ],
  );
}

async function expectRejected(
  operation: () => Promise<unknown>,
  expectedCode: string,
  label: string,
): Promise<void> {
  let caught: unknown;
  try {
    await operation();
  } catch (error) {
    caught = error;
  }
  assert(caught, `${label} must reject`);
  if (caught instanceof Error && "code" in caught) {
    assert.equal(
      (caught as Error & { code: string }).code,
      expectedCode,
      label,
    );
  } else {
    assert.equal(
      caught instanceof Error ? caught.message : "",
      expectedCode,
      label,
    );
  }
}

async function waitForAdvisoryWait(observer: Client, applicationName: string) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const result = await observer.query<{
      pid: number;
      waitEvent: string | null;
    }>(
      `SELECT pid, wait_event AS "waitEvent"
       FROM pg_catalog.pg_stat_activity
       WHERE datname = current_database() AND application_name = $1
         AND state = 'active'`,
      [applicationName],
    );
    if (result.rows[0]?.waitEvent?.toLowerCase().includes("advisory")) {
      return result.rows[0].pid;
    }
    await sleep(50);
  }
  throw new Error("AUTH_TOKEN_ADVISORY_WAIT_NOT_OBSERVED");
}

async function waitForConcurrentIndex(
  observer: Client,
  applicationName: string,
) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const result = await observer.query<{ pid: number }>(
      `SELECT pid
       FROM pg_catalog.pg_stat_activity
       WHERE datname = current_database() AND application_name = $1
         AND state = 'active'
         AND query LIKE 'CREATE UNIQUE INDEX CONCURRENTLY%'`,
      [applicationName],
    );
    if (result.rows[0]) return result.rows[0].pid;
    await sleep(50);
  }
  throw new Error("AUTH_TOKEN_CONCURRENT_INDEX_NOT_OBSERVED");
}

function isAuthorityError(error: unknown): boolean {
  return error instanceof Error && error.name === "AuthTokenAuthorityError";
}

async function main(): Promise<void> {
  process.env.DATABASE_URL = databaseUrl;
  const [dbModule, tokenModule] = await Promise.all([
    import("../src"),
    import("../../../apps/transcribe-md/src/lib/auth-tokens"),
  ]);
  const prisma = dbModule.default;
  const {
    AuthTokenAuthorityError,
    consumeAuthToken,
    consumeLockedAuthToken,
    createAuthToken,
    findAuthTokenCandidate,
    lockCurrentAuthTokenForMutation,
  } = tokenModule;
  const observer = client("auth-token-online-observer");

  async function cleanup(): Promise<void> {
    await prisma.authToken.deleteMany({ where: { userId: { in: userIds } } });
    await prisma.userSession.deleteMany({ where: { userId: { in: userIds } } });
    await prisma.user.deleteMany({ where: { id: { in: userIds } } });
    await prisma.practice.deleteMany({ where: { id: practiceId } });
  }

  try {
    await observer.connect();
    await cleanup();
    const preV5 = await observer.query<{
      indexExists: boolean;
      triggerExists: boolean;
    }>(
      `SELECT to_regclass('public.${AUTH_TOKEN_INDEX}') IS NOT NULL
                AS "indexExists",
              EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = $1 AND NOT tgisinternal
              ) AS "triggerExists"`,
      [AUTH_TOKEN_TRANSITION_TRIGGER],
    );
    assert.deepEqual(preV5.rows[0], {
      indexExists: false,
      triggerExists: false,
    });

    await prisma.practice.create({
      data: {
        id: practiceId,
        name: "Synthetic Auth Token Online Practice",
        slug: practiceId,
        isActive: true,
      },
    });
    for (const [index, id] of userIds.entries()) {
      await prisma.user.create({
        data: {
          id,
          email:
            index === 0
              ? email
              : `auth-token-online-${index}@synthetic.invalid`,
          name: `Synthetic Auth Token User ${index}`,
          passwordHash: "synthetic-not-a-credential",
          role: "DOCTOR",
          products: ["TRANSCRIBE_MD"],
          practiceId,
        },
      });
    }

    for (const [index, ageMinutes] of [3, 2, 1].entries()) {
      await insertToken(observer, {
        id: `synthetic-auth-token-historical-${index}`,
        userId,
        purpose: "PASSWORD_RESET",
        ageMinutes,
      });
    }
    await observer.query(migrationSql);
    const expanded = await readAuthTokenLinearizationStatus(observer as never);
    assert.equal(expanded.transitionTriggerEnabled, true);
    assert.equal(expanded.duplicateGroups, 1);
    assert.equal(expanded.indexExists, false);

    await expectRejected(
      () =>
        observer.query(
          `INSERT INTO public."auth_tokens" (
             "id", "userId", "purpose", "tokenHash", "expiresAt"
           ) VALUES
             ('synthetic-auth-token-multi-one', $1, 'EMAIL_VERIFICATION',
              'synthetic-auth-token-multi-hash-one',
              CURRENT_TIMESTAMP + INTERVAL '1 hour'),
             ('synthetic-auth-token-multi-two', $1, 'EMAIL_VERIFICATION',
              'synthetic-auth-token-multi-hash-two',
              CURRENT_TIMESTAMP + INTERVAL '1 hour')`,
          [raceUserId],
        ),
      "23505",
      "same-statement duplicate unused rows",
    );
    const multiRowCount = await observer.query<{ count: string }>(
      `SELECT COUNT(*)::text AS "count"
       FROM public."auth_tokens"
       WHERE "id" IN (
         'synthetic-auth-token-multi-one', 'synthetic-auth-token-multi-two'
       )`,
    );
    assert.equal(multiRowCount.rows[0]?.count, "0");

    // READ COMMITTED takes a fresh statement snapshot after the advisory wait.
    const firstWriter = client("auth-token-read-committed-first");
    const waitingWriter = client("auth-token-read-committed-waiter");
    await Promise.all([firstWriter.connect(), waitingWriter.connect()]);
    try {
      await firstWriter.query("BEGIN");
      await insertToken(firstWriter, {
        id: "synthetic-auth-token-read-committed-first",
        userId: raceUserId,
        purpose: "PASSWORD_RESET",
      });
      await waitingWriter.query("BEGIN");
      const waitingInsert = insertToken(waitingWriter, {
        id: "synthetic-auth-token-read-committed-second",
        userId: raceUserId,
        purpose: "PASSWORD_RESET",
      });
      await waitForAdvisoryWait(observer, "auth-token-read-committed-waiter");
      await firstWriter.query("COMMIT");
      await expectRejected(
        () => waitingInsert,
        "23505",
        "READ COMMITTED competing unused write",
      );
      await waitingWriter.query("ROLLBACK");
    } finally {
      await Promise.allSettled([firstWriter.end(), waitingWriter.end()]);
    }

    for (const [isolation, purpose] of [
      ["REPEATABLE READ", "EMAIL_VERIFICATION"],
      ["SERIALIZABLE", "EMAIL_CHANGE"],
    ] as const) {
      const established = client(`auth-token-${isolation.replace(" ", "-")}`);
      const opposing = client(`auth-token-${purpose.toLowerCase()}-opposing`);
      await Promise.all([established.connect(), opposing.connect()]);
      try {
        await established.query(`BEGIN ISOLATION LEVEL ${isolation}`);
        await established.query(
          `SELECT COUNT(*) FROM public."auth_tokens" WHERE "userId" = $1`,
          [isolationUserId],
        );
        await opposing.query("BEGIN");
        await insertToken(opposing, {
          id: `synthetic-auth-token-${purpose.toLowerCase()}-first`,
          userId: isolationUserId,
          purpose,
        });
        await opposing.query("COMMIT");
        await expectRejected(
          () =>
            insertToken(established, {
              id: `synthetic-auth-token-${purpose.toLowerCase()}-second`,
              userId: isolationUserId,
              purpose,
            }),
          "25000",
          `${isolation} transitional write`,
        );
        await established.query("ROLLBACK");
      } finally {
        await Promise.allSettled([established.end(), opposing.end()]);
      }
    }

    const reconciledBatch = await reconcileAuthTokenDuplicateBatch(
      observer as never,
      1,
    );
    assert.deepEqual(reconciledBatch, {
      duplicateKeys: 1,
      retiredRows: 2,
      complete: false,
    });
    const reconciledDone = await reconcileAuthTokenDuplicateBatch(
      observer as never,
      1,
    );
    assert.deepEqual(reconciledDone, {
      duplicateKeys: 0,
      retiredRows: 0,
      complete: true,
    });
    const historical = await prisma.authToken.findMany({
      where: { userId, purpose: "PASSWORD_RESET" },
      orderBy: [{ createdAt: "desc" }, { id: "desc" }],
      select: { id: true, usedAt: true },
    });
    assert.equal(historical.length, 3);
    assert.deepEqual(
      historical.filter((row) => row.usedAt === null).map((row) => row.id),
      ["synthetic-auth-token-historical-2"],
    );

    // A valid same-name index with an extra key must never authorize trigger
    // removal, even though its first two columns appear correct.
    await observer.query(
      `CREATE UNIQUE INDEX CONCURRENTLY "${AUTH_TOKEN_INDEX}"
       ON public."auth_tokens" ("userId", "purpose", "id")
       WHERE "usedAt" IS NULL`,
    );
    await expectRejected(
      () => buildAuthTokenUniqueIndex(observer as never),
      "AUTH_TOKEN_INDEX_DEFINITION_MISMATCH",
      "same-name extra-key index",
    );
    const wrongIndexStatus = await readAuthTokenLinearizationStatus(
      observer as never,
    );
    assert.equal(wrongIndexStatus.indexExact, false);
    assert.equal(wrongIndexStatus.transitionTriggerEnabled, true);
    await observer.query(
      `DROP INDEX CONCURRENTLY public."${AUTH_TOKEN_INDEX}"`,
    );

    // Interrupt a live concurrent build while a write transaction is open.
    const blocker = client("auth-token-index-blocker");
    const builder = client("auth-token-index-interrupt-builder");
    const onlineWriter = client("auth-token-index-online-writer");
    await Promise.all([
      blocker.connect(),
      builder.connect(),
      onlineWriter.connect(),
    ]);
    try {
      await blocker.query("BEGIN");
      await blocker.query(
        `UPDATE public."auth_tokens" SET "metadata" = "metadata"
         WHERE "id" = 'synthetic-auth-token-historical-0'`,
      );
      const interruptedBuild = buildAuthTokenUniqueIndex(builder as never);
      const builderPid = await waitForConcurrentIndex(
        observer,
        "auth-token-index-interrupt-builder",
      );
      const writeStarted = performance.now();
      await Promise.race([
        insertToken(onlineWriter, {
          id: "synthetic-auth-token-online-during-index",
          userId: raceUserId,
          purpose: "EMAIL_CHANGE",
          used: true,
        }),
        sleep(2_000).then(() => {
          throw new Error("AUTH_TOKEN_ONLINE_WRITE_BLOCKED");
        }),
      ]);
      assert(performance.now() - writeStarted < 2_000);
      const cancelled = await observer.query<{ cancelled: boolean }>(
        `SELECT pg_cancel_backend($1) AS "cancelled"`,
        [builderPid],
      );
      assert.equal(cancelled.rows[0]?.cancelled, true);
      await expectRejected(
        () => interruptedBuild,
        "57014",
        "interrupted concurrent index",
      );
      await blocker.query("ROLLBACK");
    } finally {
      await blocker.query("ROLLBACK").catch(() => undefined);
      await Promise.allSettled([
        blocker.end(),
        builder.end(),
        onlineWriter.end(),
      ]);
    }
    const invalid = await observer.query<{
      exists: boolean;
      valid: boolean;
      ready: boolean;
    }>(
      `SELECT TRUE AS "exists", indisvalid AS "valid", indisready AS "ready"
       FROM pg_index index_state
       JOIN pg_class index_object ON index_object.oid = index_state.indexrelid
       JOIN pg_namespace namespace ON namespace.oid = index_object.relnamespace
       WHERE namespace.nspname = 'public' AND index_object.relname = $1`,
      [AUTH_TOKEN_INDEX],
    );
    assert.equal(invalid.rows[0]?.exists, true);
    assert.equal(invalid.rows[0]?.valid, false);

    // An invalid shell may be dropped only while the exact transition guard
    // remains installed. A same-name no-op function must fail before mutation.
    await observer.query(
      `CREATE OR REPLACE FUNCTION public.${AUTH_TOKEN_TRANSITION_FUNCTION}()
       RETURNS trigger LANGUAGE plpgsql VOLATILE SECURITY DEFINER
       SET search_path = pg_catalog, public, pg_temp
       AS $$ BEGIN RETURN NEW; END; $$`,
    );
    await expectRejected(
      () => buildAuthTokenUniqueIndex(observer as never),
      "AUTH_TOKEN_TRANSITION_GUARD_MISMATCH",
      "invalid shell without exact transition guard",
    );
    const shellPreserved = await observer.query<{ exists: boolean }>(
      `SELECT to_regclass('public.${AUTH_TOKEN_INDEX}') IS NOT NULL AS "exists"`,
    );
    assert.equal(shellPreserved.rows[0]?.exists, true);

    await observer.query(migrationSql);
    await buildAuthTokenUniqueIndex(observer as never);
    const complete = await readAuthTokenLinearizationStatus(observer as never);
    assert.equal(complete.complete, true);
    await buildAuthTokenUniqueIndex(observer as never);
    assert.equal(
      (await readAuthTokenLinearizationStatus(observer as never)).complete,
      true,
    );

    // A present same-name trigger is tri-state catalog evidence, not a
    // boolean. Even with the final exact index, a subtly widened WHEN trigger
    // must be reported as mismatch and must never be auto-dropped.
    await observer.query(
      `CREATE TRIGGER "${AUTH_TOKEN_TRANSITION_TRIGGER}"
       BEFORE INSERT OR UPDATE OF "userId", "purpose", "usedAt"
       ON public."auth_tokens"
       FOR EACH ROW
       WHEN (NEW."usedAt" IS NULL)
       EXECUTE FUNCTION public.${AUTH_TOKEN_TRANSITION_FUNCTION}()`,
    );
    const malformedTrigger = await readAuthTokenLinearizationStatus(
      observer as never,
    );
    assert.equal(malformedTrigger.transitionTriggerState, "mismatch");
    assert.equal(malformedTrigger.complete, false);
    await expectRejected(
      () => buildAuthTokenUniqueIndex(observer as never),
      "AUTH_TOKEN_TRANSITION_GUARD_MISMATCH",
      "malformed transition trigger with final exact index",
    );
    const malformedPreserved = await observer.query<{ exists: boolean }>(
      `SELECT EXISTS (
         SELECT 1 FROM pg_catalog.pg_trigger
         WHERE tgrelid = 'public.auth_tokens'::pg_catalog.regclass
           AND tgname = $1
       ) AS "exists"`,
      [AUTH_TOKEN_TRANSITION_TRIGGER],
    );
    assert.equal(malformedPreserved.rows[0]?.exists, true);
    await observer.query(
      `DROP TRIGGER "${AUTH_TOKEN_TRANSITION_TRIGGER}"
       ON public."auth_tokens"`,
    );
    assert.equal(
      (await readAuthTokenLinearizationStatus(observer as never)).complete,
      true,
    );

    const lockPool = new Pool({ connectionString: databaseUrl, max: 3 });
    try {
      const firstLock = await acquireAuthTokenOperatorSessionLock(lockPool);
      await expectRejected(
        () => acquireAuthTokenOperatorSessionLock(lockPool),
        "AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY",
        "opposing online operator",
      );
      await firstLock.release();
    } finally {
      await lockPool.end();
    }

    await prisma.authToken.updateMany({
      where: { userId, purpose: "PASSWORD_RESET", usedAt: null },
      data: { usedAt: new Date() },
    });
    const mintAttempts = 16;
    const minted = await Promise.all(
      Array.from({ length: mintAttempts }, () =>
        createAuthToken({
          userId,
          purpose: "PASSWORD_RESET",
          expiresInMs: 60_000,
          expectedUserEmail: email,
        }),
      ),
    );
    const currentAfterMint = await prisma.authToken.findMany({
      where: { userId, purpose: "PASSWORD_RESET", usedAt: null },
      select: { id: true },
    });
    assert.equal(currentAfterMint.length, 1);
    const currentMint = minted.find(
      (row) => row.id === currentAfterMint[0]?.id,
    );
    assert(currentMint);
    const consumers = await Promise.all(
      Array.from({ length: 16 }, () =>
        consumeAuthToken({
          token: currentMint.token,
          purpose: "PASSWORD_RESET",
        }),
      ),
    );
    assert.equal(consumers.filter(Boolean).length, 1);

    const atomic = await createAuthToken({
      userId,
      purpose: "PASSWORD_RESET",
      expiresInMs: 60_000,
      expectedUserEmail: email,
    });
    const candidate = await findAuthTokenCandidate({
      token: atomic.token,
      purpose: "PASSWORD_RESET",
    });
    assert(candidate);
    const mutationAttempts = 12;
    const mutations = await Promise.allSettled(
      Array.from({ length: mutationAttempts }, (_, index) =>
        prisma.$transaction(async (tx) => {
          const locked = await lockCurrentAuthTokenForMutation(tx, {
            token: atomic.token,
            purpose: "PASSWORD_RESET",
            candidate,
          });
          const marker = `Synthetic Auth Token Winner ${index}`;
          await tx.user.update({
            where: { id: userId },
            data: { name: marker },
          });
          await consumeLockedAuthToken(tx, locked.token.id, locked.now);
          return marker;
        }),
      ),
    );
    const winners = mutations.filter(
      (result): result is PromiseFulfilledResult<string> =>
        result.status === "fulfilled",
    );
    assert.equal(winners.length, 1);
    for (const result of mutations) {
      if (result.status === "rejected") {
        assert(
          result.reason instanceof AuthTokenAuthorityError ||
            isAuthorityError(result.reason),
        );
      }
    }
    const finalUser = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: { name: true },
    });
    assert.equal(finalUser.name, winners[0]?.value);
    assert.equal(
      await consumeAuthToken({
        token: atomic.token,
        purpose: "PASSWORD_RESET",
      }),
      null,
    );

    process.stdout.write(
      `${JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        preV5LegacyDuplicates: 3,
        deterministicRetiredRows: reconciledBatch.retiredRows,
        readCommittedFreshSnapshotAfterAdvisoryWait: true,
        sameStatementDuplicatesRejectedAtomically: true,
        repeatableReadRejected: true,
        serializableRejected: true,
        extraKeyIndexRejected: true,
        concurrentBuildInterrupted: true,
        invalidShellPreservedWithoutExactGuard: true,
        invalidShellRecovered: true,
        onlineWriteDuringConcurrentBuild: true,
        operatorContentionRejected: true,
        idempotentFinalization: true,
        malformedTriggerWithFinalIndexRejected: true,
        finalCatalogComplete: complete.complete,
        concurrentMints: mintAttempts,
        remainingCurrentTokens: currentAfterMint.length,
        successfulConcurrentConsumes: consumers.filter(Boolean).length,
        atomicMutationWinners: winners.length,
      })}\n`,
    );
  } finally {
    try {
      await cleanup();
    } finally {
      await Promise.allSettled([prisma.$disconnect(), observer.end()]);
    }
  }
}

void main().catch(() => {
  process.stderr.write("AUTH_TOKEN_LINEARIZATION_PG_TEST_FAILED\n");
  process.exitCode = 1;
});
