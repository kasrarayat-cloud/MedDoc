// ============================================================================
// POST /api/visits/[id]/em-score (Phase 5.2)
// ----------------------------------------------------------------------------
// Body: { soapText: string }
// Response: EmScore (per types.ts)
//
// Loads the visit, validates ownership, runs the hybrid scoring engine
// (deterministic counts + LLM-judged MDM with Redis cache + fallback).
// Read-only on SOAP data — never writes back to soapNote/soapFinal.
// Coding feedback is COACHING ONLY: the engine returns scores; the
// rail decides display. The Sign action proceeds regardless.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { apiError, withApiHandler } from '@/lib/api-error';
import { computeEmScore } from '@/lib/em-coding/score';
import type { IcdCodeRow, RxDraftRow } from '@/lib/em-coding/fallback-mdm';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

const BodySchema = z.object({
  soapText: z.string().min(1).max(50_000),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:em-score',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const practiceId = session?.user?.practiceId;
    if (!userId || !practiceId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid soapText payload', 400);

    // Ownership check — 404 on any mismatch (consistent with the rest
    // of the visits API; never expose existence of a foreign visit).
    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        deletedAt: true,
        archivedAt: true,
        // Pull these for the deterministic fallback's structured signals.
        icdCodes: true,
        rxDrafts: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError('Visit is no longer active.', 400, {
        code: 'VISIT_NOT_ACTIVE',
      });
    }

    // Extract structured signals from the visit row. The Prisma JSON
    // typing is loose; we narrow at the boundary so the engine sees a
    // well-shaped array regardless of older drafts.
    const icdCodes = extractIcdCodes(visit.icdCodes);
    const rxDrafts = extractRxDrafts(visit.rxDrafts);

    const score = await computeEmScore(parsed.data.soapText, {
      practiceId,
      visitId,
      userId,
      icdCodes,
      rxDrafts,
    });

    return NextResponse.json(score, { status: 200 });
  },
);

/** The icdCodes column shape varies across migrations — Layer 7a writes
 *  `{ codes: [{ code, description, ... }] }` but legacy writes were a
 *  bare array. Normalize to IcdCodeRow[]. */
function extractIcdCodes(raw: unknown): IcdCodeRow[] {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
      .map((r) => ({
        code: typeof r.code === 'string' ? r.code : '',
        description: typeof r.description === 'string' ? r.description : undefined,
      }))
      .filter((r) => r.code.length > 0);
  }
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { codes?: unknown };
    if (Array.isArray(blob.codes)) return extractIcdCodes(blob.codes);
  }
  return [];
}

/** rxDrafts shape: `{ drafts: [{ drug, action, ... }], warnings?: [...] }`. */
function extractRxDrafts(raw: unknown): RxDraftRow[] {
  if (!raw) return [];
  if (typeof raw === 'object' && raw !== null) {
    const blob = raw as { drafts?: unknown };
    if (Array.isArray(blob.drafts)) {
      return blob.drafts
        .filter((d): d is Record<string, unknown> => !!d && typeof d === 'object')
        .map((d) => ({
          drug: typeof d.drug === 'string' ? d.drug : (typeof d.drug_name === 'string' ? d.drug_name : undefined),
          drug_name: typeof d.drug_name === 'string' ? d.drug_name : undefined,
          action: typeof d.action === 'string' ? d.action : undefined,
        }));
    }
  }
  return [];
}
