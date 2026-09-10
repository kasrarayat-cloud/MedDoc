// ============================================================================
// POST /api/admin/users/[id]/deactivate — the one-way-until-reactivated flag
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console (`deactivateUserAction`), under
// ruling #310 step 3 — "PORT, not BUILD, never REVIVE". The shape is the
// SUSPEND door's, because deactivation removes an owner seat exactly as
// suspension does:
//
//   self-action 403 -> confirmEmail -> minimal target read -> no-op refusal ->
//   friendly last-owner refusal -> ONE transaction under the practice lock ->
//   audit AFTER commit, attributed to the TARGET's practice.
//
// ⚠️ THE THREE DEACTIVATION COLUMNS ARE WRITTEN TOGETHER. `isActive = false`
// without `deactivatedAt` is the inconsistent shape ruling #226 counted in
// production (5 rows); every writer from here on sets both, plus who did it.
//
// ⚠️ AND `forceLogoutAt` IS BUMPED WITH THEM. `isActive` is checked at LOGIN
// (`nextauth.ts`) and on each request by `validateSession`, but a session that
// predates the deactivation must stay dead after a later REACTIVATION too —
// that is what `forceLogoutAt > session.createdAt` guarantees and `isActive`
// alone does not.
//
// ⚠️ `practiceRole` IS KEPT. A deactivated member keeps their seat's role so a
// later reactivation restores what they had — the no-downgrade principle (the
// 2026-08-07 ruling) needs the role to still be there to restore.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock, wouldStrandPractice } from '@/lib/last-owner-invariant';

const Body = z.object({ confirmEmail: z.string().email().max(254) }).strict();

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:deactivate', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Deactivating yourself locks you out of /admin and is unrecoverable without
  // a peer, so the server refuses it whatever the UI does.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot deactivate your own account — ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => null);
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json({ error: 'Body must include confirmEmail' }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true, isActive: true, deactivatedAt: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  if (parsed.data.confirmEmail.toLowerCase() !== user.email.toLowerCase()) {
    return NextResponse.json({ error: 'confirmEmail does not match user.email' }, { status: 400 });
  }

  // No-op refusal: already deactivated in BOTH columns. A row with only one of
  // them set is the inconsistent shape above, and deactivating it again is the
  // repair — so that case writes.
  if (user.isActive === false && user.deactivatedAt !== null) {
    return NextResponse.json(
      { error: 'This account is already deactivated.', reason: 'ALREADY_DEACTIVATED' },
      { status: 409 }
    );
  }

  // ── RULING #210 — the FRIENDLY REFUSAL, asked about the TARGET. ─────────────
  const lastOwner = await wouldStrandPractice(id);
  if (lastOwner.wouldStrand) {
    return NextResponse.json(
      { error: lastOwner.reason, reason: 'LAST_OWNER', membersLeft: lastOwner.membersLeft },
      { status: 409 }
    );
  }

  const now = new Date();
  // ⚠️ RULING #268 — THE PRACTICE LOCK BEFORE THE ROW WRITE, on the practice
  // read from the target's own row, which is the one the trigger keys on.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, user.practiceId, async () => {
      await tx.user.update({
        where: { id },
        data: {
          isActive: false,
          deactivatedAt: now,
          deactivatedBy: ctx.session.user.id,
          forceLogoutAt: now,
        },
      });
    }),
  );

  await logAudit({
    action: 'USER_DEACTIVATED',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({
    ok: true,
    user: { id, deactivatedAt: now.toISOString(), deactivatedBy: ctx.session.user.id },
  });
});
