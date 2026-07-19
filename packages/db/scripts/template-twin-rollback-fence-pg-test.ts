import prisma from "@meddoc/db";

import {
  cancelPreparedTemplateTwinRollback,
  inspectTemplateTwinRollback,
  prepareTemplateTwinRollback,
  revokeTemplateTwinRollout,
} from "../../../apps/transcribe-md/src/lib/template-twin/rollback-control";
import { drainTemplateTwinAuditOutbox } from "../../../apps/transcribe-md/src/lib/template-twin/audit-outbox";
import { lockTemplateTwinRolloutForFinalClaim } from "../../../apps/transcribe-md/src/lib/template-twin/rollout";

const PRACTICE_ID = "synthetic-rollback-fence-practice";
const ACTOR_ID = "synthetic-rollback-fence-admin";
const ORDINARY_TEMPLATE_ID = "synthetic-ordinary-template";
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
    "A fenced direct enable did not fail with the expected database guard.",
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
      UPDATE "template_twin_rollout_controls"
      SET "enabled" = true, "generation" = 11,
          "updatedAt" = CURRENT_TIMESTAMP
      WHERE "id" = 'global'
    `;
  });

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

  const revoked = await revokeTemplateTwinRollout({
    operationId: REVOKE_ID,
    actor,
  });
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

  const delivered = await drainTemplateTwinAuditOutbox({
    prisma: prisma as never,
    now: new Date("2026-07-19T13:30:00.000Z"),
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

  const rows = await prisma.$queryRaw<
    Array<{
      ordinaryStatus: string;
      auditCount: bigint;
      rollbackEventCount: bigint;
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
      fenceMetadataImmutable: true,
      auditDeliveryComplete: true,
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
