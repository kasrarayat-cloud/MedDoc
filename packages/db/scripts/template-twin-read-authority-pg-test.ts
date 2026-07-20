#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the generic Template Twin read boundary.
// Synthetic identifiers only; no provider, storage, or production service is
// contacted. The target must be a disposable database; temporary shadow
// tables keep the proof isolated from any migrated public data.

import assert from "node:assert/strict";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import {
  aggregateTemplateTwinVisibleVisits,
  inspectTemplateTwinVisitReads,
  listTemplateTwinVisibleVisitIdentities,
  listTemplateTwinVisibleVisitPage,
  templateTwinVisitReadVisibilitySql,
} from "../../../apps/transcribe-md/src/lib/template-twin/read-authority";
import { claimCurrentOrdinaryVisitDeliveryActor } from "../../../apps/transcribe-md/src/lib/clinical-visit-authority";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_READ_AUTHORITY_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable read-authority test URL is required.");
}
assertNonProdDatabase(databaseUrl);

const db = new PrismaClient({
  adapter: new PrismaPg({ connectionString: databaseUrl, max: 1 }),
});

const actorId = "synthetic-read-doctor";
const otherActorId = "synthetic-read-other-doctor";
const practiceId = "synthetic-read-practice";
const otherPracticeId = "synthetic-read-other-practice";

async function setupShadowSchema(): Promise<void> {
  // The production SQL uses explicit enum casts. A blank disposable database
  // receives only those two type definitions; an already-migrated disposable
  // database keeps its canonical definitions.
  await db.$executeRawUnsafe(`
    DO $types$
    BEGIN
      IF to_regtype('public."UserRole"') IS NULL THEN
        CREATE TYPE public."UserRole" AS ENUM
          ('DOCTOR', 'ADMIN', 'SUPER_ADMIN', 'STAFF');
      END IF;
      IF to_regtype('public."Product"') IS NULL THEN
        CREATE TYPE public."Product" AS ENUM
          ('MEDDOC_PRO', 'TRANSCRIBE_MD');
      END IF;
    END;
    $types$;
  `);
  await db.$executeRawUnsafe(`
    CREATE TEMP TABLE "practices" (
      "id" TEXT PRIMARY KEY,
      "isActive" BOOLEAN NOT NULL,
      "templateTwinEnabled" BOOLEAN NOT NULL
    );
    CREATE TEMP TABLE "users" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT,
      "email" TEXT NOT NULL,
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
      "externalId" TEXT
    );
    CREATE TEMP TABLE "note_templates" (
      "id" TEXT PRIMARY KEY,
      "doctorId" TEXT,
      "templateKind" TEXT NOT NULL,
      "version" INTEGER NOT NULL
    );
    CREATE TEMP TABLE "transcribe_visits" (
      "id" TEXT PRIMARY KEY,
      "userId" TEXT NOT NULL,
      "patientId" TEXT NOT NULL,
      "noteTemplateId" TEXT,
      "noteTemplateVersion" INTEGER,
      "createdAt" TIMESTAMPTZ NOT NULL,
      "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      "deletedAt" TIMESTAMPTZ,
      "archivedAt" TIMESTAMPTZ,
      "status" TEXT NOT NULL DEFAULT 'READY',
      "needsReview" BOOLEAN NOT NULL DEFAULT FALSE,
      "signedAt" TIMESTAMPTZ,
      "draftedInSeconds" INTEGER,
      "patientName" TEXT,
      "chiefComplaint" TEXT
    );
    CREATE TEMP TABLE "template_twin_source_artifacts" (
      "id" TEXT PRIMARY KEY,
      "practiceId" TEXT NOT NULL
    );
    CREATE TEMP TABLE "template_twin_compiled_versions" (
      "id" TEXT PRIMARY KEY,
      "sourceArtifactId" TEXT NOT NULL,
      "noteTemplateId" TEXT NOT NULL
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
      "visitId" TEXT NOT NULL,
      "practiceId" TEXT NOT NULL,
      "doctorId" TEXT NOT NULL,
      "noteTemplateId" TEXT NOT NULL,
      "noteTemplateVersion" INTEGER NOT NULL,
      "admissionId" TEXT
    );
    CREATE TEMP TABLE "template_twin_synthetic_qa_admissions" (
      "id" TEXT PRIMARY KEY,
      "parentAdmissionId" TEXT,
      "visitId" TEXT,
      "practiceId" TEXT NOT NULL,
      "actorId" TEXT NOT NULL,
      "noteTemplateId" TEXT,
      "noteTemplateVersion" INTEGER,
      "purpose" TEXT NOT NULL,
      "preCertificationVoiceEvidence" BOOLEAN NOT NULL
    );
    CREATE TEMP TABLE "template_twin_provider_executions" (
      "id" TEXT PRIMARY KEY,
      "visitId" TEXT,
      "practiceId" TEXT NOT NULL,
      "actorUserId" TEXT NOT NULL,
      "providerMode" TEXT NOT NULL,
      "syntheticAdmissionId" TEXT,
      "noteTemplateId" TEXT,
      "noteTemplateVersion" INTEGER,
      "compiledVersionId" TEXT,
      "sourceArtifactId" TEXT
    );
  `);

  await db.$executeRawUnsafe(`
    INSERT INTO "practices" VALUES
      ('${practiceId}', TRUE, FALSE),
      ('${otherPracticeId}', TRUE, TRUE);
    INSERT INTO "users" VALUES
      ('${actorId}', '${practiceId}', 'synthetic-physician@example.test',
       'DOCTOR', TRUE, NULL, NULL, NULL,
       ARRAY['TRANSCRIBE_MD']::public."Product"[]),
      ('${otherActorId}', '${practiceId}', 'synthetic-other-physician@example.test',
       'DOCTOR', TRUE, NULL, NULL, NULL,
       ARRAY['TRANSCRIBE_MD']::public."Product"[]);
    INSERT INTO "transcribe_md_patients" VALUES
      ('patient-live', '${practiceId}', NULL),
      ('patient-ordinary', '${practiceId}', NULL),
      ('patient-kind-drift', '${practiceId}', NULL),
      ('patient-detached', '${practiceId}', NULL),
      ('patient-mode-mismatch', '${practiceId}', NULL),
      ('patient-precert', '${practiceId}', 'SYNTHETIC-QA-ONLY'),
      ('patient-reserved-orphan', '${practiceId}', 'SYNTHETIC-QA-ONLY');
    INSERT INTO "note_templates" VALUES
      ('template-live', '${actorId}', 'template_twin_docx', 3),
      ('template-kind-drift', '${actorId}', 'structured', 1),
      ('template-precert', '${actorId}', 'template_twin_docx', 1);
    INSERT INTO "template_twin_source_artifacts" VALUES
      ('source-live', '${practiceId}'),
      ('source-kind-drift', '${practiceId}'),
      ('source-precert', '${practiceId}');
    INSERT INTO "template_twin_compiled_versions" VALUES
      ('compiled-live', 'source-live', 'template-live'),
      ('compiled-kind-drift', 'source-kind-drift', 'template-kind-drift'),
      ('compiled-precert', 'source-precert', 'template-precert');
    INSERT INTO "transcribe_visits" (
      "id", "userId", "patientId", "noteTemplateId",
      "noteTemplateVersion", "createdAt", "deletedAt", "archivedAt"
    ) VALUES
      ('visit-ordinary', '${actorId}', 'patient-ordinary', NULL, NULL,
       '2026-01-01T00:00:00Z', NULL, NULL),
      ('visit-ordinary-other-physician', '${otherActorId}', 'patient-ordinary',
       NULL, NULL, '2026-01-01T12:00:00Z', NULL, NULL),
      ('visit-live', '${actorId}', 'patient-live', 'template-live', 3,
       '2026-01-02T00:00:00Z', NULL, NULL),
      ('visit-kind-drift', '${actorId}', 'patient-kind-drift',
       'template-kind-drift', 1, '2026-01-02T12:00:00Z', NULL, NULL),
      ('visit-detached', '${actorId}', 'patient-detached', NULL, NULL,
       '2026-01-03T00:00:00Z', NULL, NULL),
      ('visit-mode-mismatch', '${actorId}', 'patient-mode-mismatch',
       'template-live', 3, '2026-01-03T12:00:00Z', NULL, NULL),
      ('visit-precert', '${actorId}', 'patient-precert', 'template-precert', 1,
       '2026-01-04T00:00:00Z', NULL, NULL),
      ('visit-reserved-orphan', '${actorId}', 'patient-reserved-orphan',
       NULL, NULL, '2026-01-05T00:00:00Z', NULL, NULL),
      ('visit-missing-patient', '${actorId}', 'patient-does-not-exist',
       NULL, NULL, '2026-01-06T00:00:00Z', NULL, NULL);
    INSERT INTO "template_twin_fill_manifests" VALUES
      ('fill-live', 'visit-live', '${practiceId}', 'compiled-live',
       'template-live', 3);
    INSERT INTO "template_twin_provider_executions" VALUES
      ('execution-live', 'visit-live', '${practiceId}', '${actorId}', 'LIVE',
       NULL, 'template-live', 3, 'compiled-live', 'source-live'),
      ('execution-detached', 'visit-detached', '${otherPracticeId}',
       '${actorId}', 'LIVE', NULL, NULL, NULL, NULL, NULL),
      ('execution-mode-mismatch', 'visit-mode-mismatch', '${practiceId}',
       '${actorId}', 'SYNTHETIC_QA', NULL, 'template-live', 3,
       'compiled-live', 'source-live');
    INSERT INTO "template_twin_synthetic_qa_admissions" VALUES
      ('admission-upload', NULL, NULL, '${practiceId}', '${actorId}',
       'template-precert', 1, 'UPLOAD', FALSE),
      ('admission-precert', 'admission-upload', 'visit-precert', '${practiceId}',
       '${actorId}', 'template-precert', 1, 'VISIT', TRUE);
  `);
}

async function visibleIds(): Promise<string[]> {
  const rows = await listTemplateTwinVisibleVisitIdentities({
    db,
    actorUserId: actorId,
  });
  return rows.map((row) => row.id);
}

async function sharedPatientVisibleIds(): Promise<string[]> {
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: actorId,
    visitAlias: "v",
  });
  const rows = await db.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT v."id"
    FROM "transcribe_visits" v
    WHERE v."patientId" = 'patient-ordinary'
      AND ${visibility}
    ORDER BY v."id"
  `);
  return rows.map((row) => row.id);
}

async function main(): Promise<void> {
  await setupShadowSchema();

  assert.deepEqual(
    await claimCurrentOrdinaryVisitDeliveryActor(
      { visitId: "visit-ordinary", actorUserId: actorId },
      db,
    ),
    {
      id: actorId,
      practiceId,
      email: "synthetic-physician@example.test",
    },
    "ordinary provider/delivery claim must return only the exact current actor",
  );
  await db.$executeRawUnsafe(`
    UPDATE "users" SET "suspendedAt" = clock_timestamp()
    WHERE "id" = '${actorId}'
  `);
  assert.equal(
    await claimCurrentOrdinaryVisitDeliveryActor(
      { visitId: "visit-ordinary", actorUserId: actorId },
      db,
    ),
    null,
    "ordinary provider/delivery claim must fail after actor suspension",
  );
  await db.$executeRawUnsafe(`
    UPDATE "users" SET "suspendedAt" = NULL WHERE "id" = '${actorId}';
    INSERT INTO "template_twin_provider_executions" VALUES
      ('execution-ordinary-drift', 'visit-ordinary', '${practiceId}',
       '${actorId}', 'LIVE', NULL, NULL, NULL, NULL, NULL)
  `);
  assert.equal(
    await claimCurrentOrdinaryVisitDeliveryActor(
      { visitId: "visit-ordinary", actorUserId: actorId },
      db,
    ),
    null,
    "ordinary claim must fail closed if Template Twin provider provenance appears",
  );
  await db.$executeRawUnsafe(`
    DELETE FROM "template_twin_provider_executions"
    WHERE "id" = 'execution-ordinary-drift'
  `);

  const initial = await inspectTemplateTwinVisitReads({
    db,
    actorUserId: actorId,
    visitIds: [
      "visit-ordinary",
      "visit-live",
      "visit-kind-drift",
      "visit-detached",
      "visit-mode-mismatch",
      "visit-precert",
      "visit-reserved-orphan",
      "visit-missing-patient",
    ],
  });
  assert.deepEqual(
    initial.map((row) => row.visitId).sort(),
    ["visit-live", "visit-ordinary"],
    "live owner and ordinary rows must pass; detached/pre-cert/reserved-orphan/missing-patient rows must fail",
  );
  assert.equal(
    initial.find((row) => row.visitId === "visit-live")?.templateTwinEnabled,
    false,
    "base clinical read must survive rollout revocation",
  );
  assert.deepEqual(
    initial.find((row) => row.visitId === "visit-ordinary"),
    {
      visitId: "visit-ordinary",
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    },
    "an ordinary visit with null template and null patient external id must remain readable",
  );
  assert.deepEqual(await visibleIds(), ["visit-ordinary", "visit-live"]);
  assert.deepEqual(
    await sharedPatientVisibleIds(),
    ["visit-ordinary"],
    "practice-shared patient rollups must never reveal another physician's ordinary visit",
  );

  assert.deepEqual(
    await inspectTemplateTwinVisitReads({
      db,
      actorUserId: actorId,
      visitIds: ["visit-kind-drift"],
    }),
    [],
    "compiled-version provenance must keep a templateKind-drifted visit out of the ordinary single-read path",
  );
  assert.deepEqual(
    await listTemplateTwinVisibleVisitIdentities({
      db,
      actorUserId: actorId,
      patientId: "patient-kind-drift",
    }),
    [],
    "export census must exclude templateKind drift when compiled provenance remains",
  );
  assert.deepEqual(
    await listTemplateTwinVisibleVisitPage({
      db,
      actorUserId: actorId,
      query: {
        scope: { patientId: "patient-kind-drift" },
        take: 10,
      },
    }),
    [],
    "exact list pagination must exclude templateKind drift when compiled provenance remains",
  );
  assert.equal(
    (
      await aggregateTemplateTwinVisibleVisits({
        db,
        actorUserId: actorId,
        scope: { patientId: "patient-kind-drift" },
      })
    ).count,
    0,
    "aggregate reads must exclude templateKind drift when compiled provenance remains",
  );
  assert.equal(
    (
      await aggregateTemplateTwinVisibleVisits({
        db,
        actorUserId: actorId,
        scope: { patientId: "patient-detached" },
      })
    ).count,
    0,
    "foreign-practice durable Twin provenance must not contribute patient-derived metadata",
  );

  // Exact count/order semantics are evaluated in the same PostgreSQL query,
  // not by filtering a wider page after LIMIT/cursor calculation.
  const active = await listTemplateTwinVisibleVisitIdentities({
    db,
    actorUserId: actorId,
    patientId: "patient-live",
    activeOnly: true,
  });
  assert.deepEqual(
    active.map((row) => row.id),
    ["visit-live"],
  );

  const orphanDecision = await inspectTemplateTwinVisitReads({
    db,
    actorUserId: actorId,
    visitIds: ["visit-reserved-orphan"],
  });
  assert.deepEqual(
    orphanDecision,
    [],
    "reserved synthetic patient identity must stay restricted after every auxiliary row is orphaned",
  );

  for (const mutation of [
    `UPDATE "users" SET "isActive" = FALSE WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "deactivatedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "suspendedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "softDeletedAt" = clock_timestamp() WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "role" = 'ADMIN' WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "products" = ARRAY[]::public."Product"[] WHERE "id" = '${actorId}'`,
    `UPDATE "users" SET "practiceId" = '${otherPracticeId}' WHERE "id" = '${actorId}'`,
    `UPDATE "practices" SET "isActive" = FALSE WHERE "id" = '${practiceId}'`,
  ]) {
    await db.$executeRawUnsafe(mutation);
    const decisions = await inspectTemplateTwinVisitReads({
      db,
      actorUserId: actorId,
      visitIds: ["visit-ordinary", "visit-live"],
    });
    assert.deepEqual(
      decisions.map((row) => row.visitId),
      [],
      "role/product/practice revocation must hide both ordinary and Twin clinical reads",
    );
    assert.deepEqual(
      await visibleIds(),
      [],
      "current physician/practice revocation must hide every visit from list and export census",
    );
    assert.deepEqual(
      await sharedPatientVisibleIds(),
      [],
      "revocation must not fall through to another physician's shared-patient visit",
    );
    assert.equal(
      (
        await aggregateTemplateTwinVisibleVisits({
          db,
          actorUserId: actorId,
        })
      ).count,
      0,
      "current physician/practice revocation must hide every patient-derived aggregate",
    );
    await db.$executeRawUnsafe(`
      UPDATE "users" SET "practiceId" = '${practiceId}', "role" = 'DOCTOR',
        "isActive" = TRUE, "deactivatedAt" = NULL, "suspendedAt" = NULL,
        "softDeletedAt" = NULL,
        "products" = ARRAY['TRANSCRIBE_MD']::public."Product"[]
      WHERE "id" = '${actorId}';
      UPDATE "practices" SET "isActive" = TRUE WHERE "id" = '${practiceId}';
    `);
  }

  await db.$executeRawUnsafe(`
    INSERT INTO "template_twin_compiled_versions"
      ("id", "sourceArtifactId", "noteTemplateId")
    VALUES ('compiled-live-unrelated', 'source-precert', 'template-live')
  `);
  assert.deepEqual(
    (await visibleIds()).sort(),
    ["visit-ordinary"],
    "multiple compiled rows for one template must fail closed instead of matching an unrelated row",
  );
  await db.$executeRawUnsafe(`
    DELETE FROM "template_twin_compiled_versions"
    WHERE "id" = 'compiled-live-unrelated'
  `);

  await db.$executeRawUnsafe(`
    UPDATE "template_twin_fill_manifests"
    SET "compiledVersionId" = 'compiled-precert'
    WHERE "id" = 'fill-live'
  `);
  assert.deepEqual(
    (await visibleIds()).sort(),
    ["visit-ordinary"],
    "inconsistent fill/compiled lineage must fail closed",
  );
  await db.$executeRawUnsafe(`
    UPDATE "template_twin_fill_manifests"
    SET "compiledVersionId" = 'compiled-live'
    WHERE "id" = 'fill-live';
    UPDATE "template_twin_source_artifacts"
    SET "practiceId" = '${otherPracticeId}'
    WHERE "id" = 'source-live';
  `);
  assert.deepEqual(
    (await visibleIds()).sort(),
    ["visit-ordinary"],
    "detached source tenant must fail closed",
  );
  await db.$executeRawUnsafe(`
    UPDATE "template_twin_source_artifacts"
    SET "practiceId" = '${practiceId}'
    WHERE "id" = 'source-live';
    UPDATE "template_twin_provider_executions"
    SET "compiledVersionId" = 'compiled-precert'
    WHERE "id" = 'execution-live';
  `);
  assert.deepEqual(
    (await visibleIds()).sort(),
    ["visit-ordinary"],
    "execution/compiled mismatch must fail closed",
  );
  await db.$executeRawUnsafe(`
    UPDATE "template_twin_provider_executions"
    SET "compiledVersionId" = 'compiled-live',
        "sourceArtifactId" = 'source-precert'
    WHERE "id" = 'execution-live';
  `);
  assert.deepEqual(
    (await visibleIds()).sort(),
    ["visit-ordinary"],
    "execution/source mismatch must fail closed",
  );
  await db.$executeRawUnsafe(`
    UPDATE "template_twin_provider_executions"
    SET "sourceArtifactId" = 'source-live'
    WHERE "id" = 'execution-live';
  `);

  const bulkRows = Array.from({ length: 130 }, (_, index) => {
    const suffix = index.toString().padStart(3, "0");
    return Prisma.sql`(
      ${`visit-scale-${suffix}`}, ${actorId}, 'patient-live',
      'template-live', 3,
      ${new Date(Date.UTC(2026, 1, 1, 0, index))}, NULL, NULL
    )`;
  });
  await db.$executeRaw(Prisma.sql`
    INSERT INTO "transcribe_visits" (
      "id", "userId", "patientId", "noteTemplateId",
      "noteTemplateVersion", "createdAt", "deletedAt", "archivedAt"
    ) VALUES ${Prisma.join(bulkRows)}
  `);
  const scaled = await listTemplateTwinVisibleVisitIdentities({
    db,
    actorUserId: actorId,
  });
  assert.equal(
    scaled.filter((row) => row.id.startsWith("visit-scale-")).length,
    130,
    "query-native identity census must not truncate at the old 128-visit ceiling",
  );
  assert.deepEqual(
    scaled
      .filter((row) => row.id.startsWith("visit-scale-"))
      .slice(0, 3)
      .map((row) => row.id),
    ["visit-scale-000", "visit-scale-001", "visit-scale-002"],
    "query-native ordering must remain stable beyond 128 Twin rows",
  );

  const scaledAggregate = await aggregateTemplateTwinVisibleVisits({
    db,
    actorUserId: actorId,
    scope: { deleted: "active", archived: "active" },
  });
  assert.equal(
    scaledAggregate.count,
    132,
    "exact caller count must include all authorized rows beyond the old ceiling",
  );

  const scaledPage = await listTemplateTwinVisibleVisitPage({
    db,
    actorUserId: actorId,
    query: {
      scope: { deleted: "active", archived: "active" },
      orderBy: "createdAt",
      direction: "asc",
      take: 256,
    },
  });
  assert.equal(
    scaledPage.length,
    132,
    "exact bounded caller page must be evaluated before LIMIT",
  );
  assert.deepEqual(
    scaledPage.slice(0, 3).map((row) => row.id),
    ["visit-ordinary", "visit-live", "visit-scale-000"],
    "exact caller order must exclude denied rows before pagination",
  );

  const afterLive = await listTemplateTwinVisibleVisitPage({
    db,
    actorUserId: actorId,
    query: {
      scope: { deleted: "active", archived: "active" },
      orderBy: "createdAt",
      direction: "asc",
      cursor: {
        value: new Date("2026-01-02T00:00:00Z"),
        id: "visit-live",
      },
      take: 3,
    },
  });
  assert.deepEqual(
    afterLive.map((row) => row.id),
    ["visit-scale-000", "visit-scale-001", "visit-scale-002"],
    "exact caller cursor must advance across authorized rows only",
  );

  process.stdout.write(
    JSON.stringify({
      verdict: "PASS",
      fixtures: "synthetic-only",
      actorBoundClinicalReads: true,
      sharedPatientCrossPhysicianIsolation: true,
      lifecycleRoleProductPracticeRevocation: true,
      durableLineageFailClosed: true,
      exactPaginationAndAggregates: true,
    }) + "\n",
  );
}

main()
  .catch((error) => {
    process.stderr.write(
      `${error instanceof Error ? error.message : "Read-authority PostgreSQL proof failed."}\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => {
    await db.$disconnect();
  });
