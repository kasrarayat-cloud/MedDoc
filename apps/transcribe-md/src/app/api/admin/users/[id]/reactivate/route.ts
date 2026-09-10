// ============================================================================
// POST /api/admin/users/[id]/reactivate — reactivation, and PROMO DOOR 3 OF 3
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console (`activateUserAction`), under
// ruling #310 step 3 — "PORT, not BUILD, never REVIVE". That app serves 410, so
// until this route existed the reactivation door ruling #99 depends on was
// UNREACHABLE: the practices whose members are all deactivated had no route to
// their promo at all.
//
// ⚠️ B7 STEP 3c, DOOR 3 OF 3 — THE REACTIVATION GRANT. Ruling #99: "the
// reactivation path grants the promo exactly as the signup path does". The
// backfill funds practices with an ACTIVE member; a practice whose members are
// all deactivated is funded HERE, the moment anyone returns, rather than
// pre-minted into limbo on a table that refuses deletes.
//
// ⚠️ THE GRANT RUNS AFTER THE COMMIT AND OUTSIDE ANY TRANSACTION, AND THAT IS
// A CORRECTNESS REQUIREMENT, NOT A STYLE. `grantPromoCredit` absorbs a
// collision as `already_granted`, but a unique violation ABORTS the Postgres
// transaction it runs in, and COMMIT on an aborted transaction is silently a
// ROLLBACK (`billing-grant.ts`, measured on QA 2026-08-12). A reactivation
// into an already-funded practice is the ORDINARY case, so a grant inside the
// lock transaction would silently un-reactivate most of the people it was
// asked to bring back. Called with the default client, the collision aborts
// only its own implicit statement.
//
// ⚠️ AND A GRANT FAILURE DOES NOT UN-REACTIVATE ANYONE. The account already
// exists and already works; a failed grant leaves it active and unfunded,
// which the backfill's derived population repairs because the key is
// idempotent. The failure is CAUGHT, reported in the response and recorded on
// the reactivation's audit row — the meddoc-pro original let it escape into a
// generic "Failed." after the reactivation had committed, which told the
// operator the one thing that was not true.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
// The SUBPATH, not the barrel — the same choice the meddoc-pro door made: one
// function is needed here, and none of the vendor SDKs behind `@meddoc/ai`.
import { grantPromoCredit } from '@meddoc/ai/billing-grant';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock, wouldOrphanMember } from '@/lib/last-owner-invariant';

const Body = z.object({}).strict();

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:reactivate', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Self-rehabilitation by symmetry with unsuspend: the audit trail should
  // carry a peer's action, not the subject's own.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot reactivate your own account — ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw ?? {});
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid body' }, { status: 400 });
  }

  const target = await prisma.user.findUnique({
    where: { id },
    select: {
      id: true,
      email: true,
      practiceId: true,
      practiceRole: true,
      isActive: true,
      deactivatedAt: true,
      softDeletedAt: true,
    },
  });
  if (!target) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  // A soft-deleted account is not deactivated, it is gone: `softDeletedAt` is
  // cleared nowhere, so clearing the deactivation flags would restore nothing
  // the person could use — and would still fund the practice as if somebody
  // had come back. Refused, with the reason.
  if (target.softDeletedAt !== null) {
    return NextResponse.json(
      { error: 'This account was soft-deleted; reactivation cannot restore it.', reason: 'SOFT_DELETED' },
      { status: 409 }
    );
  }

  if (target.isActive === true && target.deactivatedAt === null) {
    return NextResponse.json(
      { error: 'This account is not deactivated.', reason: 'NOT_DEACTIVATED' },
      { status: 409 }
    );
  }

  // ⚠️ T6 + THE 2026-08-07 RULING — "NO-DOWNGRADE APPLIES TO REACTIVATION".
  // OWNER is restored ONLY where the row has a practice and NO role, never
  // unconditionally: that would overwrite a real CLINICIAN/TECH assignment with
  // an owner's rights on the way back in. The narrow real case is a user
  // deactivated BEFORE the practiceRole backfill, which skipped deactivated
  // rows — reactivating them without a role fails the CHECK
  // `users_active_member_has_practice_role`, naming the CHECK and not the cause.
  const roleRestore =
    target.practiceId && !target.practiceRole ? { practiceRole: 'OWNER' as const } : {};

  const now = new Date();
  const patch = {
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    // ⚠️ A session that predates this reactivation must not come back to life
    // with it. A row deactivated by the retired console never had
    // `forceLogoutAt` bumped, so its old `user_sessions` rows — up to 7 days —
    // would validate again the moment `isActive` flips. Bumping it here is
    // strictly safe: while deactivated the person had no valid session to lose.
    forceLogoutAt: now,
    ...roleRestore,
  };

  // ── `users_no_orphan_member`'s FRIENDLY REFUSAL. ────────────────────────────
  // A CLINICIAN or TECH returning to a practice with no active owner is refused
  // by the trigger (23514); without this the operator gets a raw 500.
  const orphan = await wouldOrphanMember({ kind: 'update', userId: id, patch });
  if (orphan.wouldOrphan) {
    return NextResponse.json(
      { error: orphan.reason, reason: 'NO_ACTIVE_OWNER', restorableOwners: orphan.restorableOwners },
      { status: 409 }
    );
  }

  // ⚠️ RULING #268 — THE PRACTICE LOCK BEFORE THE ROW WRITE. Reactivating a
  // non-owner makes a live member of a row that was not one, so the orphan arm
  // takes `pg_advisory_xact_lock` on this practice: unlocked, this is one half
  // of the measured deadlock.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, target.practiceId, async () => {
      await tx.user.update({
        where: { id },
        data: {
          isActive: true,
          deactivatedAt: null,
          deactivatedBy: null,
          forceLogoutAt: now,
          ...roleRestore,
        },
      });
    }),
  );

  // ── THE GRANT — after the commit above, outside any transaction. ───────────
  let promo: 'granted' | 'already_granted' | 'failed' | 'no_practice' = 'no_practice';
  if (target.practiceId) {
    try {
      const grant = await grantPromoCredit(target.practiceId);
      if (grant.granted) {
        promo = 'granted';
        await logAudit({
          action: 'PROMO_GRANT_CREDITED',
          targetType: 'Practice',
          targetId: target.practiceId,
          practiceId: target.practiceId,
          metadata: {
            door: 'reactivation',
            bucket: 'promo',
            reactivatedUserId: id,
            amountMicroUsd: grant.amountMicroUsd.toString(),
            balanceAfter: grant.balanceAfter.toString(),
            seq: grant.seq.toString(),
          },
        });
      } else {
        promo = 'already_granted';
      }
    } catch (err) {
      promo = 'failed';
      console.error('[admin:reactivate] promo grant failed after the reactivation committed:', err);
    }
  }

  // meddoc-pro's label, kept for continuity — see the note beside
  // `USER_CREATED` in `lib/audit.ts`.
  await logAudit({
    action: 'USER_CREATED',
    targetType: 'User',
    targetId: id,
    metadata: {
      action: 'reactivated',
      targetEmail: target.email,
      actorEmail: ctx.session.user.email,
      practiceRoleRestored: 'practiceRole' in roleRestore,
      promo,
    },
    practiceId: target.practiceId,
  });

  return NextResponse.json({ ok: true, user: { id }, promo });
});
