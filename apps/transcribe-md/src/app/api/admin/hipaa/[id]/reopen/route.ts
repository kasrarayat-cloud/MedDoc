// ============================================================================
// POST /api/admin/hipaa/[id]/reopen — Phase 7B undo a resolution
// ----------------------------------------------------------------------------
// Clears status back to 'open' and wipes resolvedAt/resolvedById/
// resolvedByEmail/resolutionNote so the finding looks fresh again.
// Writes a HIPAA_FINDING_REOPENED audit row carrying the prior
// resolver's email + the original resolution note for the trail.
//
// 409 if the finding isn't currently resolved.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

export const dynamic = 'force-dynamic';

export const POST = adminApi('hipaa:reopen', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('hipaa') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const existing: any = await (prisma as any).hipaaFinding.findUnique({
    where: { id },
    select: {
      id: true,
      status: true,
      title: true,
      severity: true,
      control: true,
      resolvedByEmail: true,
      resolutionNote: true,
    },
  });
  if (!existing) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  if (existing.status !== 'resolved') {
    return NextResponse.json({ error: 'Finding is not currently resolved' }, { status: 409 });
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma as any).hipaaFinding.update({
    where: { id },
    data: {
      status: 'open',
      resolvedAt: null,
      resolvedById: null,
      resolvedByEmail: null,
      resolutionNote: null,
    },
  });

  await logAudit({
    action: 'HIPAA_FINDING_REOPENED',
    targetType: 'HipaaFinding',
    targetId: id,
    metadata: {
      control: existing.control,
      severity: existing.severity,
      title: existing.title,
      actorEmail: ctx.session.user.email,
      // Preserve the prior resolution context so the audit trail
      // shows what we're undoing.
      priorResolvedBy: existing.resolvedByEmail,
      priorResolutionNote: existing.resolutionNote,
    },
  });

  return NextResponse.json({ ok: true });
});
