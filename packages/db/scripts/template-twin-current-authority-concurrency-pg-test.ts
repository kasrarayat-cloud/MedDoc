#!/usr/bin/env tsx

// Synthetic PostgreSQL proof that the canonical practice -> physician locks
// hold tenant authority stable across a multi-statement content projection.

import assert from "node:assert/strict";

import { assertNonProdDatabase } from "../src/db-guard";
import {
  lockAndAssertActiveTemplateTwinPractice,
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "../../../apps/transcribe-md/src/lib/template-twin/final-claim-authority";

const databaseUrl =
  process.env.TEMPLATE_TWIN_CURRENT_AUTHORITY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable current-authority test URL is required.");
}
assertNonProdDatabase(databaseUrl);
if (process.env.DATABASE_URL && process.env.DATABASE_URL !== databaseUrl) {
  throw new Error(
    "DATABASE_URL must exactly match the guarded disposable current-authority test URL.",
  );
}
process.env.DATABASE_URL = databaseUrl;
process.env.TEMPLATE_TWIN_CURRENT_AUTHORITY_TEST_DATABASE_URL = databaseUrl;

const prismaPromise = import("../src").then(({ default: prisma }) => prisma);

const practiceId = "synthetic-current-authority-lock-practice";
const userId = "synthetic-current-authority-lock-doctor";

async function main(): Promise<void> {
  const prisma = await prismaPromise;
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
        name: "Synthetic Current Authority Lock Practice",
        slug: "synthetic-current-authority-lock-practice",
        isActive: true,
      },
    });
    await prisma.user.create({
      data: {
        id: userId,
        email: "synthetic-current-authority-lock@example.test",
        name: "Synthetic Current Authority Lock Doctor",
        passwordHash: "synthetic-not-a-credential",
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
        practiceId,
      },
    });

    let announceLocks!: () => void;
    const locksAcquired = new Promise<void>((resolve) => {
      announceLocks = resolve;
    });
    let releaseLocks!: () => void;
    const holdLocks = new Promise<void>((resolve) => {
      releaseLocks = resolve;
    });

    const projection = prisma.$transaction(async (tx) => {
      await lockAndAssertActiveTemplateTwinPractice({ tx, practiceId });
      await lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: { userId, practiceId },
      });
      announceLocks();
      await holdLocks;
      const stillActive = await tx.practice.findUnique({
        where: { id: practiceId },
        select: { isActive: true },
      });
      assert.equal(stillActive?.isActive, true);
    });

    await locksAcquired;
    let deactivationCommitted = false;
    const deactivation = prisma.practice
      .update({ where: { id: practiceId }, data: { isActive: false } })
      .then(() => {
        deactivationCommitted = true;
      });
    await new Promise((resolve) => setTimeout(resolve, 100));
    assert.equal(
      deactivationCommitted,
      false,
      "practice deactivation must wait for the authority projection transaction",
    );

    releaseLocks();
    await projection;
    await deactivation;
    assert.equal(deactivationCommitted, true);

    await assert.rejects(
      prisma.$transaction(async (tx) => {
        await lockAndAssertActiveTemplateTwinPractice({ tx, practiceId });
      }),
      TemplateTwinCurrentPhysicianAuthorityError,
    );

    process.stdout.write(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        canonicalLockOrder: "practice_then_physician",
        concurrentPracticeDeactivationBlocked: true,
        postDeactivationReadDenied: true,
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
    `${error instanceof Error ? error.message : "Current-authority concurrency proof failed."}\n`,
  );
  process.exitCode = 1;
});
