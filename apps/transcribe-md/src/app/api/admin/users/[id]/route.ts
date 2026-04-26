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
  const userRow: any = await (prisma.user as any).findUnique({
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
      // Phase 6 — admin lifecycle flags
      suspendedAt: true,
      suspendedBy: true,
      suspendedReason: true,
      softDeletedAt: true,
      softDeletedBy: true,
      forceLogoutAt: true,
    },
  });
  if (!userRow) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  // Phase 6 — current calendar-month API spend for this user, computed
  // alongside the other rollups so the User detail drawer renders in
  // a single round-trip.
  const monthStart = new Date(
    Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)
  );

  const [recentActivityRaw, ipHistoryRaw, activeSessionsCount, monthSpendRows] =
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
      // Phase 6Z fix: the original query referenced a non-existent
      // `revokedAt` column on user_sessions (the schema only has
      // expiresAt — sessions are deleted, not flagged). The .catch()
      // silently swallowed the column-doesn't-exist error so this
      // count was always 0 in the API response (and therefore always
      // 0 in the User detail drawer). Now matches users-data.ts which
      // already uses the correct `expiresAt > NOW()` predicate.
      prisma.$queryRaw<{ n: bigint }[]>`
        SELECT COUNT(*)::bigint AS n
        FROM user_sessions
        WHERE "userId" = ${id} AND "expiresAt" > NOW()
      `.catch(() => [{ n: BigInt(0) }] as { n: bigint }[]),
      prisma.$queryRaw<{ provider: string; total: number }[]>`
        SELECT provider, SUM("totalCostUsd")::float AS total
        FROM api_usage_events
        WHERE "userId" = ${id} AND timestamp >= ${monthStart}
        GROUP BY provider
      `.catch(
        () => [] as { provider: string; total: number }[]
      ),
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
    // Phase 6 — admin lifecycle state
    suspendedAt: userRow.suspendedAt?.toISOString() ?? null,
    suspendedBy: userRow.suspendedBy ?? null,
    suspendedReason: userRow.suspendedReason ?? null,
    softDeletedAt: userRow.softDeletedAt?.toISOString() ?? null,
    softDeletedBy: userRow.softDeletedBy ?? null,
    forceLogoutAt: userRow.forceLogoutAt?.toISOString() ?? null,
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

  const monthSpend = {
    totalCostUsd: 0,
    byProvider: {} as Record<string, number>,
  };
  for (const row of monthSpendRows) {
    const cost = Number(row.total ?? 0);
    monthSpend.totalCostUsd += cost;
    monthSpend.byProvider[row.provider] = cost;
  }
  monthSpend.totalCostUsd =
    Math.round(monthSpend.totalCostUsd * 10_000) / 10_000;
  for (const k of Object.keys(monthSpend.byProvider)) {
    monthSpend.byProvider[k] =
      Math.round(monthSpend.byProvider[k]! * 10_000) / 10_000;
  }

  return NextResponse.json({
    user,
    recentActivity,
    ipHistory,
    activeSessions,
    monthSpend,
  });
});
