// ============================================================================
// GET /api/admin/users/[id]/sessions — the user's login sessions
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console (`getUserSessionsAction`), under
// ruling #310 step 3 — but pointed at the table that is TRUE in this app.
//
// ⚠️ THE ORIGINAL READ `session_logs`, AND NOTHING IN THIS APP WRITES IT. Its
// only writers were meddoc-pro's own login hook and a dead helper, so a
// faithful port would list a history that stopped growing when that app went
// dark. The live record is `user_sessions` — one row per login, the row the
// JWT's `sessionId` claim resolves against on every request — so that is what
// is listed, and a row here is something `…/revoke` can actually end.
//
// ⚠️ `sessionToken` IS NEVER SELECTED. It is the bearer secret the JWT points
// at; returning it would hand the admin UI (and its network log) a credential
// for somebody else's account. Revocation is addressed by row id instead.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

export const dynamic = 'force-dynamic';

export type AdminSessionStatus = 'active' | 'expired' | 'invalidated';

export const GET = adminApi('users:sessions', async (req) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id || id === 'sessions') return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, isActive: true, suspendedAt: true, softDeletedAt: true, forceLogoutAt: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const rows = await prisma.userSession.findMany({
    where: { userId: id },
    orderBy: [{ lastActiveAt: 'desc' }, { id: 'desc' }],
    take: 50,
    select: {
      id: true,
      ipAddress: true,
      userAgent: true,
      createdAt: true,
      lastActiveAt: true,
      expiresAt: true,
    },
  });

  // The same rules `validateSession` applies, so "active" here means the row
  // would actually authenticate a request right now.
  const now = new Date();
  const accountBlocked = !user.isActive || !!user.suspendedAt || !!user.softDeletedAt;
  const sessions = rows.map((r) => {
    const status: AdminSessionStatus =
      r.expiresAt <= now
        ? 'expired'
        : accountBlocked || (user.forceLogoutAt && user.forceLogoutAt > r.createdAt)
          ? 'invalidated'
          : 'active';
    return {
      id: r.id,
      ipAddress: r.ipAddress ?? null,
      userAgent: r.userAgent ?? null,
      createdAt: r.createdAt.toISOString(),
      lastActiveAt: r.lastActiveAt.toISOString(),
      expiresAt: r.expiresAt.toISOString(),
      status,
    };
  });

  return NextResponse.json({ ok: true, sessions });
});
