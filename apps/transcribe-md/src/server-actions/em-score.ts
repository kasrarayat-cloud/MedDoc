'use server';

// ============================================================================
// server action: computeEmScoreAction (Phase 5.2)
// ----------------------------------------------------------------------------
// Mirror of the POST /api/visits/[id]/em-score route handler, exposed
// as a Next.js server action so React Server Components can invoke the
// engine without a fetch round-trip. Loads the visit + structured
// signals from Prisma and delegates to computeEmScore().
//
// Read-only — does not mutate the visit. Coding feedback is COACHING
// ONLY (Sign proceeds regardless of score).
// ============================================================================

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';
import { computeEmScore } from '@/lib/em-coding/score';
import type { EmScore } from '@/lib/em-coding/types';
import type { IcdCodeRow, RxDraftRow } from '@/lib/em-coding/fallback-mdm';

export interface EmScoreActionResult {
  ok: boolean;
  score?: EmScore;
  error?: string;
}

export async function computeEmScoreAction(
  visitId: string,
): Promise<EmScoreActionResult> {
  const session = await requireSession();
  const userId = session.user.id;
  const practiceId = session.user.practiceId;

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      soapFinal: true,
      signedSoap: true,
      deletedAt: true,
      archivedAt: true,
      icdCodes: true,
      rxDrafts: true,
    },
  });
  if (!visit || visit.userId !== userId) {
    return { ok: false, error: 'Visit not found.' };
  }
  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return { ok: false, error: 'Visit is no longer active.' };
  }
  // Score the SIGNED copy when available (frozen authoritative text);
  // otherwise the live draft.
  const soap = visit.signedSoap ?? visit.soapFinal;
  if (!soap?.trim()) {
    return { ok: false, error: 'Visit has no SOAP content to score.' };
  }

  const icdCodes = extractIcdCodes(visit.icdCodes);
  const rxDrafts = extractRxDrafts(visit.rxDrafts);

  const score = await computeEmScore(soap, {
    practiceId,
    visitId,
    userId,
    icdCodes,
    rxDrafts,
  });

  return { ok: true, score };
}

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
