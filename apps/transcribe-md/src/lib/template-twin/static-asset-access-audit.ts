import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";

import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import type { TemplateTwinStaticAssetActor } from "./static-assets";

export type TemplateTwinStaticAssetAccessSurface = "page" | "api";

const ACCESS_DETAILS = {
  page: {
    action: "ADMIN_DASHBOARD_ACCESS",
    source: "rsc:/settings/note-format/static-assets",
  },
  api: {
    action: "ADMIN_API_ACCESS",
    source: "api:get:/api/note-templates/template-twin/static-assets",
  },
} as const;

interface CurrentStaticAssetAdminRow {
  readonly id: string;
  readonly email: string | null;
  readonly practiceId: string;
  readonly role: string;
}

interface CurrentStaticAssetPracticeRow {
  readonly id: string;
}

export class TemplateTwinStaticAssetAccessAuditError extends Error {
  readonly code = "TT_STATIC_ASSET_ACCESS_AUDIT_UNAVAILABLE" as const;

  constructor() {
    super("The required reusable-image access audit did not complete.");
    this.name = "TemplateTwinStaticAssetAccessAuditError";
  }
}

function validActor(input: TemplateTwinStaticAssetActor): boolean {
  return (
    input.userId.length > 0 &&
    input.practiceId.length > 0 &&
    (input.role === "ADMIN" || input.role === "SUPER_ADMIN") &&
    input.rolloutToken.practiceId === input.practiceId &&
    input.rolloutToken.globalGeneration >= BigInt(1) &&
    input.rolloutToken.practiceGeneration >= BigInt(1)
  );
}

/**
 * Durable, fail-closed access receipt for the practice-admin static-asset
 * inventory. The surface selector maps to fixed PHI-free details; callers
 * cannot provide free-form audit metadata. Rollout and current tenant/admin
 * authority are reasserted under the established global -> practice -> actor
 * lock order before the audit row commits.
 */
export async function recordTemplateTwinStaticAssetInventoryAccess(input: {
  readonly actor: TemplateTwinStaticAssetActor;
  readonly surface: TemplateTwinStaticAssetAccessSurface;
}): Promise<void> {
  if (!validActor(input.actor)) {
    throw new TemplateTwinStaticAssetAccessAuditError();
  }
  const details = ACCESS_DETAILS[input.surface];
  if (!details) {
    throw new TemplateTwinStaticAssetAccessAuditError();
  }

  try {
    await runSerializableTransactionWithRetry({
      prisma,
      operation: "template_twin_static_asset_access_audit",
      isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted,
      context: { practiceId: input.actor.practiceId },
      transaction: async (tx) => {
        const rollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId: input.actor.practiceId,
          pinnedToken: input.actor.rolloutToken as TemplateTwinRolloutToken,
        });
        if (!rollout.allowed) {
          throw new TemplateTwinStaticAssetAccessAuditError();
        }

        // Re-acquire the active-practice row explicitly after the rollout
        // fence. This makes the global -> practice -> actor order visible and
        // holds practice deactivation/rollout changes through audit commit.
        const practices = await tx.$queryRaw<CurrentStaticAssetPracticeRow[]>(
          Prisma.sql`
            SELECT practice."id"
            FROM "practices" practice
            WHERE practice."id" = ${input.actor.practiceId}
              AND practice."isActive" = TRUE
              AND practice."templateTwinEnabled" = TRUE
            FOR UPDATE
          `,
        );
        if (
          practices.length !== 1 ||
          practices[0]?.id !== input.actor.practiceId
        ) {
          throw new TemplateTwinStaticAssetAccessAuditError();
        }

        const rows = await tx.$queryRaw<
          CurrentStaticAssetAdminRow[]
        >(Prisma.sql`
          SELECT actor."id", actor."email", actor."practiceId",
            actor."role"::text AS "role"
          FROM "users" actor
          WHERE actor."id" = ${input.actor.userId}
            AND actor."practiceId" = ${input.actor.practiceId}
            AND actor."role" IN (
              'ADMIN'::"UserRole",
              'SUPER_ADMIN'::"UserRole"
            )
            AND actor."isActive" = TRUE
            AND actor."deactivatedAt" IS NULL
            AND actor."suspendedAt" IS NULL
            AND actor."softDeletedAt" IS NULL
            AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
            AND (
              NOT ('SUPER_ADMIN'::"Product" = ANY(actor."products"))
              OR (
                actor."mfaEnabled" = TRUE
                AND regexp_replace(
                  actor."mfaSecret",
                  U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]',
                  '',
                  'g'
                ) <> ''
                AND actor."mfaVerifiedAt" IS NOT NULL
                AND actor."mfaVerifiedAt" <= CURRENT_TIMESTAMP
              )
            )
          FOR UPDATE
        `);
        const current = rows.length === 1 ? rows[0] : null;
        if (
          !current ||
          current.id !== input.actor.userId ||
          current.practiceId !== input.actor.practiceId ||
          (current.role !== "ADMIN" && current.role !== "SUPER_ADMIN") ||
          !current.email
        ) {
          throw new TemplateTwinStaticAssetAccessAuditError();
        }

        await tx.auditLog.create({
          data: {
            userId: current.id,
            userEmailSnapshot: current.email,
            action: details.action,
            targetId: current.practiceId,
            targetType: "TemplateTwinStaticAssetIndex",
            metadata: { source: details.source },
            success: true,
            practiceId: current.practiceId,
          },
        });
      },
    });
  } catch {
    // Never propagate database, rollout, or credential details to the caller.
    throw new TemplateTwinStaticAssetAccessAuditError();
  }
}
