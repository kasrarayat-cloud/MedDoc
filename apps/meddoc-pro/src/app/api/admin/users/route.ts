// ============================================================================
// GET /api/admin/users — list users with summary stats
// ----------------------------------------------------------------------------
// Query params:
//   search   — substring match on email or name (case-insensitive)
//   status   — "active" | "inactive" | "locked"
//   limit    — 1..200 (default 50)
//   cursor   — opaque, "createdAt|id" of last row from previous page
//
// Response:
//   { users: [{ id, email, name, role, products, isActive, lockedUntil,
//               createdAt, lastLogin, practiceId }],
//     nextCursor, hasMore }
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

const QuerySchema = z.object({
  search: z.string().trim().min(1).max(200).optional(),
  status: z.enum(['active', 'inactive', 'locked']).optional(),
  limit: z
    .string()
    .optional()
    .transform((s) => {
      const n = s ? Number.parseInt(s, 10) : 50;
      if (!Number.isFinite(n) || n < 1) return 50;
      return Math.min(n, 200);
    }),
  cursor: z.string().optional(),
});

interface UserListRow {
  id: string;
  email: string;
  name: string | null;
  role: string;
  products: string[];
  isActive: boolean;
  lockedUntil: string | null;
  createdAt: string;
  lastLogin: string | null;
  practiceId: string;
}

function parseCursor(s: string | undefined):
  | { createdAt: Date; id: string }
  | null {
  if (!s) return null;
  const idx = s.lastIndexOf('|');
  if (idx < 1) return null;
  const ts = s.slice(0, idx);
  const id = s.slice(idx + 1);
  const d = new Date(ts);
  if (Number.isNaN(d.getTime()) || !id) return null;
  return { createdAt: d, id };
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('users:list', async (req) => {
  const url = new URL(req.url);
  const parsed = QuerySchema.safeParse({
    search: url.searchParams.get('search') ?? undefined,
    status: url.searchParams.get('status') ?? undefined,
    limit: url.searchParams.get('limit') ?? undefined,
    cursor: url.searchParams.get('cursor') ?? undefined,
  });
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid query parameters' },
      { status: 400 }
    );
  }
  const q = parsed.data;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const where: any = {};
  if (q.search) {
    where.OR = [
      { email: { contains: q.search, mode: 'insensitive' } },
      { name: { contains: q.search, mode: 'insensitive' } },
    ];
  }
  if (q.status === 'active') {
    where.isActive = true;
    where.OR = where.OR ?? [];
    where.AND = [
      { OR: [{ lockedUntil: null }, { lockedUntil: { lt: new Date() } }] },
    ];
  } else if (q.status === 'inactive') {
    where.isActive = false;
  } else if (q.status === 'locked') {
    where.lockedUntil = { gt: new Date() };
  }

  const cur = parseCursor(q.cursor);
  if (cur) {
    where.OR = [
      { createdAt: { lt: cur.createdAt } },
      { createdAt: cur.createdAt, id: { lt: cur.id } },
    ];
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = await prisma.user.findMany({
    where,
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: q.limit + 1,
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      products: true,
      isActive: true,
      lockedUntil: true,
      createdAt: true,
      lastLogin: true,
      practiceId: true,
    },
  });

  const hasMore = rows.length > q.limit;
  const page = hasMore ? rows.slice(0, q.limit) : rows;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const users: UserListRow[] = page.map((r: any) => ({
    id: r.id,
    email: r.email,
    name: r.name ?? null,
    role: String(r.role),
    products: (r.products ?? []).map(String),
    isActive: r.isActive,
    lockedUntil: r.lockedUntil?.toISOString() ?? null,
    createdAt: r.createdAt.toISOString(),
    lastLogin: r.lastLogin?.toISOString() ?? null,
    practiceId: r.practiceId,
  }));

  const last = page[page.length - 1];
  const nextCursor =
    hasMore && last
      ? `${last.createdAt.toISOString()}|${last.id}`
      : null;

  return NextResponse.json({ users, nextCursor, hasMore });
});
