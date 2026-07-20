#!/usr/bin/env tsx

// Disposable PostgreSQL proof for current physician/patient mutation locks.
// Fixtures contain synthetic identifiers and non-clinical sentinel text only.
// Temporary shadow tables disappear with this connection.

import assert from "node:assert/strict";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import {
  ClinicalPatientAuthorityError,
  currentClinicalPatientReadAuthoritySql,
  lockAndAssertCurrentClinicalPatientActor,
  lockAndReadCurrentClinicalPatient,
  lockCurrentClinicalPatientAfterActor,
  lockNamedCurrentClinicalPatientAfterActor,
} from "../../../apps/transcribe-md/src/lib/clinical-patient-authority";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TRANSCRIBE_MD_CLINICAL_PATIENT_AUTHORITY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error(
    "Disposable clinical-patient authority test URL is required.",
  );
}
assertNonProdDatabase(databaseUrl);

const db = new PrismaClient({
  adapter: new PrismaPg({ connectionString: databaseUrl, max: 1 }),
});

const actor = {
  userId: "synthetic-patient-authority-doctor",
  practiceId: "synthetic-patient-authority-practice",
};
const ordinaryPatientId = "synthetic-patient-authority-patient";
const reservedMarker = "SYNTHETIC-QA-ONLY";

async function setupShadowSchema(): Promise<void> {
  await db.$executeRawUnsafe(`
    DO $types$
    BEGIN
      IF to_regtype('public."UserRole"') IS NULL THEN
        CREATE TYPE public."UserRole" AS ENUM
          ('DOCTOR', 'ADMIN', 'SUPER_ADMIN', 'STAFF');
      END IF;
      IF to_regtype('public."Product"') IS NULL THEN
        CREATE TYPE public."Product" AS ENUM
          ('MEDDOC_PRO', 'TRANSCRIBE_MD', 'SUPER_ADMIN');
      END IF;
    END;
    $types$;

    CREATE TEMP TABLE "practices" (
      "id" TEXT PRIMARY KEY,
      "isActive" BOOLEAN NOT NULL
    );
    CREATE TEMP TABLE "users" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL,
      "role" public."UserRole" NOT NULL,
      "isActive" BOOLEAN NOT NULL,
      "deactivatedAt" TIMESTAMPTZ,
      "suspendedAt" TIMESTAMPTZ,
      "softDeletedAt" TIMESTAMPTZ,
      "products" public."Product"[] NOT NULL
    );
    CREATE TEMP TABLE "transcribe_md_patients" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL,
      "name" TEXT NOT NULL,
      "dateOfBirth" DATE,
      "externalId" TEXT,
      "mrn" TEXT,
      "insurance" TEXT,
      "problemList" JSONB,
      "deletedAt" TIMESTAMPTZ,
      "createdAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    );
    CREATE TEMP TABLE "transcribe_visits" (
      "id" TEXT PRIMARY KEY,
      "userId" TEXT NOT NULL,
      "patientId" TEXT NOT NULL,
      "patientName" TEXT
    );

    INSERT INTO "practices" VALUES
      ('${actor.practiceId}', TRUE),
      ('synthetic-patient-authority-other-practice', TRUE);
    INSERT INTO "users" VALUES
      ('${actor.userId}', '${actor.practiceId}', 'DOCTOR', TRUE,
       NULL, NULL, NULL,
       ARRAY['TRANSCRIBE_MD']::public."Product"[]);
    INSERT INTO "transcribe_md_patients" (
      "id", "practiceId", "name", "externalId", "deletedAt",
      "createdAt", "updatedAt"
    ) VALUES
      ('${ordinaryPatientId}', '${actor.practiceId}',
       'Synthetic Ordinary Patient', NULL, NULL,
       '2026-07-20T00:00:00.000Z', '2026-07-20T00:00:00.000Z'),
      ('synthetic-patient-authority-reserved', '${actor.practiceId}',
       'Synthetic Reserved Replica', '${reservedMarker}', NULL,
       '2026-07-20T00:00:00.000Z', '2026-07-20T00:00:00.000Z'),
      ('synthetic-patient-authority-deleted', '${actor.practiceId}',
       'Synthetic Deleted Replica', NULL, '2026-07-20T00:00:01.000Z',
       '2026-07-20T00:00:00.000Z', '2026-07-20T00:00:01.000Z');
  `);
}

async function visitCount(): Promise<bigint> {
  const rows = await db.$queryRaw<Array<{ count: bigint }>>`
    SELECT COUNT(*)::bigint AS "count" FROM "transcribe_visits"
  `;
  return rows[0]?.count ?? -1n;
}

async function insertVisitWithPatient(
  visitId: string,
  patientId: string,
): Promise<void> {
  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    const patient = await lockAndReadCurrentClinicalPatient({
      tx,
      actor,
      patientId,
    });
    if (!patient) throw new ClinicalPatientAuthorityError();
    await tx.$executeRaw`
      INSERT INTO "transcribe_visits" (
        "id", "userId", "patientId", "patientName"
      ) VALUES (
        ${visitId}, ${actor.userId}, ${patient.id}, ${patient.name}
      )
    `;
  });
}

async function readCurrentRoster(includeDeleted = false) {
  const authority = currentClinicalPatientReadAuthoritySql({
    actor,
    patientAlias: "patient",
    includeDeleted,
  });
  return db.$queryRaw<Array<{ id: string; name: string }>>(Prisma.sql`
    SELECT patient."id", patient."name"
    FROM "transcribe_md_patients" patient
    WHERE ${authority}
    ORDER BY patient."id"
  `);
}

async function proveSameStatementRosterAuthority(): Promise<void> {
  assert.deepEqual(
    (await readCurrentRoster()).map((row) => row.id),
    [ordinaryPatientId],
  );
  assert.deepEqual(
    (await readCurrentRoster(true)).map((row) => row.id),
    ["synthetic-patient-authority-deleted", ordinaryPatientId].sort(),
  );

  await db.$executeRaw`
    UPDATE "users"
    SET "practiceId" = 'synthetic-patient-authority-other-practice'
    WHERE "id" = ${actor.userId}
  `;
  assert.deepEqual(await readCurrentRoster(), []);
  await db.$executeRaw`
    UPDATE "users"
    SET "practiceId" = ${actor.practiceId}
    WHERE "id" = ${actor.userId}
  `;

  await db.$executeRaw`
    UPDATE "practices" SET "isActive" = FALSE
    WHERE "id" = ${actor.practiceId}
  `;
  assert.deepEqual(await readCurrentRoster(), []);
  await db.$executeRaw`
    UPDATE "practices" SET "isActive" = TRUE
    WHERE "id" = ${actor.practiceId}
  `;

  await db.$executeRaw`
    UPDATE "users" SET "suspendedAt" = clock_timestamp()
    WHERE "id" = ${actor.userId}
  `;
  assert.deepEqual(await readCurrentRoster(), []);
  await db.$executeRaw`
    UPDATE "users" SET "suspendedAt" = NULL
    WHERE "id" = ${actor.userId}
  `;
}

async function proveVisitLinkAuthority(): Promise<void> {
  await insertVisitWithPatient("synthetic-authorized-visit", ordinaryPatientId);
  assert.equal(await visitCount(), 1n);

  await db.$executeRaw`
    UPDATE "users"
    SET "practiceId" = 'synthetic-patient-authority-other-practice'
    WHERE "id" = ${actor.userId}
  `;
  await assert.rejects(
    insertVisitWithPatient("synthetic-transfer-denied", ordinaryPatientId),
    ClinicalPatientAuthorityError,
  );
  assert.equal(await visitCount(), 1n);
  await db.$executeRaw`
    UPDATE "users"
    SET "practiceId" = ${actor.practiceId}
    WHERE "id" = ${actor.userId}
  `;

  await db.$executeRaw`
    UPDATE "transcribe_md_patients"
    SET "deletedAt" = clock_timestamp()
    WHERE "id" = ${ordinaryPatientId}
  `;
  await assert.rejects(
    insertVisitWithPatient("synthetic-deleted-denied", ordinaryPatientId),
    ClinicalPatientAuthorityError,
  );
  assert.equal(await visitCount(), 1n);
  await db.$executeRaw`
    UPDATE "transcribe_md_patients"
    SET "deletedAt" = NULL, "externalId" = ${reservedMarker}
    WHERE "id" = ${ordinaryPatientId}
  `;
  await assert.rejects(
    insertVisitWithPatient("synthetic-reserved-denied", ordinaryPatientId),
    ClinicalPatientAuthorityError,
  );
  assert.equal(await visitCount(), 1n);
  await db.$executeRaw`
    UPDATE "transcribe_md_patients"
    SET "externalId" = NULL
    WHERE "id" = ${ordinaryPatientId}
  `;
}

async function proveFreeTextCreateRollbackAndLink(): Promise<void> {
  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    await lockAndAssertCurrentClinicalPatientActor({ tx, actor });
    const existing = await lockNamedCurrentClinicalPatientAfterActor({
      tx,
      actor,
      patientName: "Synthetic Free Text Patient",
    });
    assert.equal(existing, null);
    await tx.$executeRaw`
      INSERT INTO "transcribe_md_patients" (
        "id", "practiceId", "name", "externalId", "deletedAt"
      ) VALUES (
        'synthetic-free-text-patient', ${actor.practiceId},
        'Synthetic Free Text Patient', NULL, NULL
      )
    `;
    const created = await lockCurrentClinicalPatientAfterActor({
      tx,
      actor,
      patientId: "synthetic-free-text-patient",
    });
    assert.equal(created?.id, "synthetic-free-text-patient");
    await tx.$executeRaw`
      INSERT INTO "transcribe_visits" (
        "id", "userId", "patientId", "patientName"
      ) VALUES (
        'synthetic-free-text-visit', ${actor.userId},
        ${created!.id}, ${created!.name}
      )
    `;
  });
  assert.equal(await visitCount(), 2n);

  await assert.rejects(
    db.$transaction(async (tx: Prisma.TransactionClient) => {
      await lockAndAssertCurrentClinicalPatientActor({ tx, actor });
      await tx.$executeRaw`
        INSERT INTO "transcribe_md_patients" (
          "id", "practiceId", "name", "externalId", "deletedAt"
        ) VALUES (
          'synthetic-free-text-rollback', ${actor.practiceId},
          'Synthetic Rollback Candidate', ${reservedMarker}, NULL
        )
      `;
      const reasserted = await lockCurrentClinicalPatientAfterActor({
        tx,
        actor,
        patientId: "synthetic-free-text-rollback",
      });
      assert.equal(reasserted, null);
      throw new ClinicalPatientAuthorityError();
    }),
    ClinicalPatientAuthorityError,
  );
  const rolledBack = await db.$queryRaw<Array<{ count: bigint }>>`
    SELECT COUNT(*)::bigint AS "count"
    FROM "transcribe_md_patients"
    WHERE "id" = 'synthetic-free-text-rollback'
  `;
  assert.equal(rolledBack[0]?.count, 0n);
  assert.equal(await visitCount(), 2n);
}

async function proveScopedPatchAndIdempotentDelete(): Promise<void> {
  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    const current = await lockAndReadCurrentClinicalPatient({
      tx,
      actor,
      patientId: ordinaryPatientId,
    });
    assert.ok(current);
    const updated = await tx.$executeRaw`
      UPDATE "transcribe_md_patients"
      SET "name" = 'Synthetic Patched Patient',
          "updatedAt" = '2026-07-20T00:00:00.100Z'
      WHERE "id" = ${current.id}
        AND "practiceId" = ${actor.practiceId}
        AND "updatedAt" = ${current.updatedAt}
        AND "deletedAt" IS NULL
        AND "externalId" IS DISTINCT FROM ${reservedMarker}
    `;
    assert.equal(updated, 1);
  });

  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    const current = await lockAndReadCurrentClinicalPatient({
      tx,
      actor,
      patientId: ordinaryPatientId,
      includeDeleted: true,
    });
    assert.ok(current);
    const deleted = await tx.$executeRaw`
      UPDATE "transcribe_md_patients"
      SET "deletedAt" = '2026-07-20T00:00:00.200Z',
          "updatedAt" = '2026-07-20T00:00:00.200Z'
      WHERE "id" = ${current.id}
        AND "practiceId" = ${actor.practiceId}
        AND "updatedAt" = ${current.updatedAt}
        AND "deletedAt" IS NULL
        AND "externalId" IS DISTINCT FROM ${reservedMarker}
    `;
    assert.equal(deleted, 1);
  });

  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    const repeated = await lockAndReadCurrentClinicalPatient({
      tx,
      actor,
      patientId: ordinaryPatientId,
      includeDeleted: true,
    });
    assert.ok(repeated?.deletedAt);
  });
}

async function main(): Promise<void> {
  try {
    await setupShadowSchema();
    await proveSameStatementRosterAuthority();
    await proveVisitLinkAuthority();
    await proveFreeTextCreateRollbackAndLink();
    await proveScopedPatchAndIdempotentDelete();
    console.log(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        actorBoundPhiProjection: true,
        sameStatementRosterAuthority: true,
        rosterTransferInactiveSuspensionDenials: true,
        transferDeletionReservedDenials: true,
        freeTextTransactionalReassertion: true,
        scopedEpochCas: true,
        idempotentRepeatDelete: true,
      }),
    );
  } finally {
    await db.$disconnect();
  }
}

void main().catch((error: unknown) => {
  console.error(
    error instanceof Error
      ? (error.stack ?? error.message)
      : "Clinical-patient authority proof failed.",
  );
  process.exitCode = 1;
});
