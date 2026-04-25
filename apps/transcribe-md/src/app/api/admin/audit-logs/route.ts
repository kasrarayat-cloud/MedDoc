// ============================================================================
// GET /api/admin/audit-logs — paginated audit-log feed
// ----------------------------------------------------------------------------
// Query params (all optional):
//   limit       — 1..200 (default 50)
//   cursor      — opaque ISO string from previous response's nextCursor
//   action      — filter by enum value (any AuditAction)
//   userId      — filter by actor (user that performed the action)
//   targetType  — filter by resource type ("TranscribeVisit", "User", ...)
//   since       — ISO timestamp inclusive lower bound
//   until       — ISO timestamp exclusive upper bound
//   success     — "true" or "false"
//
// Response:
//   { logs: AuditLogRow[], nextCursor: string | null, hasMore: boolean }
//
// Cursor design: the cursor is the timestamp+id of the last row in the
// previous page (encoded as `${timestamp}|${id}`). We page by
// (timestamp DESC, id DESC) so even rows with the exact same ms-timestamp
// are stable across pages. Order matches `audit_logs_timestamp_idx`.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, type AuditAction } from '@prisma/client';

import { adminApi } from '@/lib/admin-api-gate';

const QuerySchema = z.object({
  limit: z
    .string()
    .optional()
    .transform((s) => {
      const n = s ? Number.parseInt(s, 10) : 50;
      if (!Number.isFinite(n) || n < 1) return 50;
      return Math.min(n, 200);
    }),
  cursor: z.string().optional(),
  action: z.string().optional(),
  userId: z.string().optional(),
  targetType: z.string().optional(),
  since: z.string().optional(),
  until: z.string().optional(),
  success: z.enum(['true', 'false']).optional(),
});

interface AuditLogRow {
  id: string;
  timestamp: string;
  action: string;
  userId: string | null;
  userEmail: string | null;
  targetType: string | null;
  targetId: string | null;
  success: boolean;
  errorCode: string | null;
  metadata: unknown;
  ipAddress: string | null;
  userAgent: string | null;
}

function parseCursor(s: string | undefined):
  | { timestamp: Date; id: string }
  | null {
  if (!s) return null;
  const idx = s.lastIndexOf('|');
  if (idx < 1) return null;
  const ts = s.slice(0, idx);
  const id = s.slice(idx + 1);
  const d = new Date(ts);
  if (Number.isNaN(d.getTime()) || !id) return null;
  return { timestamp: d, id };
}

function makeCursor(row: { timestamp: Date; id: string }): string {
  return `${row.timestamp.toISOString()}|${row.id}`;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('audit-logs:list', async (req) => {
  const url = new URL(req.url);
  const params = QuerySchema.safeParse({
    limit: url.searchParams.get('limit') ?? undefined,
    cursor: url.searchParams.get('cursor') ?? undefined,
    action: url.searchParams.get('action') ?? undefined,
    userId: url.searchParams.get('userId') ?? undefined,
    targetType: url.searchParams.get('targetType') ?? undefined,
    since: url.searchParams.get('since') ?? undefined,
    until: url.searchParams.get('until') ?? undefined,
    success: url.searchParams.get('success') ?? undefined,
  });
  if (!params.success) {
    return NextResponse.json(
      { error: 'Invalid query parameters' },
      { status: 400 }
    );
  }
  const q = params.data;

  // Compose the where clause. Prisma's strong typing for AuditAction
  // means we have to cast `q.action` after a soft validation — invalid
  // enum strings get caught by Postgres as a type-mismatch error.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const where: any = {};
  if (q.action) where.action = q.action as AuditAction;
  if (q.userId) where.userId = q.userId;
  if (q.targetType) where.targetType = q.targetType;
  if (q.success === 'true') where.success = true;
  if (q.success === 'false') where.success = false;
  if (q.since || q.until) {
    where.timestamp = {} as { gte?: Date; lt?: Date };
    if (q.since) {
      const d = new Date(q.since);
      if (Number.isNaN(d.getTime())) {
        return NextResponse.json({ error: 'Invalid `since`' }, { status: 400 });
      }
      where.timestamp.gte = d;
    }
    if (q.until) {
      const d = new Date(q.until);
      if (Number.isNaN(d.getTime())) {
        return NextResponse.json({ error: 'Invalid `until`' }, { status: 400 });
      }
      where.timestamp.lt = d;
    }
  }

  // Cursor — order is (timestamp DESC, id DESC). The "last seen" cursor
  // means "next page should be strictly older than this".
  const cur = parseCursor(q.cursor);
  if (cur) {
    // Tuple comparison via a raw OR — Prisma doesn't have a clean
    // tuple compare. Either timestamp is strictly older, OR same
    // timestamp with id strictly less.
    where.OR = [
      { timestamp: { lt: cur.timestamp } },
      { timestamp: cur.timestamp, id: { lt: cur.id } },
    ];
  }

  // Fetch limit+1 — peek at the next page boundary without a second query.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = await prisma.auditLog.findMany({
    where,
    orderBy: [{ timestamp: 'desc' }, { id: 'desc' }],
    take: q.limit + 1,
  });

  const hasMore = rows.length > q.limit;
  const page = hasMore ? rows.slice(0, q.limit) : rows;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const logs: AuditLogRow[] = page.map((r: any) => ({
    id: r.id,
    timestamp: r.timestamp.toISOString(),
    action: r.action,
    userId: r.userId ?? null,
    userEmail: r.userEmailSnapshot ?? null,
    targetType: r.targetType ?? null,
    targetId: r.targetId ?? null,
    success: r.success ?? true,
    errorCode: r.errorCode ?? null,
    metadata: r.metadata ?? null,
    ipAddress: r.ipAddress ?? null,
    userAgent: r.userAgent ?? null,
  }));

  const nextCursor =
    hasMore && page.length > 0
      ? makeCursor({
          timestamp: new Date(page[page.length - 1]!.timestamp),
          id: page[page.length - 1]!.id,
        })
      : null;

  return NextResponse.json({ logs, nextCursor, hasMore });
});

// Suppress an unused-import warning if Prisma is exported as *.
void Prisma;
