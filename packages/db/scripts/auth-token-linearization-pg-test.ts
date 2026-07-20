#!/usr/bin/env tsx

// Actual-PostgreSQL proof for one-current-token issuance and atomic redemption.
// Synthetic identifiers only; the target must be a disposable database.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { Client } from "pg";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.AUTH_TOKEN_LINEARIZATION_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable auth-token test URL is required.");
}
assertNonProdDatabase(databaseUrl);

const practiceId = "synthetic-auth-token-practice";
const userId = "synthetic-auth-token-doctor";
const email = "synthetic-auth-token-doctor@example.test";
const migrationUrl = new URL(
  "../prisma/migrations/20260720150000_auth_token_linearization_v5/migration.sql",
  import.meta.url,
);

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
    hashToken,
    lockCurrentAuthTokenForMutation,
  } = tokenModule;
  const client = new Client({ connectionString: databaseUrl });

  async function cleanup(): Promise<void> {
    await prisma.authToken.deleteMany({ where: { userId } });
    await prisma.userSession.deleteMany({ where: { userId } });
    await prisma.user.deleteMany({ where: { id: userId } });
    await prisma.practice.deleteMany({ where: { id: practiceId } });
  }

  try {
    await client.connect();
    await cleanup();
    await prisma.practice.create({
      data: {
        id: practiceId,
        name: "Synthetic Auth Token Practice",
        slug: "synthetic-auth-token-practice",
        isActive: true,
      },
    });
    await prisma.user.create({
      data: {
        id: userId,
        email,
        name: "Synthetic Auth Token Doctor",
        passwordHash: "synthetic-not-a-credential",
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
        practiceId,
      },
    });

    // Rehearse the exact migration against a deliberately duplicated legacy
    // state. Dropping the new index is safe only because the target guard above
    // positively identifies this disposable database.
    await client.query(
      'DROP INDEX IF EXISTS "auth_tokens_one_unused_per_user_purpose"',
    );
    const historical = [
      { id: "synthetic-auth-token-oldest", ageMinutes: 3 },
      { id: "synthetic-auth-token-middle", ageMinutes: 2 },
      { id: "synthetic-auth-token-newest", ageMinutes: 1 },
    ];
    for (const row of historical) {
      await prisma.authToken.create({
        data: {
          id: row.id,
          userId,
          purpose: "PASSWORD_RESET",
          tokenHash: hashToken(`${row.id}-raw-token-with-sufficient-length`),
          expiresAt: new Date(Date.now() + 60 * 60 * 1000),
          createdAt: new Date(Date.now() - row.ageMinutes * 60_000),
        },
      });
    }
    const migrationSql = await readFile(fileURLToPath(migrationUrl), "utf8");
    await client.query(migrationSql);

    const reconciled = await prisma.authToken.findMany({
      where: { userId, purpose: "PASSWORD_RESET" },
      orderBy: [{ createdAt: "asc" }, { id: "asc" }],
      select: { id: true, usedAt: true },
    });
    assert.equal(reconciled.length, 3);
    assert.deepEqual(
      reconciled.filter((row) => row.usedAt === null).map((row) => row.id),
      ["synthetic-auth-token-newest"],
      "the migration must retain only the newest historical unused token",
    );
    const index = await client.query<{
      indisunique: boolean;
      predicate: string | null;
    }>(
      `SELECT i.indisunique,
              pg_get_expr(i.indpred, i.indrelid) AS predicate
         FROM pg_index i
         JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = 'auth_tokens_one_unused_per_user_purpose'`,
    );
    assert.equal(index.rowCount, 1);
    assert.equal(index.rows[0]?.indisunique, true);
    assert.match(index.rows[0]?.predicate ?? "", /"usedAt" IS NULL/u);

    await prisma.authToken.updateMany({
      where: { userId, usedAt: null },
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
    assert.equal(
      currentAfterMint.length,
      1,
      "concurrent minting must leave exactly one unused token",
    );
    assert.ok(minted.some((row) => row.id === currentAfterMint[0]?.id));
    assert.ok(minted.every((row) => row.userEmail === email));

    const currentMint = minted.find(
      (row) => row.id === currentAfterMint[0]?.id,
    );
    assert.ok(currentMint);
    const consumers = await Promise.all(
      Array.from({ length: 16 }, () =>
        consumeAuthToken({
          token: currentMint.token,
          purpose: "PASSWORD_RESET",
        }),
      ),
    );
    assert.equal(
      consumers.filter(Boolean).length,
      1,
      "exactly one concurrent generic redemption may succeed",
    );

    const atomic = await createAuthToken({
      userId,
      purpose: "PASSWORD_RESET",
      expiresInMs: 60_000,
      expectedUserEmail: email,
    });
    assert.equal(atomic.userEmail, email);
    const candidate = await findAuthTokenCandidate({
      token: atomic.token,
      purpose: "PASSWORD_RESET",
    });
    assert.ok(candidate);
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
    assert.equal(
      winners.length,
      1,
      "token consumption and identity mutation must have one winner",
    );
    for (const result of mutations) {
      if (result.status === "rejected") {
        assert.ok(
          result.reason instanceof AuthTokenAuthorityError ||
            isAuthorityError(result.reason),
          "every losing mutation must fail with token authority denial",
        );
      }
    }
    const finalUser = await prisma.user.findUniqueOrThrow({
      where: { id: userId },
      select: { name: true },
    });
    assert.equal(finalUser.name, winners[0]?.value);
    const replay = await consumeAuthToken({
      token: atomic.token,
      purpose: "PASSWORD_RESET",
    });
    assert.equal(replay, null, "a redeemed token must fail closed on replay");

    process.stdout.write(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        reconciledHistoricalRows: reconciled.length,
        retainedHistoricalUnused: 1,
        concurrentMints: mintAttempts,
        remainingCurrentTokens: currentAfterMint.length,
        successfulConcurrentConsumes: consumers.filter(Boolean).length,
        atomicMutationAttempts: mutationAttempts,
        atomicMutationWinners: winners.length,
        replayAccepted: replay !== null,
      }) + "\n",
    );
  } finally {
    try {
      await cleanup();
    } finally {
      await Promise.allSettled([prisma.$disconnect(), client.end()]);
    }
  }
}

main().catch((error) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : "Auth-token PostgreSQL proof failed."}\n`,
  );
  process.exitCode = 1;
});
