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
//   2. ADMIN-5 — the practice must be the user's ALONE. Any other user row
//      in it (a colleague, or a removed ex-member) refuses BY NAME with a 409,
//      before any write. See the block below for why.
//   3. Read the data needed for the audit row (visit count, specialty,
//      email, name, practiceId) and BUILD the ACCOUNT_DELETED row — a failure
//      to build it refuses (fail-closed, as S4c requires).
//   4. Transaction:
//        a. the practice lock (#268);
//        b. INSERT the ACCOUNT_DELETED audit row — ADMIN-5: INSIDE the
//           transaction, as its FIRST write, so it commits with the deletion
//           or rolls back with it. It was written outside, before, and a
//           refused deletion left it behind;
//        c. INSERT AccountDeletion;
//        d. DELETE User — Prisma cascades TranscribeVisit → VisitDelivery +
//           DoctorEditPattern, UserSession, Account, Session, AuthToken;
//        e. DELETE the practice-scoped clinical rows (the user's own, because
//           the practice is theirs alone — step 2 guarantees it);
//        f. DELETE Practice.
//   5. Publish the audit row to the live admin stream, then best-effort MinIO
//      prefix purge + goodbye email — both catch-and-log.
//   6. Return 200 with a redirect URL; the client signs out + navigates.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';

import type { TransactionClient } from '@meddoc/db';
import { apiError, withApiHandler } from '@/lib/api-error';
import { LIVE_MEMBER_WHERE, withPracticeLock } from '@/lib/last-owner-invariant';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { deleteAudioObjectsByPrefix } from '@/lib/minio';
import { sendAccountDeletedConfirmation } from '@/lib/email';
import { MARKETING_URL } from '@/lib/constants';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { buildAuditRow, publishAuditRow, type AuditRowData } from '@/lib/audit';

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

/** ADMIN-5 — the two refusals, in the doctor's words. */
const PRACTICE_HAS_MEMBERS_MESSAGE =
  "Your practice has other members, so your account can't be deleted here — deleting it " +
  "would also delete the practice's shared patients and records. Ask a practice owner to " +
  'remove you, or, if you are an owner, use Transfer ownership in Settings → Members and ' +
  'choose to leave.';
const PRACTICE_HAS_FORMER_MEMBERS_MESSAGE =
  'Your practice still holds the accounts of former members, so it cannot be deleted from ' +
  'here. Contact support to close the practice.';

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

  // ── ADMIN-5 — THE PRACTICE MUST BE THE USER'S ALONE, OR WE REFUSE BY NAME ──
  //
  // ⚠️ THIS ROUTE ASSUMED A SOLO PRACTICE, AND ADMIN-1's INVITES MADE THAT FALSE.
  // Its purge below deletes EVERY patient, task, medication, allergy and AI call
  // of the PRACTICE — correct when the practice is one person's, and a deletion
  // of colleagues' clinical records when it is not. Driven on the unfixed route
  // (`__tests__/admin5-member-deletion.test.ts`): a clinician in a two-member
  // practice reached `patient.deleteMany({ where: { practiceId } })`. It never
  // stuck only because `practice.delete` then failed on `users_practiceId_fkey`
  // (ON DELETE RESTRICT) and rolled everything back — the FK ruling #210 calls
  // "a coincidence that has been lucky" — and the user got a generic 500.
  //
  // So ANY other user row refuses, before any write. Not only live members:
  // a removed or deactivated ex-member's row still references the practice, so
  // `practice.delete` cannot succeed either, and the honest answer is a
  // sentence, not "please try again". A SOLO practice passes untouched and is
  // deleted exactly as before.
  //
  // ⚠️ THIS IS A PRE-CHECK, NOT A GUARD. A member joining between here and the
  // transaction makes `practice.delete` fail on the FK and the whole
  // transaction — the audit row included, now — roll back: fail-closed.
  const othersInPractice = await prisma.user.count({
    where: { practiceId: user.practiceId, id: { not: user.id } },
  });
  if (othersInPractice > 0) {
    const liveOthers = await prisma.user.count({
      where: { practiceId: user.practiceId, id: { not: user.id }, ...LIVE_MEMBER_WHERE },
    });
    return liveOthers > 0
      ? apiError(PRACTICE_HAS_MEMBERS_MESSAGE, 409, { code: 'PRACTICE_HAS_MEMBERS' })
      : apiError(PRACTICE_HAS_FORMER_MEMBERS_MESSAGE, 409, { code: 'PRACTICE_HAS_FORMER_MEMBERS' });
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

  // ── The audit row: BUILT first, WRITTEN inside the transaction ───────────
  //
  // S4c (kept): the row must be written while the practice and user rows still
  // exist, so it lands with valid references; the FKs then DETACH it (SET
  // NULL) as those rows go, and `practiceIdSnapshot` keeps the tenant. And it
  // is FAIL-CLOSED: if the row cannot be recorded, the deletion is not
  // performed — an unauditable destruction of clinical records is the one
  // outcome this route must never produce.
  //
  // ADMIN-5 (changed): S4c met both of those by writing the row BEFORE and
  // OUTSIDE the transaction, which bought a third outcome it did not intend —
  // a deletion the database REFUSED (the last-owner trigger, the FK above)
  // rolled back and LEFT THE ROW BEHIND. An append-only trail then says an
  // account was deleted that still exists. Measured on a real database: status
  // 500, one ACCOUNT_DELETED row, the user intact. Now the row is the
  // transaction's first write, so it commits with the deletion or rolls back
  // with it, and S4c's two properties still hold.
  let auditRow: AuditRowData;
  try {
    auditRow = await buildAuditRow({
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
      `[api:settings:delete-account] AUDIT ROW COULD NOT BE BUILT — refusing to delete user=${user.id}:`,
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

      // ⚠️ ADMIN-5 — THE AUDIT ROW IS THE FIRST WRITE. See the block above.
      // The same row `logAudit` would have built; `as never` is the same cast
      // `logAudit` uses, for the same reason (the shared barrel's Json typing).
      await tx.auditLog.create({ data: auditRow as never });

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
      // user's own records — the ADMIN-5 refusal above guarantees nobody else
      // is in this practice — and the request is an explicit full purge, so
      // they are deleted rather than detached. audit_logs and billing_events
      // are deliberately absent from this list: they DETACH (SET NULL) when the
      // practice goes, because an audit trail and a financial record must
      // outlive the account they describe.
      await tx.aiCall.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.allergy.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.medication.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.task.deleteMany({ where: { practiceId: user.practiceId } });
      await tx.patient.deleteMany({ where: { practiceId: user.practiceId } });

      // Practice last. Cascades TranscribeMdPatient and the template_twin_*
      // artifacts; nulls the practice ref on the surviving audit/billing rows.
      // ⚠️ "TranscribeMD signup only creates solo ones" USED TO BE THE REASON
      // THIS WAS SAFE, AND SINCE ADMIN-1 IT IS FALSE. It is safe now because
      // the refusal above runs first.
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

  // Committed — only now does the row reach the live admin stream.
  publishAuditRow(auditRow);

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
