import prisma from "@meddoc/db";
import { Client } from "pg";

import {
  cancelPreparedTemplateTwinRollback,
  inspectTemplateTwinRollback,
  prepareTemplateTwinRollback,
  revokeTemplateTwinRollout,
} from "../../../apps/transcribe-md/src/lib/template-twin/rollback-control";
import { drainTemplateTwinAuditOutbox } from "../../../apps/transcribe-md/src/lib/template-twin/audit-outbox";
import { lockTemplateTwinRolloutForFinalClaim } from "../../../apps/transcribe-md/src/lib/template-twin/rollout";

const PRACTICE_ID = "synthetic-rollback-fence-practice";
const OTHER_PRACTICE_ID = "synthetic-rollback-fence-other-practice";
const ACTOR_ID = "synthetic-rollback-fence-admin";
const PHYSICIAN_ID = "synthetic-rollback-fence-physician";
const RACE_PHYSICIAN_ID = "synthetic-rollback-fence-race-physician";
const SAME_PRACTICE_PHYSICIAN_ID =
  "synthetic-rollback-fence-same-practice-physician";
const OTHER_PRACTICE_PHYSICIAN_ID =
  "synthetic-rollback-fence-other-practice-physician";
const ORDINARY_TEMPLATE_ID = "synthetic-ordinary-template";
const INACTIVE_TWIN_TEMPLATE_ID = "synthetic-inactive-twin-template";
const TWIN_SOURCE_ID = "synthetic-rollback-fence-twin-source";
const TWIN_COMPILED_ID = "synthetic-rollback-fence-twin-compiled";
const TWIN_FILL_ID = "synthetic-rollback-fence-twin-fill";
const PATIENT_ID = "synthetic-rollback-fence-patient";
const VISIT_ID = "synthetic-rollback-fence-visit";
const TWIN_VISIT_ID = "synthetic-rollback-fence-twin-visit";
const SIGNED_TWIN_VISIT_ID = "synthetic-rollback-fence-signed-twin-visit";
const SIGNED_TWIN_FILL_ID = "synthetic-rollback-fence-signed-twin-fill";
const RACE_TWIN_VISIT_ID = "synthetic-rollback-fence-race-twin-visit";
const RACE_TWIN_FILL_ID = "synthetic-rollback-fence-race-twin-fill";
const SYNTHETIC_SHA256 = "a".repeat(64);
const PREPARE_CANCEL_ID = "573250ae-77b6-4dc7-920d-82f82ac8887c";
const REVOKE_ID = "bd5c7de8-3490-4aee-a16e-3bb74e3dd072";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertDisposableDatabase(): void {
  const raw = process.env.DATABASE_URL;
  if (!raw)
    throw new Error("DATABASE_URL is required for the disposable test.");
  const database = new URL(raw).pathname.replace(/^\//u, "");
  if (!/(?:test|qa|synthetic|rollback)/iu.test(database)) {
    throw new Error(
      "Rollback-fence PostgreSQL proof requires a disposable database name.",
    );
  }
}

async function expectDatabaseRejection(
  operation: () => Promise<unknown>,
  expectedMessage: string,
): Promise<void> {
  let rejection: unknown;
  const originalConsoleError = console.error;
  console.error = () => undefined;
  try {
    await operation();
  } catch (error) {
    rejection = error;
  } finally {
    console.error = originalConsoleError;
  }
  assert(
    rejection instanceof Error && rejection.message.includes(expectedMessage),
    `A rollback-integrity probe did not fail with the expected database guard: ${expectedMessage}`,
  );
}

async function expectAnyDatabaseRejection(
  operation: () => Promise<unknown>,
  description: string,
): Promise<void> {
  let rejection: unknown;
  const originalConsoleError = console.error;
  console.error = () => undefined;
  try {
    await operation();
  } catch (error) {
    rejection = error;
  } finally {
    console.error = originalConsoleError;
  }
  assert(
    rejection instanceof Error,
    `A rollback-integrity probe unexpectedly succeeded: ${description}`,
  );
}

async function waitForAdvisoryWaiter(
  observer: Client,
  blockedClient: Client,
  description: string,
): Promise<void> {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const result = await observer.query<{ waiting: boolean }>(
      `SELECT EXISTS (
         SELECT 1 FROM pg_locks
         WHERE pid = $1 AND locktype = 'advisory' AND NOT granted
       ) AS waiting`,
      [blockedClient.processID],
    );
    if (result.rows[0]?.waiting) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`Timed out waiting for ${description}.`);
}

async function insertRaceFill(client: Client): Promise<void> {
  await client.query(
    `INSERT INTO "template_twin_fill_manifests" (
       "id", "practiceId", "visitId", "compiledVersionId",
       "noteTemplateId", "noteTemplateVersion", "compilerVersion",
       "resolverVersion", "rendererVersion", "status", "fillManifest",
       "manifestSha256", "factSetSha256", "validationResult",
       "createdAt", "updatedAt"
     ) VALUES (
       $1, $2, $3, $4, $5, 1, 'synthetic-compiler-v1',
       'synthetic-resolver-v1', 'synthetic-renderer-v1', 'FAILED',
       '{"synthetic":true}'::jsonb, $6, $6,
       '{"synthetic":true}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
     )`,
    [
      RACE_TWIN_FILL_ID,
      PRACTICE_ID,
      RACE_TWIN_VISIT_ID,
      TWIN_COMPILED_ID,
      INACTIVE_TWIN_TEMPLATE_ID,
      SYNTHETIC_SHA256,
    ],
  );
}

async function main(): Promise<void> {
  assertDisposableDatabase();
  const existing = await prisma.$queryRaw<Array<{ count: bigint }>>`
    SELECT COUNT(*)::bigint AS "count"
    FROM "template_twin_rollback_operations"
  `;
  assert(
    existing[0]?.count === BigInt(0),
    "Disposable rollback table is not empty.",
  );

  await prisma.$transaction(async (tx: typeof prisma) => {
    await tx.$executeRaw`
      INSERT INTO "practices" (
        "id", "name", "slug", "templateTwinEnabled",
        "templateTwinRolloutGeneration", "createdAt", "updatedAt"
      ) VALUES (
        ${PRACTICE_ID}, 'Synthetic Rollback Fence Practice',
        'synthetic-rollback-fence-practice', true, 7,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "practices" (
        "id", "name", "slug", "templateTwinEnabled",
        "templateTwinRolloutGeneration", "createdAt", "updatedAt"
      ) VALUES (
        ${OTHER_PRACTICE_ID}, 'Synthetic Other Practice',
        'synthetic-rollback-fence-other-practice', false, 1,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "users" (
        "id", "email", "name", "passwordHash", "role", "isActive",
        "practiceId", "products", "createdAt", "updatedAt"
      ) VALUES (
        ${ACTOR_ID}, 'rollback-fence-admin@synthetic.test',
        'Synthetic Rollback Operator', 'INVALID_SYNTHETIC_PASSWORD_HASH',
        'ADMIN', true, ${PRACTICE_ID},
        ARRAY['TRANSCRIBE_MD', 'SUPER_ADMIN']::"Product"[],
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "users" (
        "id", "email", "name", "passwordHash", "role", "isActive",
        "practiceId", "products", "createdAt", "updatedAt"
      ) VALUES
        (${PHYSICIAN_ID}, 'rollback-physician@synthetic.test',
         'Synthetic Rollback Physician', 'INVALID_SYNTHETIC_PASSWORD_HASH',
         'DOCTOR', true, ${PRACTICE_ID}, ARRAY['TRANSCRIBE_MD']::"Product"[],
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        (${RACE_PHYSICIAN_ID}, 'rollback-race@synthetic.test',
         'Synthetic Rollback Race Physician', 'INVALID_SYNTHETIC_PASSWORD_HASH',
         'DOCTOR', true, ${PRACTICE_ID}, ARRAY['TRANSCRIBE_MD']::"Product"[],
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        (${SAME_PRACTICE_PHYSICIAN_ID}, 'rollback-peer@synthetic.test',
         'Synthetic Same Practice Physician', 'INVALID_SYNTHETIC_PASSWORD_HASH',
         'DOCTOR', true, ${PRACTICE_ID}, ARRAY['TRANSCRIBE_MD']::"Product"[],
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        (${OTHER_PRACTICE_PHYSICIAN_ID}, 'rollback-other@synthetic.test',
         'Synthetic Other Practice Physician', 'INVALID_SYNTHETIC_PASSWORD_HASH',
         'DOCTOR', true, ${OTHER_PRACTICE_ID}, ARRAY['TRANSCRIBE_MD']::"Product"[],
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    `;
    await tx.$executeRaw`
      INSERT INTO "note_templates" (
        "id", "doctorId", "name", "sections", "version",
        "versionDescription", "status", "isSystemDefault", "lineageId",
        "templateKind", "createdAt", "updatedAt"
      ) VALUES (
        ${ORDINARY_TEMPLATE_ID}, ${ACTOR_ID}, 'Synthetic ordinary SOAP',
        '[]'::jsonb, 1, 'Synthetic rollback continuity control', 'active',
        false, 'synthetic-ordinary-lineage', 'structured',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "note_templates" (
        "id", "doctorId", "name", "sections", "version",
        "versionDescription", "status", "isSystemDefault", "lineageId",
        "templateKind", "createdAt", "updatedAt"
      ) VALUES (
        ${INACTIVE_TWIN_TEMPLATE_ID}, ${ACTOR_ID},
        'Synthetic inactive Twin boundary', '[]'::jsonb, 1,
        'Synthetic rollback concurrency boundary', 'inactive', false,
        'synthetic-inactive-twin-lineage', 'template_twin_docx',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "template_twin_source_artifacts" (
        "id", "practiceId", "createdById", "lineageId", "lineageVersion",
        "sha256", "mimeType", "sizeBytes", "validationStatus",
        "rejectionCodes", "createdAt"
      ) VALUES (
        ${TWIN_SOURCE_ID}, ${PRACTICE_ID}, ${ACTOR_ID},
        'synthetic-inactive-twin-lineage', 1, ${SYNTHETIC_SHA256},
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        4096, 'quarantined', ARRAY['SYNTHETIC_ROLLBACK_FIXTURE'],
        CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "template_twin_compiled_versions" (
        "id", "sourceArtifactId", "noteTemplateId", "compilerVersion",
        "irSchemaVersion", "compiledAt", "compiledDocumentIr",
        "unsupportedElements", "structureSha256", "staticContentSha256",
        "certificationStatus", "blockingUnsupportedCount"
      ) VALUES (
        ${TWIN_COMPILED_ID}, ${TWIN_SOURCE_ID}, ${INACTIVE_TWIN_TEMPLATE_ID},
        'synthetic-compiler-v1', 1, CURRENT_TIMESTAMP,
        '{"synthetic":true}'::jsonb, '[]'::jsonb, ${SYNTHETIC_SHA256},
        ${SYNTHETIC_SHA256}, 'NEEDS_CONFIRMATION', 0
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "transcribe_md_patients" (
        "id", "practiceId", "name", "createdAt", "updatedAt"
      ) VALUES (
        ${PATIENT_ID}, ${PRACTICE_ID}, 'Reserved Synthetic Identity',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "transcribe_visits" (
        "id", "userId", "patientId", "specialty", "inputMode", "status",
        "noteTemplateId", "noteTemplateVersion", "createdAt", "updatedAt"
      ) VALUES (
        ${VISIT_ID}, ${ACTOR_ID}, ${PATIENT_ID}, 'synthetic', 'text_notes',
        'QUEUED', ${ORDINARY_TEMPLATE_ID}, 1,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "transcribe_visits" (
        "id", "userId", "patientId", "specialty", "inputMode", "status",
        "noteTemplateId", "noteTemplateVersion", "createdAt", "updatedAt"
      ) VALUES (
        ${TWIN_VISIT_ID}, ${PHYSICIAN_ID}, ${PATIENT_ID}, 'synthetic', 'text_notes',
        'QUEUED', ${INACTIVE_TWIN_TEMPLATE_ID}, 1,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "transcribe_visits" (
        "id", "userId", "patientId", "specialty", "inputMode", "status",
        "noteTemplateId", "noteTemplateVersion", "createdAt", "updatedAt"
      ) VALUES
        (${SIGNED_TWIN_VISIT_ID}, ${PHYSICIAN_ID}, ${PATIENT_ID}, 'synthetic',
         'text_notes', 'FAILED', ${INACTIVE_TWIN_TEMPLATE_ID}, 1,
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        (${RACE_TWIN_VISIT_ID}, ${RACE_PHYSICIAN_ID}, ${PATIENT_ID}, 'synthetic',
         'text_notes', 'FAILED', ${INACTIVE_TWIN_TEMPLATE_ID}, 1,
         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    `;
    // A terminal-but-unsigned fill hides its nonterminal Twin visit from the
    // pinned-without-fill inventory. Reassigning it after PREPARE used to
    // expose new drain inventory without touching status.
    await tx.$executeRaw`
      INSERT INTO "template_twin_fill_manifests" (
        "id", "practiceId", "visitId", "compiledVersionId",
        "noteTemplateId", "noteTemplateVersion", "compilerVersion",
        "resolverVersion", "rendererVersion", "status", "fillManifest",
        "manifestSha256", "factSetSha256", "validationResult",
        "createdAt", "updatedAt"
      ) VALUES (
        ${TWIN_FILL_ID}, ${PRACTICE_ID}, ${TWIN_VISIT_ID}, ${TWIN_COMPILED_ID},
        ${INACTIVE_TWIN_TEMPLATE_ID}, 1, 'synthetic-compiler-v1',
        'synthetic-resolver-v1', 'synthetic-renderer-v1', 'FAILED',
        '{"synthetic":true}'::jsonb, ${SYNTHETIC_SHA256}, ${SYNTHETIC_SHA256},
        '{"synthetic":true}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      INSERT INTO "template_twin_fill_manifests" (
        "id", "practiceId", "visitId", "compiledVersionId",
        "noteTemplateId", "noteTemplateVersion", "compilerVersion",
        "resolverVersion", "rendererVersion", "status", "fillManifest",
        "manifestSha256", "factSetSha256", "soapVersion", "soapSha256",
        "validationResult", "pinnedGlobalRolloutGeneration",
        "pinnedPracticeRolloutGeneration", "signedGlobalRolloutGeneration",
        "signedPracticeRolloutGeneration", "signedDecisionAt",
        "createdAt", "updatedAt"
      ) VALUES (
        ${SIGNED_TWIN_FILL_ID}, ${PRACTICE_ID}, ${SIGNED_TWIN_VISIT_ID},
        ${TWIN_COMPILED_ID}, ${INACTIVE_TWIN_TEMPLATE_ID}, 1,
        'synthetic-compiler-v1', 'synthetic-resolver-v1',
        'synthetic-renderer-v1', 'SIGNED', '{"synthetic":true}'::jsonb,
        ${SYNTHETIC_SHA256}, ${SYNTHETIC_SHA256}, 1, ${SYNTHETIC_SHA256},
        '{"synthetic":true}'::jsonb, 11, 7, 11, 7, CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      )
    `;
    await tx.$executeRaw`
      UPDATE "template_twin_rollout_controls"
      SET "enabled" = true, "generation" = 11,
          "updatedAt" = CURRENT_TIMESTAMP
      WHERE "id" = 'global'
    `;
  });

  // Owner-first race: a fill INSERT waiting on the shared lineage gate must
  // re-read the physician's committed tenant and fail closed.
  const databaseUrl = process.env.DATABASE_URL!;
  const observerClient = new Client({ connectionString: databaseUrl });
  const ownerClient = new Client({ connectionString: databaseUrl });
  const fillClient = new Client({ connectionString: databaseUrl });
  await Promise.all([
    observerClient.connect(),
    ownerClient.connect(),
    fillClient.connect(),
  ]);
  await fillClient.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
  await expectDatabaseRejection(
    () => insertRaceFill(fillClient),
    "Template Twin tenant lineage writes require READ COMMITTED isolation",
  );
  await fillClient.query("ROLLBACK");

  await ownerClient.query("BEGIN");
  await ownerClient.query(
    `SELECT pg_advisory_xact_lock(
       hashtextextended('template_twin_fill_visit_owner_lineage_v5', 0)
     )`,
  );
  await ownerClient.query(
    `UPDATE "users" SET "practiceId" = $1, "updatedAt" = CURRENT_TIMESTAMP
     WHERE "id" = $2`,
    [OTHER_PRACTICE_ID, RACE_PHYSICIAN_ID],
  );
  await fillClient.query("BEGIN ISOLATION LEVEL READ COMMITTED");
  const staleFillAttempt = insertRaceFill(fillClient);
  void staleFillAttempt.catch(() => undefined);
  await waitForAdvisoryWaiter(
    observerClient,
    fillClient,
    "owner-first fill lineage gate",
  );
  await ownerClient.query("COMMIT");
  await expectDatabaseRejection(
    () => staleFillAttempt,
    "Template Twin fill physician tenant lineage mismatch",
  );
  await fillClient.query("ROLLBACK");
  await prisma.$executeRaw`
    UPDATE "users"
    SET "practiceId" = ${PRACTICE_ID}, "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = ${RACE_PHYSICIAN_ID}
  `;

  // Fill-first race: once a fill commits, a waiting visit reassignment must
  // observe it and reject the ownership change, including before signing.
  await fillClient.query("BEGIN ISOLATION LEVEL READ COMMITTED");
  await fillClient.query(
    `SELECT pg_advisory_xact_lock(
       hashtextextended('template_twin_fill_visit_owner_lineage_v5', 0)
     )`,
  );
  await insertRaceFill(fillClient);
  await ownerClient.query("BEGIN ISOLATION LEVEL READ COMMITTED");
  const staleVisitAttempt = ownerClient.query(
    `UPDATE "transcribe_visits"
     SET "userId" = $1, "updatedAt" = CURRENT_TIMESTAMP
     WHERE "id" = $2`,
    [OTHER_PRACTICE_PHYSICIAN_ID, RACE_TWIN_VISIT_ID],
  );
  void staleVisitAttempt.catch(() => undefined);
  await waitForAdvisoryWaiter(
    observerClient,
    ownerClient,
    "fill-first visit lineage gate",
  );
  await fillClient.query("COMMIT");
  await expectDatabaseRejection(
    () => staleVisitAttempt,
    "Template Twin visit physician ownership is immutable",
  );
  await ownerClient.query("ROLLBACK");
  await prisma.$executeRaw`
    DELETE FROM "template_twin_fill_manifests"
    WHERE "id" = ${RACE_TWIN_FILL_ID}
  `;
  await Promise.all([
    observerClient.end(),
    ownerClient.end(),
    fillClient.end(),
  ]);

  const actor = {
    userId: ACTOR_ID,
    userEmail: "stale-session-value@synthetic.test",
    practiceId: PRACTICE_ID,
  };
  const cancelled = await prepareTemplateTwinRollback({
    operationId: PREPARE_CANCEL_ID,
    reasonCode: "DISPOSABLE_REHEARSAL",
    changeId: "synthetic-change-cancel",
    actor,
  });
  assert(cancelled.status.fenceState === "PREPARED", "Prepare did not fence.");
  const cancelResult = await cancelPreparedTemplateTwinRollback({
    operationId: PREPARE_CANCEL_ID,
    actor,
  });
  assert(
    cancelResult.status.fenceState === "OPEN",
    "Cancel did not reopen fence.",
  );
  assert(
    cancelResult.status.globalRolloutEnabled,
    "Cancel changed global rollout.",
  );
  assert(
    cancelResult.status.inventory.enabledPractices === 1,
    "Cancel changed practice rollout.",
  );

  const prepared = await prepareTemplateTwinRollback({
    operationId: REVOKE_ID,
    reasonCode: "DISPOSABLE_REHEARSAL",
    changeId: "synthetic-change-revoke",
    actor,
  });
  assert(
    prepared.status.readyToRevoke,
    "Synthetic inventory should be revocable.",
  );
  const fencedFinalClaim = await prisma.$transaction(
    async (tx: typeof prisma) =>
      lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: PRACTICE_ID,
        pinnedToken: {
          practiceId: PRACTICE_ID,
          globalGeneration: BigInt(11),
          practiceGeneration: BigInt(7),
        },
        env: { TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
  );
  assert(
    !fencedFinalClaim.allowed &&
      fencedFinalClaim.code === "TEMPLATE_TWIN_ROLLBACK_FENCE_ACTIVE",
    "Prepared rollback did not block a database-backed final claim.",
  );

  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_rollout_controls"
        SET "rollbackFenceState" = 'OPEN',
            "rollbackFenceGeneration" = "rollbackFenceGeneration" + 1,
            "rollbackOperationId" = NULL,
            "rollbackPreparedAt" = NULL,
            "rollbackRevokedAt" = NULL
        WHERE "id" = 'global'
      `,
    "Template Twin prepared operation must own the fence",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_rollback_operations"
        SET "state" = 'CANCELLED',
            "cancelledAt" = CURRENT_TIMESTAMP,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${REVOKE_ID}::uuid
      `,
    "Template Twin prepared fence must link a prepared operation",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        DELETE FROM "template_twin_rollout_controls" WHERE "id" = 'global'
      `,
    "Template Twin rollout singleton cannot be deleted",
  );
  await expectAnyDatabaseRejection(
    () =>
      prisma.$executeRaw`
        TRUNCATE TABLE "template_twin_rollback_operations"
      `,
    "rollback operation history truncate",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "note_templates"
        SET "templateKind" = 'template_twin_docx'
        WHERE "id" = ${ORDINARY_TEMPLATE_ID}
      `,
    "Template Twin version cannot be activated while rollback is fenced",
  );

  await expectDatabaseRejection(
    () =>
      prisma.$transaction(async (tx: typeof prisma) => {
        await tx.$executeRaw`
        UPDATE "template_twin_rollout_controls"
        SET "enabled" = false, "generation" = "generation" + 1
        WHERE "id" = 'global'
      `;
        await tx.$executeRaw`
        UPDATE "template_twin_rollout_controls"
        SET "enabled" = true, "generation" = "generation" + 1
        WHERE "id" = 'global'
      `;
      }),
    "Template Twin cannot be enabled while rollback is fenced",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$transaction(async (tx: typeof prisma) => {
        await tx.$executeRaw`
        UPDATE "practices"
        SET "templateTwinEnabled" = false,
            "templateTwinRolloutGeneration" =
              "templateTwinRolloutGeneration" + 1
        WHERE "id" = ${PRACTICE_ID}
      `;
        await tx.$executeRaw`
        UPDATE "practices"
        SET "templateTwinEnabled" = true,
            "templateTwinRolloutGeneration" =
              "templateTwinRolloutGeneration" + 1
        WHERE "id" = ${PRACTICE_ID}
      `;
      }),
    "Template Twin practice cannot be enabled while rollback is fenced",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_rollout_controls"
        SET "rollbackPreparedAt" = "rollbackPreparedAt" + INTERVAL '1 second'
        WHERE "id" = 'global'
      `,
    "Template Twin rollback fence metadata cannot change without a transition",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_fill_manifests"
        SET "visitId" = ${VISIT_ID}, "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${TWIN_FILL_ID}
      `,
    "Template Twin fill identity is immutable",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_fill_manifests"
        SET "id" = ${`${TWIN_FILL_ID}-tampered`}
        WHERE "id" = ${TWIN_FILL_ID}
      `,
    "Template Twin fill primary identity is immutable",
  );
  for (const visitId of [TWIN_VISIT_ID, SIGNED_TWIN_VISIT_ID]) {
    await expectDatabaseRejection(
      () =>
        prisma.$executeRaw`
          UPDATE "transcribe_visits"
          SET "userId" = ${SAME_PRACTICE_PHYSICIAN_ID},
              "updatedAt" = CURRENT_TIMESTAMP
          WHERE "id" = ${visitId}
        `,
      "Template Twin visit physician ownership is immutable",
    );
    await expectDatabaseRejection(
      () =>
        prisma.$executeRaw`
          UPDATE "transcribe_visits"
          SET "userId" = ${OTHER_PRACTICE_PHYSICIAN_ID},
              "updatedAt" = CURRENT_TIMESTAMP
          WHERE "id" = ${visitId}
        `,
      "Template Twin visit physician ownership is immutable",
    );
  }
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "users"
        SET "practiceId" = ${OTHER_PRACTICE_ID},
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${PHYSICIAN_ID}
      `,
    "Template Twin physician practice ownership is immutable",
  );

  const preparedEventKey = `template-twin:rollback:${REVOKE_ID}:prepared`;
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        DELETE FROM "template_twin_audit_outbox"
        WHERE "eventKey" = ${preparedEventKey}
      `,
    "Template Twin rollback outbox evidence cannot be deleted",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_audit_outbox"
        SET "eventKey" = ${`${preparedEventKey}:tampered`}
        WHERE "eventKey" = ${preparedEventKey}
      `,
    "Template Twin rollback outbox identity is immutable",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_audit_outbox"
        SET "status" = 'DELIVERED',
            "deliveredAt" = CURRENT_TIMESTAMP,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "eventKey" = ${preparedEventKey}
      `,
    "Template Twin delivered rollback audit receipt is missing",
  );

  const concurrentClient = new Client({ connectionString: databaseUrl });
  await concurrentClient.connect();
  const [revocationRace, pinnedVisitRace] = await Promise.allSettled([
    revokeTemplateTwinRollout({ operationId: REVOKE_ID, actor }),
    concurrentClient.query(
      `UPDATE "transcribe_visits"
       SET "noteTemplateId" = $1, "noteTemplateVersion" = 1,
           "updatedAt" = CURRENT_TIMESTAMP
       WHERE "id" = $2`,
      [INACTIVE_TWIN_TEMPLATE_ID, VISIT_ID],
    ),
  ]);
  await concurrentClient.end();
  assert(
    revocationRace.status === "fulfilled",
    "Concurrent rollback revocation did not complete.",
  );
  assert(
    pinnedVisitRace.status === "rejected" &&
      pinnedVisitRace.reason instanceof Error &&
      pinnedVisitRace.reason.message.includes(
        "Template Twin pinned visit cannot start while rollback is fenced",
      ),
    "A concurrent Twin-pinned visit crossed the rollback fence.",
  );
  const revoked = revocationRace.value;
  const repeated = await revokeTemplateTwinRollout({
    operationId: REVOKE_ID,
    actor,
  });
  assert(
    revoked.status.fenceState === "REVOKED",
    "Revoke did not become terminal.",
  );
  assert(
    !revoked.status.globalRolloutEnabled,
    "Global rollout remains enabled.",
  );
  assert(
    revoked.status.inventory.enabledPractices === 0,
    "Practice rollout remains enabled.",
  );
  assert(
    revoked.status.inventory.activeTemplateVersions === 0,
    "Active Twins remain.",
  );
  assert(
    !revoked.status.rollbackComplete,
    "Rollback was marked complete before transactional audit delivery.",
  );
  assert(repeated.idempotent, "Repeated revoke was not idempotent.");

  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_rollback_operations"
        SET "reasonCode" = 'TAMPERED_HISTORY'
        WHERE "id" = ${REVOKE_ID}::uuid
      `,
    "Template Twin rollback operation identity is immutable",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        UPDATE "template_twin_rollback_operations"
        SET "updatedAt" = "updatedAt" + INTERVAL '1 second'
        WHERE "id" = ${REVOKE_ID}::uuid
      `,
    "Template Twin rollback operation transition is invalid",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        DELETE FROM "template_twin_rollback_operations"
        WHERE "id" = ${REVOKE_ID}::uuid
      `,
    "Template Twin rollback operation history cannot be deleted",
  );

  const databaseClock = await prisma.$queryRaw<Array<{ drainAt: Date }>>`
    SELECT clock_timestamp() + INTERVAL '1 minute' AS "drainAt"
  `;
  assert(databaseClock[0], "Synthetic database clock was unavailable.");
  const delivered = await drainTemplateTwinAuditOutbox({
    prisma: prisma as never,
    now: databaseClock[0].drainAt,
    limit: 100,
  });
  assert(
    delivered.delivered === 5 &&
      delivered.failed === 0 &&
      delivered.contended === 0,
    "Synthetic rollback audit delivery did not drain exactly once.",
  );
  const completed = await inspectTemplateTwinRollback();
  assert(
    completed.rollbackComplete,
    "Synthetic rollback did not complete after audit delivery and reconciliation.",
  );
  assert(
    completed.inventory.missingRollbackAuditReceipts === 0,
    "Rollback completion retained missing exact audit receipts.",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        DELETE FROM "audit_logs"
        WHERE "templateTwinOutboxEventKey" = ${preparedEventKey}
      `,
    "Template Twin rollback audit receipt cannot be deleted",
  );
  await expectDatabaseRejection(
    () =>
      prisma.$executeRaw`
        DELETE FROM "template_twin_audit_outbox"
        WHERE "eventKey" = ${preparedEventKey}
      `,
    "Template Twin rollback outbox evidence cannot be deleted",
  );
  await expectDatabaseRejection(
    () => prisma.$executeRaw`TRUNCATE TABLE "audit_logs"`,
    "Template Twin rollback audit evidence cannot be truncated",
  );

  const rows = await prisma.$queryRaw<
    Array<{
      ordinaryStatus: string;
      auditCount: bigint;
      rollbackEventCount: bigint;
      exactReceiptCount: bigint;
      actorEmailCount: bigint;
      appliedMigrationCount: bigint;
    }>
  >`
    SELECT
      (SELECT "status" FROM "note_templates" WHERE "id" = ${ORDINARY_TEMPLATE_ID})
        AS "ordinaryStatus",
      (SELECT COUNT(*)::bigint FROM "template_twin_audit_outbox")
        AS "auditCount",
      (SELECT COUNT(*)::bigint FROM "template_twin_audit_outbox"
       WHERE "action" IN (
         'TEMPLATE_TWIN_ROLLBACK_PREPARED',
         'TEMPLATE_TWIN_ROLLBACK_CANCELLED',
         'TEMPLATE_TWIN_ROLLOUT_REVOKED'
       )) AS "rollbackEventCount",
      (SELECT COUNT(*)::bigint FROM "audit_logs"
       WHERE "templateTwinOutboxEventKey" LIKE
         ${`template-twin:rollback:${REVOKE_ID}:%`}) AS "exactReceiptCount",
      (SELECT COUNT(*)::bigint FROM "template_twin_audit_outbox"
       WHERE "actorEmailSnapshot" = 'rollback-fence-admin@synthetic.test')
        AS "actorEmailCount",
      (SELECT COUNT(*)::bigint FROM "_prisma_migrations"
       WHERE "finished_at" IS NOT NULL AND "rolled_back_at" IS NULL)
        AS "appliedMigrationCount"
  `;
  const evidence = rows[0];
  assert(evidence?.ordinaryStatus === "active", "Ordinary template changed.");
  assert(evidence.auditCount === BigInt(5), "Unexpected outbox event census.");
  assert(
    evidence.rollbackEventCount === BigInt(4),
    "Rollback audit events are incomplete.",
  );
  assert(
    evidence.exactReceiptCount === BigInt(3),
    "Revoked operation audit receipts are not exactly linked.",
  );
  assert(
    evidence.actorEmailCount === evidence.auditCount,
    "DB actor snapshot was not refreshed.",
  );

  process.stdout.write(
    `${JSON.stringify({
      status: "PASS",
      migrations: Number(evidence.appliedMigrationCount),
      fenceGeneration: revoked.status.fenceGeneration,
      globalGeneration: revoked.status.globalRolloutGeneration,
      auditEvents: Number(evidence.auditCount),
      ordinaryTemplatePreserved: true,
      repeatedRevokeIdempotent: true,
      operationHistoryImmutable: true,
      operationFenceCouplingEnforced: true,
      completeOperationAuditHistoryEnforced: true,
      rolloutSingletonImmutable: true,
      rollbackTruncateBlocked: true,
      activeVersionFenceEnforced: true,
      fenceMetadataImmutable: true,
      auditDeliveryComplete: true,
      exactAuditReceiptsImmutable: true,
      unsignedFillIdentityImmutable: true,
      fillPrimaryIdentityImmutable: true,
      fillPhysicianOwnershipImmutable: true,
      signedFillPhysicianOwnershipImmutable: true,
      fillOwnershipLineageRacesBlocked: true,
      staleSnapshotLineageWritesBlocked: true,
      databaseRelativeAuditClock: true,
      concurrentPinnedVisitBlocked: true,
      finalClaimBlocked: true,
      directEnableBlocked: true,
      productionMutation: false,
    })}\n`,
  );
}

main()
  .catch((error: unknown) => {
    process.stderr.write(
      `${error instanceof Error ? error.message : "Rollback-fence PostgreSQL proof failed."}\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
