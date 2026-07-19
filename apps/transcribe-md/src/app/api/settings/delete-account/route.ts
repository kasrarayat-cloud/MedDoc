// ============================================================================
// POST /api/settings/delete-account (T-M16.2)
// ----------------------------------------------------------------------------
// Body: { password: string, confirmation: string }
//   - `password` must match the current user's passwordHash.
//   - `confirmation` must be literally "DELETE" (typed by the user in
//     the dialog).
//
// Safety ordering:
//   1. Auth check + password check + confirmation string check.
//      Any of these failing returns 400/401 before we touch anything.
//   2. Read the data needed for the audit row (visit count, specialty,
//      email, name, practiceId).
//   3. Transaction:
//        a. INSERT AccountDeletion (the audit row — written BEFORE
//           the User is dropped so a crash mid-transaction rolls BOTH
//           back and we never end up with an audit row pointing at a
//           user that still exists, or a deleted user with no audit).
//        b. DELETE AiCall WHERE practiceId = user.practiceId (PHI-
//           adjacent; user's explicit scope is a full purge).
//        c. DELETE Practice (the synthetic 1:1 for a solo-TranscribeMD
//           user; FK to users has no cascade so we do it manually).
//        d. DELETE User — Prisma cascades TranscribeVisit →
//           VisitDelivery + DoctorEditPattern, UserSession, Account,
//           Session, AuthToken.
//   4. Best-effort MinIO prefix purge + goodbye email — both
//      catch-and-log. The T-M12 orphan sweep handles MinIO stragglers.
//   5. Return 200 with a redirect URL; the client signs out + navigates.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

import prisma from "@meddoc/db";
import { AuditAction, Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { deleteAudioObjectsByPrefix } from "@/lib/minio";
import { sendAccountDeletedConfirmation } from "@/lib/email";
import { MARKETING_URL } from "@/lib/constants";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BodySchema = z.object({
  password: z.string().min(1),
  confirmation: z.literal("DELETE", {
    message: "Type DELETE to confirm.",
  }),
});

/** Audit-row retention window. When the T-M16.3+ sweeper lands it
 *  deletes AccountDeletion rows with purgeAt in the past. */
const PURGE_DELAY_MS = 90 * 24 * 60 * 60 * 1000;

const RETAINED_TEMPLATE_TWIN_AUDIT_ACTIONS: readonly AuditAction[] = [
  AuditAction.TEMPLATE_TWIN_SOURCE_UPLOADED,
  AuditAction.TEMPLATE_TWIN_COMPILED,
  AuditAction.TEMPLATE_TWIN_QUARANTINED,
  AuditAction.TEMPLATE_TWIN_MAPPING_UPDATED,
  AuditAction.TEMPLATE_TWIN_CERTIFIED,
  AuditAction.TEMPLATE_TWIN_ACTIVATED,
  AuditAction.TEMPLATE_TWIN_SYNTHETIC_TESTED,
  AuditAction.TEMPLATE_TWIN_FIELD_REVIEWED,
  AuditAction.TEMPLATE_TWIN_SIGN_BLOCKED,
  AuditAction.TEMPLATE_TWIN_RENDER_VERIFIED,
  AuditAction.TEMPLATE_TWIN_FIELD_TEST_WAIVED,
  AuditAction.TEMPLATE_TWIN_DEACTIVATED,
  AuditAction.TEMPLATE_TWIN_RETIRED,
  AuditAction.TEMPLATE_TWIN_ROLLED_BACK,
  AuditAction.TEMPLATE_TWIN_SAFETY_GATE_BLOCKED,
  AuditAction.TEMPLATE_TWIN_OBJECT_RECONCILED,
  AuditAction.TEMPLATE_TWIN_FIELD_INTENT_RECORDED,
  AuditAction.TEMPLATE_TWIN_CUSTOM_EXAMPLE_EXECUTED,
  AuditAction.TEMPLATE_TWIN_CUSTOM_EXAMPLE_ACKNOWLEDGED,
  AuditAction.TEMPLATE_TWIN_STATIC_ASSET_APPROVED,
  AuditAction.TEMPLATE_TWIN_STATIC_ASSET_REJECTED,
  AuditAction.TEMPLATE_TWIN_STATIC_ASSET_REVOKED,
  AuditAction.TEMPLATE_TWIN_STATIC_ASSET_USED,
  AuditAction.EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED,
];

type RetainedTemplateTwinClient = Pick<
  Prisma.TransactionClient,
  | "templateTwinSourceArtifact"
  | "templateTwinCertification"
  | "templateTwinFieldTestWaiver"
  | "templateTwinFieldIntentDecision"
  | "templateTwinStaticAsset"
  | "templateTwinStaticAssetDecision"
  | "templateTwinStaticAssetReviewReceipt"
  | "templateTwinCustomExampleExecution"
  | "templateTwinSyntheticQaRun"
  | "noteTemplate"
  | "templateTwinFillManifest"
  | "templateTwinObjectLedger"
  | "templateTwinAuditOutbox"
  | "auditLog"
>;

async function countRetainedTemplateTwinRecords(
  client: RetainedTemplateTwinClient,
  user: { id: string; practiceId: string },
): Promise<number> {
  const counts = await Promise.all([
    client.templateTwinSourceArtifact.count({
      where: { practiceId: user.practiceId },
    }),
    client.templateTwinCertification.count({
      where: { certifiedById: user.id },
    }),
    client.templateTwinFieldTestWaiver.count({
      where: { waivedById: user.id },
    }),
    client.templateTwinFieldIntentDecision.count({
      where: { decidedById: user.id },
    }),
    client.templateTwinStaticAsset.count({
      where: { practiceId: user.practiceId },
    }),
    client.templateTwinStaticAssetDecision.count({
      where: { asset: { practiceId: user.practiceId } },
    }),
    client.templateTwinStaticAssetReviewReceipt.count({
      where: { practiceId: user.practiceId },
    }),
    client.templateTwinCustomExampleExecution.count({
      where: {
        OR: [
          { practiceId: user.practiceId },
          { executedById: user.id },
          { acknowledgedById: user.id },
        ],
      },
    }),
    client.templateTwinSyntheticQaRun.count({
      where: {
        OR: [{ practiceId: user.practiceId }, { doctorId: user.id }],
      },
    }),
    client.noteTemplate.count({
      where: { doctorId: user.id, templateKind: "template_twin_docx" },
    }),
    client.templateTwinFillManifest.count({
      where: { practiceId: user.practiceId },
    }),
    client.templateTwinObjectLedger.count({
      where: { practiceId: user.practiceId },
    }),
    client.templateTwinAuditOutbox.count({
      where: { practiceId: user.practiceId },
    }),
    client.auditLog.count({
      where: {
        practiceId: user.practiceId,
        action: { in: [...RETAINED_TEMPLATE_TWIN_AUDIT_ACTIONS] },
      },
    }),
  ]);
  return counts.reduce((total, count) => total + count, 0);
}

class TemplateTwinDeletionAuditError extends Error {
  constructor(cause: unknown) {
    super("The Template Twin deletion safety audit could not be recorded.", {
      cause,
    });
    this.name = "TemplateTwinDeletionAuditError";
  }
}

class TemplateTwinDeletionOwnershipConflict extends Error {
  constructor() {
    super("The account ownership rows changed during deletion.");
    this.name = "TemplateTwinDeletionOwnershipConflict";
  }
}

async function enqueueRetainedTemplateTwinDeletionGate(
  client: Parameters<typeof enqueueTemplateTwinAudit>[0],
  input: {
    userId: string;
    practiceId: string;
    email: string;
    retainedRecordCount: number;
  },
): Promise<void> {
  try {
    await enqueueTemplateTwinAudit(client, {
      eventKey: `account-deletion-policy-gate:${input.userId}:${crypto.randomUUID()}`,
      practiceId: input.practiceId,
      actorId: input.userId,
      actorEmailSnapshot: input.email,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "User",
      targetId: input.userId,
      metadata: {
        reasonCode: "TEMPLATE_TWIN_RETENTION_POLICY_REQUIRED",
        retainedRecordCount: input.retainedRecordCount,
      },
    });
  } catch (error) {
    throw new TemplateTwinDeletionAuditError(error);
  }
}

function retainedTemplateTwinResponse(): NextResponse {
  return NextResponse.json(
    {
      error:
        "This account has retained Template Twin records. Deletion requires an approved retention or anonymization policy.",
      code: "TEMPLATE_TWIN_RETENTION_POLICY_REQUIRED",
    },
    { status: 409 },
  );
}

function databaseErrorCode(error: unknown): string | null {
  if (!error || typeof error !== "object" || !("code" in error)) return null;
  return typeof error.code === "string" ? error.code : null;
}

function isSerializableWriteConflict(error: unknown): boolean {
  const code = databaseErrorCode(error);
  return code === "P2034" || code === "40001";
}

function isRestrictiveDeletionConflict(error: unknown): boolean {
  if (error instanceof TemplateTwinDeletionOwnershipConflict) return true;
  const code = databaseErrorCode(error);
  if (code === "P2003" || code === "P2014" || code === "P2004") return true;
  const message =
    error instanceof Error
      ? error.message
      : error && typeof error === "object" && "message" in error
        ? String(error.message)
        : "";
  return /template[ _-]?twin|foreign key|restrict(?:ive)?|trigger/i.test(
    message,
  );
}

export const POST = withApiHandler(
  "api:settings:delete-account",
  async (req) => {
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join(".") || "_form";
      return NextResponse.json(
        { error: first?.message || "invalid payload", field },
        { status: 400 },
      );
    }

    // Verify the password ourselves — don't call NextAuth signIn because
    // that would rotate the session cookie + trip single-session tracking.
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        name: true,
        passwordHash: true,
        practiceId: true,
      },
    });
    if (!user) return apiError("user not found", 404);

    const passwordOk = await bcrypt.compare(
      parsed.data.password,
      user.passwordHash,
    );
    if (!passwordOk) {
      return NextResponse.json(
        { error: "Password is incorrect.", field: "password" },
        { status: 400 },
      );
    }

    // Template Twin artifacts and certification evidence are deliberately
    // immutable. Until Privacy/Legal approves an anonymization, retention, and
    // legal-hold policy, deleting an account that owns or has certified Twin
    // records would either violate those guarantees or fail on restrictive
    // foreign keys. Detect that state before starting the destructive
    // transaction or touching object storage, and durably record the blocked
    // safety gate.
    const retainedTwinRecordCount = await countRetainedTemplateTwinRecords(
      prisma,
      user,
    );

    if (retainedTwinRecordCount > 0) {
      try {
        await enqueueRetainedTemplateTwinDeletionGate(prisma, {
          userId: user.id,
          practiceId: user.practiceId,
          email: user.email,
          retainedRecordCount: retainedTwinRecordCount,
        });
      } catch {
        return NextResponse.json(
          {
            error:
              "Account deletion is temporarily unavailable because the required safety audit could not be recorded.",
            code: "TEMPLATE_TWIN_AUDIT_ENQUEUE_FAILED",
          },
          { status: 503 },
        );
      }
      return retainedTemplateTwinResponse();
    }

    // Read the audit-row data inside a read-only snapshot. We don't care
    // about strict isolation here — a visit created in the microsecond
    // between this read and the transaction below only skews visitCount
    // by one, and will be cascade-dropped anyway.
    const [visitCount, lastVisit] = await Promise.all([
      prisma.transcribeVisit.count({ where: { userId: user.id } }),
      prisma.transcribeVisit.findFirst({
        where: { userId: user.id },
        orderBy: { createdAt: "desc" },
        select: { specialty: true },
      }),
    ]);
    const specialty = lastVisit?.specialty ?? null;

    const purgeAt = new Date(Date.now() + PURGE_DELAY_MS);

    // ── Atomic destructive path ─────────────────────────────────────
    try {
      let deletionResult:
        | { deleted: true; retainedRecordCount: 0 }
        | { deleted: false; retainedRecordCount: number }
        | undefined;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          deletionResult = await prisma.$transaction(
            async (tx: Prisma.TransactionClient) => {
              // Lock both FK roots before the second retained-record check.
              // Inserts for practice-owned or physician-owned Twin evidence
              // must obtain a conflicting FK key-share lock, so a racing write
              // either commits before this check (and is observed) or waits for
              // the atomic deletion outcome. Serializable isolation catches any
              // remaining predicate race.
              const lockedOwners = await tx.$queryRaw<
                Array<{ userId: string }>
              >(
                Prisma.sql`
                SELECT u."id" AS "userId"
                FROM "practices" p
                JOIN "users" u ON u."practiceId" = p."id"
                WHERE p."id" = ${user.practiceId} AND u."id" = ${user.id}
                FOR UPDATE OF p, u
              `,
              );
              if (lockedOwners.length !== 1) {
                throw new TemplateTwinDeletionOwnershipConflict();
              }

              const recheckedRetainedCount =
                await countRetainedTemplateTwinRecords(tx, user);
              if (recheckedRetainedCount > 0) {
                await enqueueRetainedTemplateTwinDeletionGate(tx, {
                  userId: user.id,
                  practiceId: user.practiceId,
                  email: user.email,
                  retainedRecordCount: recheckedRetainedCount,
                });
                return {
                  deleted: false as const,
                  retainedRecordCount: recheckedRetainedCount,
                };
              }

              await tx.accountDeletion.create({
                data: {
                  userId: user.id,
                  email: user.email,
                  specialty,
                  visitCount,
                  purgeAt,
                },
              });
              await tx.aiCall.deleteMany({
                where: { practiceId: user.practiceId },
              });
              // User and Practice are symmetric for solo TranscribeMD users
              // (1:1 synthetic Practice). Non-solo users would keep the
              // Practice — but TranscribeMD signup only creates solo ones,
              // so dropping it is always correct here.
              await tx.user.delete({ where: { id: user.id } });
              await tx.practice.delete({ where: { id: user.practiceId } });
              return {
                deleted: true as const,
                retainedRecordCount: 0 as const,
              };
            },
            { isolationLevel: "Serializable" },
          );
          break;
        } catch (error) {
          if (isSerializableWriteConflict(error) && attempt < 2) continue;
          throw error;
        }
      }

      if (!deletionResult?.deleted) {
        return retainedTemplateTwinResponse();
      }
    } catch (err) {
      if (err instanceof TemplateTwinDeletionAuditError) {
        return NextResponse.json(
          {
            error:
              "Account deletion is temporarily unavailable because the required safety audit could not be recorded.",
            code: "TEMPLATE_TWIN_AUDIT_ENQUEUE_FAILED",
          },
          { status: 503 },
        );
      }
      if (
        isRestrictiveDeletionConflict(err) ||
        isSerializableWriteConflict(err)
      ) {
        // The destructive transaction has rolled back. Recount and enqueue the
        // policy gate in a separate committed statement so a restrictive FK,
        // trigger, or exhausted serializable race cannot become a generic 500.
        const racedRetainedCount = await countRetainedTemplateTwinRecords(
          prisma,
          user,
        );
        try {
          await enqueueRetainedTemplateTwinDeletionGate(prisma, {
            userId: user.id,
            practiceId: user.practiceId,
            email: user.email,
            retainedRecordCount: racedRetainedCount,
          });
        } catch {
          return NextResponse.json(
            {
              error:
                "Account deletion is temporarily unavailable because the required safety audit could not be recorded.",
              code: "TEMPLATE_TWIN_AUDIT_ENQUEUE_FAILED",
            },
            { status: 503 },
          );
        }
        return retainedTemplateTwinResponse();
      }
      console.error(
        `[api:settings:delete-account] transaction failed user=${user.id}:`,
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError(
        "Could not complete deletion. Please try again or contact support.",
        500,
      );
    }

    log.info("api:settings:delete-account", "user purged", {
      userId: user.id,
      visitCount,
    });
    // Pass explicit userId + userEmail + practiceId — the session has
    // just been invalidated via the transaction's cascade, so a fresh
    // auth() inside logAudit would see no session. The audit row still
    // needs the actor for the compliance export.
    void logAudit({
      action: "ACCOUNT_DELETED",
      targetType: "User",
      targetId: user.id,
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      metadata: { visitCount },
    });

    // ── Best-effort post-transaction cleanup ────────────────────────

    // MinIO: wipe everything under `{userId}/`. T-M12 sweep handles
    // stragglers if this errors.
    try {
      const result = await deleteAudioObjectsByPrefix(`${user.id}/`);
      if (result.failures.length > 0) {
        console.warn(
          `[api:settings:delete-account] minio: ${result.deleted} deleted, ${result.failures.length} failed (T-M12 sweep will catch them)`,
        );
      } else if (result.deleted > 0) {
        console.info(
          `[api:settings:delete-account] minio: purged ${result.deleted} audio objects under ${user.id}/`,
        );
      }
    } catch (err) {
      console.error(
        `[api:settings:delete-account] minio cleanup threw (T-M12 sweep will catch):`,
        redactPhi(err instanceof Error ? err.message : err),
      );
    }

    // Goodbye email — catch-and-log; never fail the delete on an email
    // hiccup.
    if (process.env.RESEND_API_KEY) {
      try {
        await sendAccountDeletedConfirmation({
          toEmail: user.email,
          userName: user.name,
        });
      } catch (err) {
        console.error(
          `[api:settings:delete-account] goodbye email failed:`,
          redactPhi(err instanceof Error ? err.message : err),
        );
      }
    }

    return NextResponse.json(
      {
        ok: true,
        redirectTo: `${MARKETING_URL}/?deleted=1`,
      },
      { status: 200 },
    );
  },
);
