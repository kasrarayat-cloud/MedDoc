// ============================================================================
// POST /api/admin/users/[id]/sessions/[sid]/revoke — end ONE login session
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console's per-row session action, under
// ruling #310 step 3 — and made to do what its button said.
//
// ⚠️ THE ORIGINAL DELETED A `session_logs` HISTORY ROW AND REVOKED NOTHING. Its
// own module said so ("history-only delete"): the person stayed signed in and
// the only effect was a hole in the record. Porting that verbatim would delete
// audit-like history for a click an operator believes ended a session.
//
// This deletes the `user_sessions` row through `revokeSession` — the helper the
// /settings "Sign out" button uses — so the JWT whose `sessionId` pointed at it
// is treated as signed out on its next request. The row is looked up by BOTH
// its id and the user in the path, so a session id belonging to somebody else
// is a 404, never a revocation of the wrong person.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { revokeSession } from '@meddoc/auth';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:sessions:revoke', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  const sid = segs[segs.indexOf('sessions') + 1];
  if (!id || !sid || segs.indexOf('sessions') < 0) {
    return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  }

  // Revoking your own session from here is a sign-out that bypasses the
  // audited LOGOUT path; use Sign out.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot revoke your own session here — use Sign out.' },
      { status: 403 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const row = await prisma.userSession.findFirst({
    where: { id: sid, userId: id },
    select: { id: true, sessionToken: true },
  });
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  await revokeSession(row.sessionToken);

  // meddoc-pro audited its session actions as `SESSION_EXPIRED`; kept, with the
  // reason that distinguishes an admin revocation from a natural expiry.
  await logAudit({
    action: 'SESSION_EXPIRED',
    targetType: 'User',
    targetId: id,
    metadata: {
      reason: 'admin_revoke',
      sessionId: row.id,
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({ ok: true, sessionId: row.id });
});
