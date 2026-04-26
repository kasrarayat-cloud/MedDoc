// ============================================================================
// POST /api/admin/hipaa/[id]/resolve — Phase 7B mark finding closed
// ----------------------------------------------------------------------------
// Body: { note?: string }
//
// Sets status='resolved', stamps resolvedAt + resolvedById +
// resolvedByEmail (snapshot survives later soft-delete of the admin),
// stores the optional resolution note, and writes a HIPAA_FINDING_RESOLVED
// audit row. 409 if the finding is already resolved (idempotency at
// the workflow layer — re-resolves don't double-stamp).
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

const Body = z.object({
  note: z.string().trim().max(2000).optional(),
});

export const dynamic = 'force-dynamic';

export const POST = adminApi('hipaa:resolve', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('hipaa') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json({ error: 'Body must be { note?: string }' }, { status: 400 });
  }
  const note = parsed.data.note ?? null;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const existing: any = await (prisma as any).hipaaFinding.findUnique({
    where: { id },
    select: { id: true, status: true, title: true, severity: true, control: true },
  });
  if (!existing) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  if (existing.status === 'resolved') {
    return NextResponse.json({ error: 'Already resolved' }, { status: 409 });
  }

  const now = new Date();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma as any).hipaaFinding.update({
    where: { id },
    data: {
      status: 'resolved',
      resolvedAt: now,
      resolvedById: ctx.session.user.id,
      resolvedByEmail: ctx.session.user.email,
      resolutionNote: note,
    },
  });

  await logAudit({
    action: 'HIPAA_FINDING_RESOLVED',
    targetType: 'HipaaFinding',
    targetId: id,
    metadata: {
      control: existing.control,
      severity: existing.severity,
      title: existing.title,
      actorEmail: ctx.session.user.email,
      note,
    },
  });

  return NextResponse.json({
    ok: true,
    resolvedAt: now.toISOString(),
  });
});
