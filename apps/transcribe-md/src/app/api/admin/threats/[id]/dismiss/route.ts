// ============================================================================
// POST /api/admin/threats/[id]/dismiss — Phase 6H mark-false-positive
// ----------------------------------------------------------------------------
// Same shape as /resolve except resolutionKind=FALSE_POSITIVE and an
// optional silencePattern that future detector runs apply to suppress
// similar threats. The pattern shape per type is documented in
// dashboard-data.ts (matchesSilencePattern).
//
// We auto-derive the pattern when `silenceSimilar=true` so the UI
// doesn't have to re-implement that logic. Admin can still pass an
// explicit `silencePattern` to override.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

export const dynamic = 'force-dynamic';

const Body = z.object({
  note: z.string().trim().min(1).max(2000).optional(),
  silenceSimilar: z.boolean().optional(),
  silencePattern: z.record(z.string(), z.unknown()).optional(),
});

export const POST = adminApi('threats:dismiss', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const idIdx = segs.indexOf('threats') + 1;
  const rawId = segs[idIdx];
  if (!rawId) return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  const threatId = decodeURIComponent(rawId);

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body must be { note?, silenceSimilar?, silencePattern? }' },
      { status: 400 }
    );
  }
  const note = parsed.data.note ?? null;

  let silencePattern: Record<string, unknown> | null = null;
  if (parsed.data.silencePattern) {
    silencePattern = parsed.data.silencePattern;
  } else if (parsed.data.silenceSimilar) {
    silencePattern = derivePatternFromId(threatId);
  }

  try {
    const row = await prisma.threatResolution.create({
      data: {
        threatId,
        resolutionKind: 'FALSE_POSITIVE',
        resolvedById: ctx.session.user.id,
        resolvedByEmail: ctx.session.user.email,
        note,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        silencePattern: (silencePattern ?? undefined) as any,
      },
      select: { id: true, resolvedAt: true },
    });

    await logAudit({
      action: 'THREAT_DISMISSED_FALSE_POSITIVE',
      targetType: 'Threat',
      targetId: threatId,
      metadata: {
        resolutionId: row.id,
        actorEmail: ctx.session.user.email,
        note,
        silencePattern,
      },
    });

    return NextResponse.json({
      ok: true,
      resolutionId: row.id,
      resolvedAt: row.resolvedAt.toISOString(),
      silencePattern,
    });
  } catch (err) {
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

function derivePatternFromId(threatId: string): Record<string, unknown> | null {
  const parts = threatId.split(':');
  switch (parts[0]) {
    case 'burst':
      return parts[1]
        ? { type: 'failed_login_burst', ipAddress: parts[1] }
        : null;
    case 'cross':
      return parts[1]
        ? { type: 'cross_tenant_attempts', userId: parts[1] }
        : null;
    case 'bulk':
      return parts[1] ? { type: 'bulk_phi_access', userId: parts[1] } : null;
    case 'xdom':
      // For external-domain dismissals, default to silencing the
      // (userId, domain) pair — usually what a "this is fine" means.
      return parts[1] && parts.length >= 3
        ? {
            type: 'export_to_external_domain',
            userId: parts[1],
            domain: parts.slice(2).join(':'),
          }
        : null;
    case 'grant-admin':
      // Privilege grants can't be silenced by class — every grant is
      // its own review-worthy event. Pattern stays null.
      return null;
    case 'volume-spike':
      // Phase 8 — Detector 4. Silence per-user (covers a doctor with
      // a legitimately high baseline). Today's daily key isn't
      // useful in the silence pattern — the goal is "this user is
      // expected to spike again tomorrow", not "this exact day".
      return parts[1]
        ? { type: 'volume_spike', userId: parts[1] }
        : null;
    default:
      return null;
  }
}
