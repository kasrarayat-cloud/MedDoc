#!/usr/bin/env tsx

// Actual-PostgreSQL proof for Template Twin generic mutation boundaries.
// Synthetic identifiers and non-clinical sentinel text only; no provider,
// storage, production service, or external network is contacted. The target
// must be a disposable database. Temporary shadow tables keep the proof
// isolated from migrated public data and disappear with this connection.

import assert from "node:assert/strict";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import { lockAndAssertCurrentTemplateTwinPhysician } from "../../../apps/transcribe-md/src/lib/template-twin/final-claim-authority";
import {
  lockAndAssertOrdinaryClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
} from "../../../apps/transcribe-md/src/lib/template-twin/ordinary-visit-mutation-authority";
import { enqueueTemplateTwinVisitMutationAudit } from "../../../apps/transcribe-md/src/lib/template-twin/visit-mutation-audit";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "../../../apps/transcribe-md/src/lib/template-twin/durable-visit-exclusion";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_MUTATION_AUTHORITY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable mutation-authority test URL is required.");
}
assertNonProdDatabase(databaseUrl);

const db = new PrismaClient({
  adapter: new PrismaPg({ connectionString: databaseUrl, max: 1 }),
});

const actorId = "synthetic-mutation-doctor";
const practiceId = "synthetic-mutation-practice";
const admittedAt = new Date("2026-07-20T00:00:00.000Z");
const changedAt = new Date("2026-07-20T00:00:01.000Z");

async function setupShadowSchema(): Promise<void> {
  // The real physician lock uses explicit production enum casts. A blank
  // disposable database receives only these type definitions; an already
  // migrated disposable database keeps its canonical definitions.
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
  `);

  await db.$executeRawUnsafe(`
    CREATE TEMP TABLE "practices" (
      "id" TEXT PRIMARY KEY,
      "isActive" BOOLEAN NOT NULL,
      "templateTwinEnabled" BOOLEAN NOT NULL,
      "templateTwinRolloutGeneration" BIGINT NOT NULL
    );
    CREATE TEMP TABLE "users" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT,
      "email" TEXT,
      "role" public."UserRole" NOT NULL,
      "isActive" BOOLEAN NOT NULL,
      "deactivatedAt" TIMESTAMPTZ,
      "suspendedAt" TIMESTAMPTZ,
      "softDeletedAt" TIMESTAMPTZ,
      "products" public."Product"[] NOT NULL
    );
    CREATE TEMP TABLE "template_twin_rollout_controls" (
      "id" TEXT PRIMARY KEY,
      "enabled" BOOLEAN NOT NULL,
      "generation" BIGINT NOT NULL,
      "rollbackFenceState" TEXT NOT NULL,
      "rollbackOperationId" UUID
    );
    CREATE TEMP TABLE "transcribe_md_patients" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL,
      "externalId" TEXT
    );
    CREATE TEMP TABLE "note_templates" (
      "id" TEXT PRIMARY KEY,
      "doctorId" TEXT,
      "templateKind" TEXT NOT NULL,
      "version" INTEGER NOT NULL
    );
    -- patientId is intentionally nullable only in this shadow table so the
    -- historical/null corruption case can be proven fail-closed.
    CREATE TEMP TABLE "transcribe_visits" (
      "id" TEXT PRIMARY KEY,
      "userId" TEXT NOT NULL,
      "patientId" TEXT,
      "noteTemplateId" TEXT,
      "noteTemplateVersion" INTEGER,
      "updatedAt" TIMESTAMPTZ NOT NULL,
      "soapFinal" TEXT,
      "soapVersion" INTEGER NOT NULL DEFAULT 1
    );
    CREATE TEMP TABLE "template_twin_source_artifacts" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL,
      "validationStatus" TEXT NOT NULL
    );
    CREATE TEMP TABLE "template_twin_compiled_versions" (
      "id" TEXT PRIMARY KEY,
      "sourceArtifactId" TEXT NOT NULL,
      "noteTemplateId" TEXT NOT NULL,
      "certificationStatus" TEXT NOT NULL
    );
    CREATE TEMP TABLE "template_twin_certifications" (
      "id" TEXT PRIMARY KEY,
      "compiledVersionId" TEXT NOT NULL,
      "certifiedById" TEXT NOT NULL,
      "providerAuthorizationMode" TEXT NOT NULL,
      "providerAuthorizationAdmissionId" TEXT
    );
    CREATE TEMP TABLE "template_twin_fill_manifests" (
      "id" TEXT PRIMARY KEY,
      "visitId" TEXT NOT NULL,
      "practiceId" TEXT NOT NULL,
      "compiledVersionId" TEXT NOT NULL,
      "noteTemplateId" TEXT NOT NULL,
      "noteTemplateVersion" INTEGER NOT NULL
    );
    CREATE TEMP TABLE "template_twin_synthetic_qa_runs" (
      "id" TEXT PRIMARY KEY,
      "visitId" TEXT NOT NULL
    );
    CREATE TEMP TABLE "template_twin_synthetic_qa_admissions" (
      "id" TEXT PRIMARY KEY,
      "visitId" TEXT
    );
    CREATE TEMP TABLE "template_twin_provider_executions" (
      "id" TEXT PRIMARY KEY,
      "visitId" TEXT,
      "practiceId" TEXT NOT NULL,
      "actorUserId" TEXT NOT NULL,
      "sourceArtifactId" TEXT,
      "compiledVersionId" TEXT,
      "noteTemplateId" TEXT,
      "noteTemplateVersion" INTEGER,
      "providerMode" TEXT NOT NULL,
      "syntheticAdmissionId" TEXT
    );
    CREATE TEMP TABLE "template_twin_audit_outbox" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL,
      "actorId" TEXT,
      "actorEmailSnapshot" TEXT,
      "ipAddress" INET,
      "userAgent" TEXT,
      "eventKey" TEXT NOT NULL UNIQUE,
      "action" TEXT NOT NULL,
      "targetId" TEXT,
      "targetType" TEXT,
      "metadata" JSONB,
      "status" TEXT NOT NULL DEFAULT 'PENDING',
      "attemptCount" INTEGER NOT NULL DEFAULT 0,
      "availableAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      "deliveredAt" TIMESTAMPTZ,
      "lastErrorCode" TEXT,
      "createdAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    );
  `);

  await db.$executeRawUnsafe(`
    INSERT INTO "practices" VALUES
      ('${practiceId}', TRUE, TRUE, 7),
      ('synthetic-mutation-other-practice', TRUE, TRUE, 3);
    INSERT INTO "users" VALUES
      ('${actorId}', '${practiceId}', 'synthetic-doctor@example.invalid',
       'DOCTOR', TRUE, NULL, NULL, NULL,
       ARRAY['TRANSCRIBE_MD']::public."Product"[]);
    INSERT INTO "template_twin_rollout_controls" VALUES
      ('global', TRUE, 11, 'OPEN', NULL);

    INSERT INTO "transcribe_md_patients" VALUES
      ('patient-ordinary', '${practiceId}', NULL),
      ('patient-template', '${practiceId}', NULL),
      ('patient-reserved', '${practiceId}', 'SYNTHETIC-QA-ONLY'),
      ('patient-live', '${practiceId}', NULL);
    INSERT INTO "note_templates" VALUES
      ('template-ordinary', '${actorId}', 'structured', 2),
      ('template-kind-drift', '${actorId}', 'structured', 4),
      ('template-live', '${actorId}', 'template_twin_docx', 4);
    INSERT INTO "template_twin_source_artifacts" VALUES
      ('source-live', '${practiceId}', 'accepted'),
      ('source-other', '${practiceId}', 'accepted');
    INSERT INTO "template_twin_compiled_versions" VALUES
      ('compiled-live', 'source-live', 'template-live', 'CERTIFIED'),
      ('compiled-kind-drift', 'source-live', 'template-kind-drift', 'CERTIFIED'),
      ('compiled-other', 'source-other', 'template-live', 'CERTIFIED');
    INSERT INTO "template_twin_certifications" VALUES
      ('cert-live', 'compiled-live', '${actorId}', 'LIVE', NULL);

    INSERT INTO "transcribe_visits" VALUES
      ('visit-ordinary', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'ordinary-v1', 1),
      ('visit-template-ordinary', '${actorId}', 'patient-template',
       'template-ordinary', 2, '${admittedAt.toISOString()}',
       'ordinary-template-v1', 1),
      ('visit-kind-drift', '${actorId}', 'patient-template',
       'template-kind-drift', 4, '${admittedAt.toISOString()}',
       'kind-drift-marker', 1),
      ('visit-fill', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'fill-marker', 1),
      ('visit-run', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'run-marker', 1),
      ('visit-admission', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'admission-marker', 1),
      ('visit-execution', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'execution-marker', 1),
      ('visit-reserved', '${actorId}', 'patient-reserved', NULL, NULL,
       '${admittedAt.toISOString()}', 'reserved-marker', 1),
      ('visit-missing-patient', '${actorId}', 'patient-missing', NULL, NULL,
       '${admittedAt.toISOString()}', 'missing-patient-marker', 1),
      ('visit-null-patient', '${actorId}', NULL, NULL, NULL,
       '${admittedAt.toISOString()}', 'null-patient-marker', 1),
      ('visit-provider-window', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'provider-window-v1', 1),
      ('visit-drift', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'drift-v1', 1),
      ('visit-audit-rollback', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'audit-before', 1),
      ('visit-live', '${actorId}', 'patient-live', 'template-live', 4,
       '${admittedAt.toISOString()}', 'live-v1', 1),
      ('cleanup-ordinary', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-ordinary', 1),
      ('cleanup-template', '${actorId}', 'patient-live', 'template-live', 4,
       '${admittedAt.toISOString()}', 'cleanup-template', 1),
      ('cleanup-compiled-kind-drift', '${actorId}', 'patient-template',
       'template-kind-drift', 4, '${admittedAt.toISOString()}',
       'cleanup-compiled-kind-drift', 1),
      ('cleanup-fill', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-fill', 1),
      ('cleanup-run', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-run', 1),
      ('cleanup-admission', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-admission', 1),
      ('cleanup-execution', '${actorId}', 'patient-ordinary', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-execution', 1),
      ('cleanup-reserved', '${actorId}', 'patient-reserved', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-reserved', 1),
      ('cleanup-missing-patient', '${actorId}', 'patient-missing', NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-missing', 1),
      ('cleanup-null-patient', '${actorId}', NULL, NULL, NULL,
       '${admittedAt.toISOString()}', 'cleanup-null', 1);

    INSERT INTO "template_twin_fill_manifests" VALUES
      ('marker-fill', 'visit-fill', '${practiceId}', 'compiled-live',
       'template-live', 4),
      ('cleanup-fill-marker', 'cleanup-fill', '${practiceId}',
       'compiled-live', 'template-live', 4),
      ('fill-live', 'visit-live', '${practiceId}', 'compiled-live',
       'template-live', 4);
    INSERT INTO "template_twin_synthetic_qa_runs" VALUES
      ('marker-run', 'visit-run'),
      ('cleanup-run-marker', 'cleanup-run');
    INSERT INTO "template_twin_synthetic_qa_admissions" VALUES
      ('marker-admission', 'visit-admission'),
      ('cleanup-admission-marker', 'cleanup-admission');
    INSERT INTO "template_twin_provider_executions" VALUES
      ('marker-execution', 'visit-execution', '${practiceId}', '${actorId}',
       NULL, NULL, NULL, NULL, 'LIVE', NULL),
      ('cleanup-execution-marker', 'cleanup-execution', '${practiceId}',
       '${actorId}', NULL, NULL, NULL, NULL, 'LIVE', NULL),
      ('execution-live', 'visit-live', '${practiceId}', '${actorId}',
       'source-live', 'compiled-live', 'template-live', 4, 'LIVE', NULL);
  `);
}

async function ordinaryFence(input: {
  visitId: string;
  admittedPatientId?: string;
  admittedNoteTemplateId?: string | null;
  admittedVisitUpdatedAt?: Date;
}): Promise<void> {
  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    await lockAndAssertOrdinaryClinicalMutation({
      tx,
      visitId: input.visitId,
      actorUserId: actorId,
      admittedVisitUpdatedAt: input.admittedVisitUpdatedAt ?? admittedAt,
      admittedPatientId: input.admittedPatientId ?? "patient-ordinary",
      admittedNoteTemplateId: input.admittedNoteTemplateId ?? null,
    });
  });
}

async function expectOrdinaryFenceDenied(
  input: Parameters<typeof ordinaryFence>[0],
): Promise<void> {
  await assert.rejects(
    ordinaryFence(input),
    (error: unknown) =>
      error instanceof TemplateTwinClinicalMutationAuthorizationError &&
      error.code === "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
  );
}

async function expectOrdinaryAuthorityDenied(
  input: Parameters<typeof ordinaryFence>[0],
): Promise<void> {
  await assert.rejects(
    ordinaryFence(input),
    (error: unknown) =>
      error instanceof TemplateTwinClinicalMutationAuthorizationError &&
      error.code === "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
  );
}

async function proveOrdinaryAndProviderFences(): Promise<void> {
  await ordinaryFence({ visitId: "visit-ordinary" });
  await ordinaryFence({
    visitId: "visit-template-ordinary",
    admittedPatientId: "patient-template",
    admittedNoteTemplateId: "template-ordinary",
  });
  await expectOrdinaryFenceDenied({
    visitId: "visit-kind-drift",
    admittedPatientId: "patient-template",
    admittedNoteTemplateId: "template-kind-drift",
  });

  for (const visitId of [
    "visit-fill",
    "visit-run",
    "visit-admission",
    "visit-execution",
  ]) {
    await expectOrdinaryFenceDenied({ visitId });
  }
  await expectOrdinaryFenceDenied({
    visitId: "visit-reserved",
    admittedPatientId: "patient-reserved",
  });
  await expectOrdinaryFenceDenied({
    visitId: "visit-missing-patient",
    admittedPatientId: "patient-missing",
  });
  await expectOrdinaryFenceDenied({
    visitId: "visit-null-patient",
    admittedPatientId: "patient-ordinary",
  });

  // Pre-egress failure means the synthetic provider body is never entered.
  let providerCalls = 0;
  await expectOrdinaryFenceDenied({ visitId: "visit-fill" });
  assert.equal(providerCalls, 0);

  // A durable execution arriving during egress is caught immediately on
  // provider return and again at the final transaction boundary.
  await ordinaryFence({ visitId: "visit-provider-window" });
  providerCalls += 1;
  await db.$executeRawUnsafe(`
    INSERT INTO "template_twin_provider_executions" VALUES
      ('provider-window-marker', 'visit-provider-window', '${practiceId}',
       '${actorId}', NULL, NULL, NULL, NULL, 'LIVE', NULL)
  `);
  // Immediate post-return fence.
  await expectOrdinaryFenceDenied({ visitId: "visit-provider-window" });
  // Independent final-write transaction fence.
  await expectOrdinaryFenceDenied({ visitId: "visit-provider-window" });
  assert.equal(providerCalls, 1);
  const providerWindow = await db.$queryRaw<Array<{ soapFinal: string }>>`
    SELECT "soapFinal" FROM "transcribe_visits"
    WHERE "id" = 'visit-provider-window'
  `;
  assert.equal(providerWindow[0]?.soapFinal, "provider-window-v1");
}

async function proveContentAndVersionDrift(): Promise<void> {
  await db.$executeRaw`
    UPDATE "transcribe_visits"
    SET "soapFinal" = 'drift-v2', "soapVersion" = 2,
        "updatedAt" = ${changedAt}
    WHERE "id" = 'visit-drift'
  `;
  await expectOrdinaryFenceDenied({ visitId: "visit-drift" });
  const staleEpochCas = await db.$executeRaw`
    UPDATE "transcribe_visits"
    SET "soapFinal" = 'must-not-land', "soapVersion" = 2
    WHERE "id" = 'visit-drift'
      AND "userId" = ${actorId}
      AND "updatedAt" = ${admittedAt}
      AND "soapFinal" = 'drift-v1'
      AND "soapVersion" = 1
  `;
  assert.equal(staleEpochCas, 0);

  // Even when a faulty concurrent writer preserves updatedAt, the ordinary
  // lineage fence may still pass, but the route's exact content/version CAS
  // must miss rather than overwrite that writer.
  await db.$executeRaw`
    UPDATE "transcribe_visits"
    SET "soapFinal" = 'drift-v3', "soapVersion" = 3,
        "updatedAt" = ${admittedAt}
    WHERE "id" = 'visit-drift'
  `;
  await ordinaryFence({ visitId: "visit-drift" });
  const exactContentCas = await db.$executeRaw`
    UPDATE "transcribe_visits"
    SET "soapFinal" = 'must-not-land', "soapVersion" = 2
    WHERE "id" = 'visit-drift'
      AND "userId" = ${actorId}
      AND "updatedAt" = ${admittedAt}
      AND "soapFinal" = 'drift-v1'
      AND "soapVersion" = 1
  `;
  assert.equal(exactContentCas, 0);
}

async function provePrePhiActorBinding(): Promise<void> {
  let phiProjectionCount = 0;

  await db.$executeRaw`
    UPDATE "transcribe_visits"
    SET "userId" = 'synthetic-reassigned-doctor'
    WHERE "id" = 'visit-live'
  `;

  try {
    await db.$transaction(async (tx: Prisma.TransactionClient) => {
      const locked = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        SELECT visit."id"
        FROM "transcribe_visits" visit
        WHERE visit."id" = 'visit-live'
          AND visit."userId" = ${actorId}
        FOR UPDATE
      `);

      assert.deepEqual(locked, []);
      if (locked.length !== 1) return;

      phiProjectionCount += 1;
      await tx.$queryRaw(Prisma.sql`
        SELECT visit."soapFinal"
        FROM "transcribe_visits" visit
        WHERE visit."id" = 'visit-live'
          AND visit."userId" = ${actorId}
      `);
    });
  } finally {
    await db.$executeRaw`
      UPDATE "transcribe_visits"
      SET "userId" = ${actorId}
      WHERE "id" = 'visit-live'
    `;
  }

  assert.equal(phiProjectionCount, 0);
  assert.equal(await liveMutationContractAllowed(), true);
}

async function proveCleanupExclusion(): Promise<void> {
  const serializedPredicate = JSON.stringify(
    TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
  );
  assert.match(serializedPredicate, /templateTwinCompiledVersion/);
  assert.match(serializedPredicate, /templateTwinProviderExecutions/);
  assert.match(serializedPredicate, /SYNTHETIC-QA-ONLY/);

  // SQL-equivalent execution of the exported Prisma relation predicate. Raw
  // SQL is intentional here: Prisma qualifies model tables as public, which
  // would bypass the connection-local temporary shadow schema.
  const rows = await db.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT visit."id"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."id" LIKE 'cleanup-%'
      AND (
        visit."noteTemplateId" IS NULL
        OR EXISTS (
          SELECT 1
          FROM "note_templates" template
          WHERE template."id" = visit."noteTemplateId"
            AND template."templateKind" <> 'template_twin_docx'
            AND NOT EXISTS (
              SELECT 1
              FROM "template_twin_compiled_versions" compiled
              WHERE compiled."noteTemplateId" = template."id"
            )
        )
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_fill_manifests" fill
        WHERE fill."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_synthetic_qa_runs" run
        WHERE run."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
        WHERE admission."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_provider_executions" execution
        WHERE execution."visitId" = visit."id"
      )
      AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
    ORDER BY visit."id" ASC
  `);
  assert.deepEqual(rows, [{ id: "cleanup-ordinary" }]);
}

async function assertCurrentPhysicianAllowed(): Promise<void> {
  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    const actor = await lockAndAssertCurrentTemplateTwinPhysician({
      tx,
      actor: { userId: actorId, practiceId },
    });
    assert.equal(actor.email, "synthetic-doctor@example.invalid");
  });
}

async function proveCurrentPhysicianRevocation(): Promise<void> {
  await assertCurrentPhysicianAllowed();

  await db.$executeRawUnsafe(
    `UPDATE "users" SET "role" = 'ADMIN' WHERE "id" = '${actorId}'`,
  );
  await assert.rejects(assertCurrentPhysicianAllowed());
  await db.$executeRawUnsafe(
    `UPDATE "users" SET "role" = 'DOCTOR' WHERE "id" = '${actorId}'`,
  );

  await db.$executeRawUnsafe(
    `UPDATE "users" SET "products" = ARRAY[]::public."Product"[] WHERE "id" = '${actorId}'`,
  );
  await assert.rejects(assertCurrentPhysicianAllowed());
  await db.$executeRawUnsafe(
    `UPDATE "users" SET "products" = ARRAY['TRANSCRIBE_MD']::public."Product"[] WHERE "id" = '${actorId}'`,
  );

  await db.$executeRawUnsafe(
    `UPDATE "users" SET "suspendedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
  );
  await assert.rejects(assertCurrentPhysicianAllowed());
  await db.$executeRawUnsafe(
    `UPDATE "users" SET "suspendedAt" = NULL WHERE "id" = '${actorId}'`,
  );

  await db.$transaction(async (tx: Prisma.TransactionClient) => {
    await assert.rejects(
      lockAndAssertCurrentTemplateTwinPhysician({
        tx,
        actor: { userId: actorId, practiceId: "synthetic-other-practice" },
      }),
    );
  });
  await assertCurrentPhysicianAllowed();
}

async function proveOrdinaryCurrentAuthorityRevocation(): Promise<void> {
  const mutateAndDeny = async (
    mutateSql: string,
    restoreSql: string,
  ): Promise<void> => {
    await db.$executeRawUnsafe(mutateSql);
    try {
      await expectOrdinaryAuthorityDenied({ visitId: "visit-ordinary" });
    } finally {
      await db.$executeRawUnsafe(restoreSql);
    }
    await ordinaryFence({ visitId: "visit-ordinary" });
  };

  await ordinaryFence({ visitId: "visit-ordinary" });
  await mutateAndDeny(
    `UPDATE "practices" SET "isActive" = FALSE WHERE "id" = '${practiceId}'`,
    `UPDATE "practices" SET "isActive" = TRUE WHERE "id" = '${practiceId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "role" = 'ADMIN' WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "role" = 'DOCTOR' WHERE "id" = '${actorId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "isActive" = FALSE WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "isActive" = TRUE WHERE "id" = '${actorId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "deactivatedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "deactivatedAt" = NULL WHERE "id" = '${actorId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "suspendedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "suspendedAt" = NULL WHERE "id" = '${actorId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "softDeletedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "softDeletedAt" = NULL WHERE "id" = '${actorId}'`,
  );
  await mutateAndDeny(
    `UPDATE "users" SET "products" = ARRAY[]::public."Product"[] WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "products" = ARRAY['TRANSCRIBE_MD']::public."Product"[] WHERE "id" = '${actorId}'`,
  );

  await db.$executeRawUnsafe(
    `UPDATE "users" SET "practiceId" = 'synthetic-mutation-other-practice' WHERE "id" = '${actorId}'`,
  );
  try {
    await expectOrdinaryFenceDenied({ visitId: "visit-ordinary" });
  } finally {
    await db.$executeRawUnsafe(
      `UPDATE "users" SET "practiceId" = '${practiceId}' WHERE "id" = '${actorId}'`,
    );
  }
  await ordinaryFence({ visitId: "visit-ordinary" });
}

/**
 * PostgreSQL mirror of the exact persisted live-lineage portion of the final
 * mutation claim. Runtime attestation/release ownership has its own dedicated
 * executable PG proof; this query covers the mutation-specific actor,
 * rollout, visit, patient, fill, and provider lineage joins in one snapshot.
 */
async function liveMutationContractAllowed(): Promise<boolean> {
  const rows = await db.$queryRaw<Array<{ allowed: boolean }>>(Prisma.sql`
    SELECT EXISTS (
      SELECT 1
      FROM "transcribe_visits" visit
      JOIN "transcribe_md_patients" patient
        ON patient."id" = visit."patientId"
      JOIN "practices" practice
        ON practice."id" = patient."practiceId"
      JOIN "users" actor
        ON actor."id" = visit."userId"
       AND actor."practiceId" = practice."id"
      JOIN "note_templates" template
        ON template."id" = visit."noteTemplateId"
      JOIN "template_twin_compiled_versions" compiled
        ON compiled."noteTemplateId" = template."id"
      JOIN "template_twin_source_artifacts" source
        ON source."id" = compiled."sourceArtifactId"
       AND source."practiceId" = practice."id"
      JOIN "template_twin_certifications" certification
        ON certification."compiledVersionId" = compiled."id"
      JOIN "template_twin_rollout_controls" rollout
        ON rollout."id" = 'global'
      LEFT JOIN "template_twin_fill_manifests" fill
        ON fill."visitId" = visit."id"
      WHERE visit."id" = 'visit-live'
        AND visit."userId" = ${actorId}
        AND visit."updatedAt" = ${admittedAt}
        AND visit."noteTemplateVersion" = 4
        AND actor."role" = 'DOCTOR'::public."UserRole"
        AND actor."isActive" = TRUE
        AND actor."deactivatedAt" IS NULL
        AND actor."suspendedAt" IS NULL
        AND actor."softDeletedAt" IS NULL
        AND 'TRANSCRIBE_MD'::public."Product" = ANY(actor."products")
        AND practice."id" = ${practiceId}
        AND practice."isActive" = TRUE
        AND practice."templateTwinEnabled" = TRUE
        AND practice."templateTwinRolloutGeneration" = 7
        AND rollout."enabled" = TRUE
        AND rollout."generation" = 11
        AND rollout."rollbackFenceState" = 'OPEN'
        AND template."doctorId" = actor."id"
        AND template."templateKind" = 'template_twin_docx'
        AND template."version" = visit."noteTemplateVersion"
        AND compiled."id" = 'compiled-live'
        AND compiled."certificationStatus" = 'CERTIFIED'
        AND source."id" = 'source-live'
        AND source."validationStatus" = 'accepted'
        AND certification."id" = 'cert-live'
        AND certification."certifiedById" = actor."id"
        AND certification."providerAuthorizationMode" = 'LIVE'
        AND certification."providerAuthorizationAdmissionId" IS NULL
        AND fill."id" = 'fill-live'
        AND fill."practiceId" = practice."id"
        AND fill."compiledVersionId" = compiled."id"
        AND fill."noteTemplateId" = template."id"
        AND fill."noteTemplateVersion" = template."version"
        AND NOT EXISTS (
          SELECT 1
          FROM "template_twin_provider_executions" execution
          WHERE execution."visitId" = visit."id"
            AND (
              execution."practiceId" IS DISTINCT FROM practice."id"
              OR execution."actorUserId" IS DISTINCT FROM actor."id"
              OR execution."sourceArtifactId" IS DISTINCT FROM source."id"
              OR execution."compiledVersionId" IS DISTINCT FROM compiled."id"
              OR execution."noteTemplateId" IS DISTINCT FROM template."id"
              OR execution."noteTemplateVersion" IS DISTINCT FROM template."version"
              OR execution."providerMode" IS DISTINCT FROM 'LIVE'
              OR execution."syntheticAdmissionId" IS NOT NULL
            )
        )
    ) AS "allowed"
  `);
  return rows.length === 1 && rows[0]?.allowed === true;
}

async function mutateAndRestore(
  mutateSql: string,
  restoreSql: string,
): Promise<void> {
  await db.$executeRawUnsafe(mutateSql);
  assert.equal(await liveMutationContractAllowed(), false);
  await db.$executeRawUnsafe(restoreSql);
  assert.equal(await liveMutationContractAllowed(), true);
}

async function proveLiveRevocationAndLineage(): Promise<void> {
  assert.equal(await liveMutationContractAllowed(), true);

  await mutateAndRestore(
    `UPDATE "note_templates" SET "templateKind" = 'structured' WHERE "id" = 'template-live'`,
    `UPDATE "note_templates" SET "templateKind" = 'template_twin_docx' WHERE "id" = 'template-live'`,
  );
  await mutateAndRestore(
    `UPDATE "users" SET "role" = 'ADMIN' WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "role" = 'DOCTOR' WHERE "id" = '${actorId}'`,
  );
  await mutateAndRestore(
    `UPDATE "users" SET "products" = ARRAY[]::public."Product"[] WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "products" = ARRAY['TRANSCRIBE_MD']::public."Product"[] WHERE "id" = '${actorId}'`,
  );
  await mutateAndRestore(
    `UPDATE "practices" SET "isActive" = FALSE WHERE "id" = '${practiceId}'`,
    `UPDATE "practices" SET "isActive" = TRUE WHERE "id" = '${practiceId}'`,
  );
  await mutateAndRestore(
    `UPDATE "practices" SET "templateTwinEnabled" = FALSE WHERE "id" = '${practiceId}'`,
    `UPDATE "practices" SET "templateTwinEnabled" = TRUE WHERE "id" = '${practiceId}'`,
  );
  await mutateAndRestore(
    `UPDATE "template_twin_rollout_controls" SET "enabled" = FALSE WHERE "id" = 'global'`,
    `UPDATE "template_twin_rollout_controls" SET "enabled" = TRUE WHERE "id" = 'global'`,
  );
  await mutateAndRestore(
    `UPDATE "template_twin_rollout_controls" SET "generation" = 12 WHERE "id" = 'global'`,
    `UPDATE "template_twin_rollout_controls" SET "generation" = 11 WHERE "id" = 'global'`,
  );
  await mutateAndRestore(
    `UPDATE "practices" SET "templateTwinRolloutGeneration" = 8 WHERE "id" = '${practiceId}'`,
    `UPDATE "practices" SET "templateTwinRolloutGeneration" = 7 WHERE "id" = '${practiceId}'`,
  );
  await mutateAndRestore(
    `UPDATE "template_twin_fill_manifests" SET "compiledVersionId" = 'compiled-other' WHERE "id" = 'fill-live'`,
    `UPDATE "template_twin_fill_manifests" SET "compiledVersionId" = 'compiled-live' WHERE "id" = 'fill-live'`,
  );
  await mutateAndRestore(
    `UPDATE "template_twin_provider_executions" SET "compiledVersionId" = 'compiled-other' WHERE "id" = 'execution-live'`,
    `UPDATE "template_twin_provider_executions" SET "compiledVersionId" = 'compiled-live' WHERE "id" = 'execution-live'`,
  );
  await mutateAndRestore(
    `UPDATE "template_twin_provider_executions" SET "sourceArtifactId" = 'source-other' WHERE "id" = 'execution-live'`,
    `UPDATE "template_twin_provider_executions" SET "sourceArtifactId" = 'source-live' WHERE "id" = 'execution-live'`,
  );
}

async function proveAuditOutboxRollback(): Promise<void> {
  await db.$executeRawUnsafe(`
    CREATE OR REPLACE FUNCTION pg_temp.reject_synthetic_outbox_insert()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $body$
    BEGIN
      RAISE EXCEPTION 'synthetic outbox unavailable';
    END;
    $body$;
    CREATE TRIGGER reject_synthetic_outbox_insert
      BEFORE INSERT ON "template_twin_audit_outbox"
      FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_synthetic_outbox_insert();
  `);

  await assert.rejects(
    db.$transaction(async (tx: Prisma.TransactionClient) => {
      const updated = await tx.$executeRaw`
        UPDATE "transcribe_visits"
        SET "soapFinal" = 'audit-must-roll-back', "soapVersion" = 2
        WHERE "id" = 'visit-audit-rollback'
          AND "soapFinal" = 'audit-before'
          AND "soapVersion" = 1
      `;
      assert.equal(updated, 1);
      await enqueueTemplateTwinVisitMutationAudit({
        tx,
        practiceId,
        actorUserId: actorId,
        visitId: "visit-audit-rollback",
        operation: "soap_save",
        action: "EDITED_NOTE",
        admittedVisitUpdatedAtEpochMs: admittedAt.getTime(),
        noteTemplateId: null,
        noteTemplateVersion: null,
      });
    }),
  );

  const visits = await db.$queryRaw<
    Array<{ soapFinal: string; soapVersion: number }>
  >`
    SELECT "soapFinal", "soapVersion"
    FROM "transcribe_visits"
    WHERE "id" = 'visit-audit-rollback'
  `;
  assert.deepEqual(visits, [{ soapFinal: "audit-before", soapVersion: 1 }]);
  const outboxCount = await db.$queryRaw<Array<{ count: bigint }>>`
    SELECT COUNT(*)::bigint AS "count" FROM "template_twin_audit_outbox"
  `;
  assert.equal(outboxCount[0]?.count, 0n);
}

async function main(): Promise<void> {
  try {
    await setupShadowSchema();
    await proveOrdinaryAndProviderFences();
    await proveContentAndVersionDrift();
    await provePrePhiActorBinding();
    await proveCleanupExclusion();
    await proveCurrentPhysicianRevocation();
    await proveOrdinaryCurrentAuthorityRevocation();
    await proveLiveRevocationAndLineage();
    await proveAuditOutboxRollback();
    console.log(
      "template-twin mutation authority PostgreSQL proof: PASS (synthetic only)",
    );
  } finally {
    await db.$disconnect();
  }
}

void main().catch((error: unknown) => {
  console.error(
    error instanceof Error ? error.message : "Mutation-authority proof failed.",
  );
  process.exitCode = 1;
});
