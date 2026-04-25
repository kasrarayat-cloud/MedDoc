// ============================================================================
// /admin/users — server-side data layer
// ----------------------------------------------------------------------------
// One Prisma round-trip per query, never N+1. The page-list spend rollup
// in particular runs as a single GROUP BY across the page's user IDs,
// not one query per user.
//
// Pagination is offset-based (page 1..N) to match the design's "Page X
// of Y" + Prev/Next buttons. The existing /api/admin/users endpoint is
// cursor-based — we don't reuse it here because the design needs an
// addressable page number, and going cursor → page index would require
// counting pages anyway.
// ============================================================================

import 'server-only';

import prisma from '@meddoc/db';

import { defaultUnitLabel } from '../../_lib/admin-format';
import type {
  ListParams,
  UserListPage,
  UserListRow,
  UserRoleLabel,
  UserStats,
  UserStatus,
} from '../_types';

const PAGE_SIZE = 20;

export async function fetchUserStats(): Promise<UserStats> {
  // Counts exclude soft-deleted users for the stats strip — those rows
  // exist in the DB for HIPAA retention but they're not part of the
  // "active platform population" headline number.
  const [total, admins, suspended] = await Promise.all([
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (prisma.user as any).count({ where: { softDeletedAt: null } }),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (prisma.user as any).count({
      where: { softDeletedAt: null, products: { has: 'SUPER_ADMIN' } },
    }),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (prisma.user as any).count({
      where: { softDeletedAt: null, suspendedAt: { not: null } },
    }),
  ]);
  return { total, admins, suspended };
}

interface RawUserRow {
  id: string;
  email: string;
  name: string | null;
  role: string;
  products: string[];
  practiceId: string;
  createdAt: Date;
  lastLogin: Date | null;
  lastLoginIp: string | null;
  suspendedAt: Date | null;
  suspendedReason: string | null;
  softDeletedAt: Date | null;
  softDeletedBy: string | null;
  practice_name: string;
}

interface SpendRow {
  userId: string;
  provider: string;
  total: number;
  unit_count: number;
}
interface VisitRow {
  userId: string;
  n: bigint;
}
interface SessionRow {
  userId: string;
  n: bigint;
}

export async function fetchUserListPage(p: ListParams): Promise<UserListPage> {
  const page = Math.max(1, Math.floor(p.page) || 1);
  const offset = (page - 1) * PAGE_SIZE;

  // Build the WHERE in raw SQL — Prisma's where-builder doesn't compose
  // cleanly with the `products: { has: ... }` array filter alongside our
  // search + status mix without a lot of conditional spread.
  const where: string[] = [];
  const params: unknown[] = [];

  if (p.status === 'active') {
    where.push(`u."suspendedAt" IS NULL`, `u."softDeletedAt" IS NULL`);
  } else if (p.status === 'suspended') {
    where.push(`u."suspendedAt" IS NOT NULL`, `u."softDeletedAt" IS NULL`);
  } else if (p.status === 'deleted') {
    where.push(`u."softDeletedAt" IS NOT NULL`);
  }
  // status === 'all' shows everything including soft-deleted (matches the
  // design — admin can see the whole population).

  if (p.role === 'admin') {
    where.push(`'SUPER_ADMIN' = ANY(u.products)`);
  } else if (p.role === 'doctor') {
    where.push(`NOT ('SUPER_ADMIN' = ANY(u.products))`);
  }

  if (p.search.trim()) {
    const q = `%${p.search.trim()}%`;
    params.push(q, q, q);
    const a = `$${params.length - 2}`;
    const b = `$${params.length - 1}`;
    const c = `$${params.length}`;
    where.push(`(u.email ILIKE ${a} OR u.name ILIKE ${b} OR pr.name ILIKE ${c})`);
  }
  const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';

  // Two queries: count + page rows. Composing them as one CTE is
  // possible but doesn't measurably help here.
  const countQuery = `
    SELECT COUNT(*)::int AS n
    FROM users u
    JOIN practices pr ON pr.id = u."practiceId"
    ${whereClause}
  `;
  const rowsQuery = `
    SELECT
      u.id, u.email, u.name, u.role::text AS role,
      u.products::text[] AS products,
      u."practiceId", u."createdAt", u."lastLogin", u."lastLoginIp",
      u."suspendedAt", u."suspendedReason",
      u."softDeletedAt", u."softDeletedBy",
      pr.name AS practice_name
    FROM users u
    JOIN practices pr ON pr.id = u."practiceId"
    ${whereClause}
    ORDER BY u."createdAt" DESC, u.id DESC
    LIMIT ${PAGE_SIZE}
    OFFSET ${offset}
  `;

  const [countRows, userRows] = (await Promise.all([
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (prisma as any)
      .$queryRawUnsafe(countQuery, ...params)
      .catch(() => [{ n: 0 }]),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (prisma as any)
      .$queryRawUnsafe(rowsQuery, ...params)
      .catch(() => []),
  ])) as [{ n: number }[], RawUserRow[]];

  const totalCount = countRows[0]?.n ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const ids = userRows.map((r: RawUserRow) => r.id);

  // Per-page rollups — each is ONE query no matter how big the page.
  const monthStart = firstOfCurrentMonthUTC();
  const [spendRows, visitRows, sessionRows] = await Promise.all([
    ids.length === 0
      ? Promise.resolve([] as SpendRow[])
      : prisma.$queryRaw<SpendRow[]>`
          SELECT "userId",
                 provider,
                 SUM("totalCostUsd")::float AS total,
                 SUM("unitCount")::float    AS unit_count
          FROM api_usage_events
          WHERE "userId" = ANY(${ids}::text[])
            AND timestamp >= ${monthStart}
          GROUP BY "userId", provider
        `.catch(() => [] as SpendRow[]),
    ids.length === 0
      ? Promise.resolve([] as VisitRow[])
      : prisma.$queryRaw<VisitRow[]>`
          SELECT "userId", COUNT(*)::bigint AS n
          FROM transcribe_visits
          WHERE "userId" = ANY(${ids}::text[])
            AND "createdAt" >= ${monthStart}
          GROUP BY "userId"
        `.catch(() => [] as VisitRow[]),
    ids.length === 0
      ? Promise.resolve([] as SessionRow[])
      : prisma.$queryRaw<SessionRow[]>`
          SELECT "userId", COUNT(*)::bigint AS n
          FROM user_sessions
          WHERE "userId" = ANY(${ids}::text[])
            AND "expiresAt" > NOW()
          GROUP BY "userId"
        `.catch(() => [] as SessionRow[]),
  ]);

  // Index the rollups by userId.
  const spendByUser = new Map<
    string,
    {
      totalCostUsd: number;
      byProvider: Record<string, { costUsd: number; unitCount: number; unitLabel: string }>;
    }
  >();
  for (const r of spendRows) {
    const e =
      spendByUser.get(r.userId) ?? {
        totalCostUsd: 0,
        byProvider: {} as Record<string, { costUsd: number; unitCount: number; unitLabel: string }>,
      };
    const cost = Number(r.total ?? 0);
    e.totalCostUsd += cost;
    e.byProvider[r.provider] = {
      costUsd: cost,
      unitCount: Number(r.unit_count ?? 0),
      unitLabel: defaultUnitLabel(r.provider),
    };
    spendByUser.set(r.userId, e);
  }
  const visitsByUser = new Map<string, number>();
  for (const v of visitRows) visitsByUser.set(v.userId, Number(v.n ?? 0));
  const sessionsByUser = new Map<string, number>();
  for (const s of sessionRows) sessionsByUser.set(s.userId, Number(s.n ?? 0));

  const users: UserListRow[] = userRows.map((r: RawUserRow) => {
    const isSuperAdmin = (r.products ?? []).includes('SUPER_ADMIN');
    const baseRole = (r.role ?? 'DOCTOR') as 'DOCTOR' | 'ADMIN' | 'STAFF';
    const roleLabel: UserRoleLabel = isSuperAdmin
      ? baseRole === 'ADMIN'
        ? 'ADMIN'
        : baseRole === 'STAFF'
          ? 'STAFF+ADMIN'
          : 'DOCTOR+ADMIN'
      : baseRole;
    const status: UserStatus = r.softDeletedAt
      ? 'soft_deleted'
      : r.suspendedAt
        ? 'suspended'
        : 'active';
    const spend = spendByUser.get(r.id) ?? { totalCostUsd: 0, byProvider: {} };
    return {
      id: r.id,
      email: r.email,
      fullName: r.name?.trim() || r.email,
      role: roleLabel,
      isSuperAdmin,
      products: r.products ?? [],
      status,
      suspendedReason: r.suspendedReason,
      softDeletedAt: r.softDeletedAt?.toISOString() ?? null,
      softDeletedBy: r.softDeletedBy,
      practiceId: r.practiceId,
      practiceName: r.practice_name,
      createdAt: r.createdAt.toISOString(),
      lastLoginAt: r.lastLogin?.toISOString() ?? null,
      lastLoginIp: r.lastLoginIp,
      activeSessions: sessionsByUser.get(r.id) ?? 0,
      monthSpend: {
        totalCostUsd: round4(spend.totalCostUsd),
        byProvider: spend.byProvider,
      },
      monthVisits: visitsByUser.get(r.id) ?? 0,
    };
  });

  return { users, totalPages, totalCount, page };
}

function firstOfCurrentMonthUTC(): Date {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
}

function round4(n: number): number {
  return Math.round(n * 10_000) / 10_000;
}
