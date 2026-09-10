// ============================================================================
// POST /api/admin/users/[id]/suspend — soft-pause an account
// ----------------------------------------------------------------------------
// Sets suspendedAt + suspendedBy + suspendedReason and bumps
// forceLogoutAt to now so any in-flight session is invalidated on its
// next request. Reversible via /unsuspend (the row stays intact —
// distinct from the older deactivatedAt one-way flag).
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { refuseLastOwner } from '@/lib/admin-last-owner-refusal';
import { logAudit } from '@/lib/audit';
import {
  classifyGuardError,
  withPracticeLock,
  wouldStrandPractice,
} from '@/lib/last-owner-invariant';

const Body = z.object({ reason: z.string().trim().max(500).optional() });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:suspend', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Phase 6Z — server-side self-action block. The UI already disables the
  // chip when isSelf, but a direct POST (curl, replay, browser console)
  // would otherwise lock the actor out of /admin/* and nuke their
  // session via forceLogoutAt. Defense in depth: refuse here too.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot suspend your own account — ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid body' }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  // ── RULING #210 — the FRIENDLY REFUSAL. ────────────────────────────────────
  // Enforcement is the `users_last_owner_guard` trigger; without this block the
  // write still cannot strand the practice, but the caller would learn why only
  // from the trigger-refusal branch below.
  //
  // ⚠️ ADMIN-5 — THE REFUSAL IS AUDITED NOW. It returned a bare 409 before, so
  // the one act this invariant exists to stop left no trace when it was
  // stopped. A gate nothing records is one path away from not existing.
  const lastOwner = await wouldStrandPractice(id);
  if (lastOwner.wouldStrand) {
    return refuseLastOwner({
      targetId: id,
      practiceId: user.practiceId,
      attempted: 'SUSPEND',
      source: 'precheck',
      reason: lastOwner.reason,
      membersLeft: lastOwner.membersLeft,
    });
  }

  const now = new Date();
  // ⚠️ RULING #268 — THE PRACTICE LOCK BEFORE THE ROW WRITE. Suspending an
  // active owner removes a seat, so this write reaches the guard's locking path
  // and can be one half of the measured deadlock. `user.practiceId` is read
  // from the row above, which is the practice the trigger will key on.
  try {
    await prisma.$transaction((tx) =>
      withPracticeLock(tx, user.practiceId, async () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await (tx.user as any).update({
          where: { id },
          data: {
            suspendedAt: now,
            suspendedBy: ctx.session.user.id,
            suspendedReason: parsed.data.reason ?? null,
            forceLogoutAt: now,
          },
        });
      }),
    );
  } catch (err) {
    // ⚠️ ADMIN-5 — THE RACE THE PRE-CHECK CANNOT SEE, SPOKEN INSTEAD OF A 500.
    // The pre-check runs OUTSIDE the lock, so two admins suspending the last
    // two owners at once both pass it and the trigger refuses the second. That
    // refusal used to reach the caller as "Internal server error". Only a
    // last-owner refusal is mapped — an isolation or orphan refusal, or any
    // other database error, is rethrown and stays a 500, because this route
    // cannot honestly name a remedy for it.
    const refusal = classifyGuardError(err);
    if (refusal?.kind !== 'LAST_OWNER') throw err;
    return refuseLastOwner({
      targetId: id,
      practiceId: user.practiceId,
      attempted: 'SUSPEND',
      source: 'trigger',
      reason: refusal.reason,
      membersLeft: refusal.membersLeft,
    });
  }

  await logAudit({
    action: 'USER_SUSPENDED',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      reason: parsed.data.reason ?? null,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({
    ok: true,
    user: {
      id,
      suspendedAt: now.toISOString(),
      suspendedBy: ctx.session.user.id,
      suspendedReason: parsed.data.reason ?? null,
    },
  });
});
