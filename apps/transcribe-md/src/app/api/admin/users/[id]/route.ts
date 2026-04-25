// ============================================================================
// GET /api/admin/users/[id] — detailed view of a single user
// ----------------------------------------------------------------------------
// Returns the user record plus three derived bundles for the admin view:
//
//   recentActivity  — last 50 audit_logs rows for this userId
//   ipHistory       — distinct ipAddresses they've used (with first/last seen)
//   activeSessions  — count of UserSession rows still considered active
//
// All practice-unscoped (admin sees everything).
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

export const dynamic = 'force-dynamic';

export const GET = adminApi('users:detail', async (req) => {
  // Pull id from the path. Next.js's App Router gives us
  // req.url; parsing the path keeps the route file segregated
  // from the gate's NextRequest typing.
  const url = new URL(req.url);
  const segments = url.pathname.split('/').filter(Boolean);
  const id = segments[segments.length - 1];
  if (!id) {
    return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userRow: any = await prisma.user.findUnique({
    where: { id },
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      products: true,
      isActive: true,
      lockedUntil: true,
      failedLoginCount: true,
      createdAt: true,
      lastLogin: true,
      lastLoginIp: true,
      practiceId: true,
      mfaEnabled: true,
      specialty: true,
      npi: true,
      timeZone: true,
    },
  });
  if (!userRow) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const [recentActivityRaw, ipHistoryRaw, activeSessionsCount] =
    await Promise.all([
      prisma.auditLog.findMany({
        where: { userId: id },
        orderBy: [{ timestamp: 'desc' }, { id: 'desc' }],
        take: 50,
        select: {
          id: true,
          timestamp: true,
          action: true,
          targetType: true,
          targetId: true,
          success: true,
          errorCode: true,
          ipAddress: true,
          metadata: true,
        },
      }),
      prisma.$queryRaw<
        { ip: string; first_seen: Date; last_seen: Date; count: bigint }[]
      >`
        SELECT
          "ipAddress"::text AS ip,
          MIN("timestamp") AS first_seen,
          MAX("timestamp") AS last_seen,
          COUNT(*)::bigint AS count
        FROM audit_logs
        WHERE "userId" = ${id} AND "ipAddress" IS NOT NULL
        GROUP BY 1
        ORDER BY last_seen DESC
        LIMIT 25
      `,
      // UserSession rows that are still active = revokedAt IS NULL.
      // The schema lives in the @meddoc/auth package; not all
      // workspaces have a Prisma type for it, so we count via the
      // user_sessions table directly.
      prisma.$queryRaw<{ n: bigint }[]>`
        SELECT COUNT(*)::bigint AS n
        FROM user_sessions
        WHERE "userId" = ${id} AND "revokedAt" IS NULL
      `.catch(() => [{ n: BigInt(0) }] as { n: bigint }[]),
    ]);

  const user = {
    id: userRow.id,
    email: userRow.email,
    name: userRow.name ?? null,
    role: String(userRow.role),
    products: (userRow.products ?? []).map(String),
    isActive: userRow.isActive,
    lockedUntil: userRow.lockedUntil?.toISOString() ?? null,
    failedLoginCount: userRow.failedLoginCount,
    createdAt: userRow.createdAt.toISOString(),
    lastLogin: userRow.lastLogin?.toISOString() ?? null,
    lastLoginIp: userRow.lastLoginIp ?? null,
    practiceId: userRow.practiceId,
    mfaEnabled: userRow.mfaEnabled,
    specialty: userRow.specialty ?? null,
    npi: userRow.npi ?? null,
    timeZone: userRow.timeZone ?? null,
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recentActivity = (recentActivityRaw as any[]).map((r: any) => ({
    id: r.id,
    timestamp: r.timestamp.toISOString(),
    action: r.action,
    targetType: r.targetType ?? null,
    targetId: r.targetId ?? null,
    success: r.success ?? true,
    errorCode: r.errorCode ?? null,
    ipAddress: r.ipAddress ?? null,
    metadata: r.metadata ?? null,
  }));

  const ipHistory = ipHistoryRaw.map((r: { ip: string; first_seen: Date; last_seen: Date; count: bigint }) => ({
    ipAddress: r.ip,
    firstSeen: r.first_seen.toISOString(),
    lastSeen: r.last_seen.toISOString(),
    count: Number(r.count),
  }));

  const activeSessions = Number(activeSessionsCount[0]?.n ?? 0);

  return NextResponse.json({
    user,
    recentActivity,
    ipHistory,
    activeSessions,
  });
});
