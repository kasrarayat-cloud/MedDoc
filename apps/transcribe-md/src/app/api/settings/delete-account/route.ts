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

import { z } from 'zod';
import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';

import type { TransactionClient } from '@meddoc/db';
import { apiError, withApiHandler } from '@/lib/api-error';
import { withPracticeLock } from '@/lib/last-owner-invariant';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { deleteAudioObjectsByPrefix } from '@/lib/minio';
import { sendAccountDeletedConfirmation } from '@/lib/email';
import { MARKETING_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  password: z.string().min(1),
  confirmation: z.literal('DELETE', {
    message: 'Type DELETE to confirm.',
  }),
});

/** Audit-row retention window. When the T-M16.3+ sweeper lands it
 *  deletes AccountDeletion rows with purgeAt in the past. */
const PURGE_DELAY_MS = 90 * 24 * 60 * 60 * 1000;

export const POST = withApiHandler('api:settings:delete-account', async (req) => {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
  if (blocked) return blocked;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError('invalid JSON body', 400);
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    const field = first?.path.join('.') || '_form';
    return NextResponse.json(
      { error: first?.message || 'invalid payload', field },
      { status: 400 }
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
  if (!user) return apiError('user not found', 404);

  const passwordOk = await bcrypt.compare(parsed.data.password, user.passwordHash);
  if (!passwordOk) {
    return NextResponse.json(
      { error: 'Password is incorrect.', field: 'password' },
      { status: 400 }
    );
  }

  // Read the audit-row data inside a read-only snapshot. We don't care
  // about strict isolation here — a visit created in the microsecond
  // between this read and the transaction below only skews visitCount
  // by one, and will be cascade-dropped anyway.
  const [visitCount, lastVisit] = await Promise.all([
    prisma.transcribeVisit.count({ where: { userId: user.id } }),
    prisma.transcribeVisit.findFirst({
      where: { userId: user.id },
      orderBy: { createdAt: 'desc' },
      select: { specialty: true },
    }),
  ]);
  const specialty = lastVisit?.specialty ?? null;

  const purgeAt = new Date(Date.now() + PURGE_DELAY_MS);

  // ── Audit FIRST, and fail closed ────────────────────────────────
  //
  // S4c. This used to be a `void logAudit(...)` AFTER the transaction, which
  // was wrong twice over: the transaction always threw (see below) so it was
  // never reached, and it passes practiceId — which by then would have been
  // deleted, so the insert would have FK-violated and `void` would have
  // swallowed it. Either way ACCOUNT_DELETED was never written.
  //
  // Writing it BEFORE the destructive work means the practice and user rows
  // still exist, so the row lands with valid references. The migration then
  // detaches those references (SET NULL) as the entities are removed, and
  // practiceIdSnapshot preserves the tenant.
  //
  // Awaited and fail-closed on purpose: if we cannot record the deletion we do
  // not perform it. An unauditable destruction of clinical records is the one
  // outcome this system must never produce — better a user retries than that
  // PHI disappears with no trace of who removed it or when.
  try {
    await logAudit({
      action: 'ACCOUNT_DELETED',
      targetType: 'User',
      targetId: user.id,
      userId: user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      metadata: { visitCount, specialty },
    });
  } catch (err) {
    console.error(
      `[api:settings:delete-account] AUDIT WRITE FAILED — refusing to delete user=${user.id}:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    return apiError(
      'Could not complete deletion. Please try again or contact support.',
      500
    );
  }

  // ── Atomic destructive path ─────────────────────────────────────
  try {
    await prisma.$transaction(async (tx: TransactionClient) => {
      // ⚠️ RULING #268 — THE PRACTICE LOCK BEFORE THE USER-ROW WRITE, AND THIS
      // DOOR IS A DELETE. Self-service deletion removes an active-owner seat
      // like any other removal, so it reaches the guard's locking path and can
      // be one half of the measured deadlock. Taken here, at the TOP of the
      // transaction, so it precedes every write below rather than only the
      // `user.delete` — a lock taken after an earlier row write would order
      // nothing.
      await withPracticeLock(tx, user.practiceId, async () => {});
      await tx.accountDeletion.create({
        data: {
          userId: user.id,
          email: user.email,
          specialty,
          visitCount,
          purgeAt,
        },
      });

      // User first. Cascades TranscribeVisit (and, since the S4c migration,
      // the RxWarningOverride rows hanging off each visit — that FK was
      // RESTRICT and silently blocked the whole cascade for any doctor who
      // had ever overridden an Rx warning), plus UserSession, Session,
      // Account, AuthToken, ApiUsage, SessionLog, DoctorEditPattern.
      // Deleting sessions here is what revokes access immediately.
      await tx.user.delete({ where: { id: user.id } });

      // Practice-scoped clinical rows whose FK is RESTRICT. These are the
      // user's own records and the request is an explicit full purge, so they
      // are deleted rather than detached. audit_logs and billing_events are
      // deliberately absent from this list: they DETACH (SET NULL) when the
      // practice goes, because an audit trail and a financial record must
      // outlive the account they describe.
      await tx.aiCall.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.allergy.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.medication.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.task.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.patient.deleteMany({ where: { practiceId: user.practiceId } });

      // Practice last. Cascades TranscribeMdPatient and the template_twin_*
      // artifacts; nulls the practice ref on the surviving audit/billing rows.
      // User and Practice are symmetric for solo TranscribeMD users (1:1
      // synthetic Practice) — TranscribeMD signup only creates solo ones, so
      // dropping it is always correct here.
      await tx.practice.delete({ where: { id: user.practiceId } });
    });
  } catch (err) {
    console.error(
      `[api:settings:delete-account] transaction failed user=${user.id}:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    return apiError(
      'Could not complete deletion. Please try again or contact support.',
      500
    );
  }

  log.info('api:settings:delete-account', 'user purged', {
    userId: user.id,
    visitCount,
  });

  // ── Best-effort post-transaction cleanup ────────────────────────

  // MinIO: wipe everything under `{userId}/`. T-M12 sweep handles
  // stragglers if this errors.
  try {
    const result = await deleteAudioObjectsByPrefix(`${user.id}/`);
    if (result.failures.length > 0) {
      console.warn(
        `[api:settings:delete-account] minio: ${result.deleted} deleted, ${result.failures.length} failed (T-M12 sweep will catch them)`
      );
    } else if (result.deleted > 0) {
      console.info(
        `[api:settings:delete-account] minio: purged ${result.deleted} audio objects under ${user.id}/`
      );
    }
  } catch (err) {
    console.error(
      `[api:settings:delete-account] minio cleanup threw (T-M12 sweep will catch):`,
      redactPhi(err instanceof Error ? err.message : err)
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
        redactPhi(err instanceof Error ? err.message : err)
      );
    }
  }

  return NextResponse.json(
    {
      ok: true,
      redirectTo: `${MARKETING_URL}/?deleted=1`,
    },
    { status: 200 }
  );
});
