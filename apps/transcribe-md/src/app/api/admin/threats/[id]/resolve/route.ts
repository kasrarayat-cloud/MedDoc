// ============================================================================
// POST /api/admin/threats/[id]/resolve — Phase 6H mark-resolved
// ----------------------------------------------------------------------------
// Persists a ThreatResolution(RESOLVED) row keyed by the deterministic
// threat id, then writes a THREAT_RESOLVED audit row. Idempotent at the
// DB layer via the unique constraint on threatId — a duplicate POST
// returns 409 instead of orphaning a second row.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

export const dynamic = 'force-dynamic';

const Body = z.object({
  note: z.string().trim().min(1).max(2000).optional(),
});

export const POST = adminApi('threats:resolve', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const idIdx = segs.indexOf('threats') + 1;
  const rawId = segs[idIdx];
  if (!rawId) return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  const threatId = decodeURIComponent(rawId);

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body must be { note?: string }' },
      { status: 400 }
    );
  }
  const note = parsed.data.note ?? null;

  try {
    const row = await prisma.threatResolution.create({
      data: {
        threatId,
        resolutionKind: 'RESOLVED',
        resolvedById: ctx.session.user.id,
        resolvedByEmail: ctx.session.user.email,
        note,
      },
      select: { id: true, resolvedAt: true },
    });

    await logAudit({
      action: 'THREAT_RESOLVED',
      targetType: 'Threat',
      targetId: threatId,
      metadata: {
        resolutionId: row.id,
        actorEmail: ctx.session.user.email,
        note,
      },
    });

    return NextResponse.json({
      ok: true,
      resolutionId: row.id,
      resolvedAt: row.resolvedAt.toISOString(),
    });
  } catch (err) {
    // Unique-constraint violation = already resolved/dismissed. Treat
    // as a soft conflict so the UI can render a friendly message.
    if (
      err &&
      typeof err === 'object' &&
      'code' in err &&
      (err as { code?: string }).code === 'P2002'
    ) {
      return NextResponse.json(
        { error: 'Threat already resolved or dismissed' },
        { status: 409 }
      );
    }
    throw err;
  }
});
