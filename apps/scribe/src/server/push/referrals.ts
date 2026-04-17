// ============================================================================
// Push — Referral letters → MedDoc Pro Documents (M6)
// ----------------------------------------------------------------------------
// Reuses the Document table with procedureType='Referral Letter' per D2.
// Idempotent on the target side via the composite unique on
// (sourceScribeOutputId, sourceItemIndex).
// ============================================================================

import {
  ReferralOutputSchema,
  type CreateReferralsRequest,
  type CreateReferralsResponse,
} from '@meddoc/types';
import { pushFetch } from './http';
import type { PushOutcome } from './types';

export interface RunReferralsPushArgs {
  patientId: string;
  sourceVisitId: string;
  sourceScribeOutputId: string;
  clinicianUserId: string;
  rawContent: unknown;
}

export async function runReferralsPush(
  args: RunReferralsPushArgs
): Promise<PushOutcome> {
  const parsed = ReferralOutputSchema.safeParse(args.rawContent);
  if (!parsed.success) {
    return {
      target: 'referrals',
      status: 'skipped',
      reason: 'Referral output is missing or stored as an error sentinel.',
    };
  }
  if (parsed.data.referrals.length === 0) {
    return {
      target: 'referrals',
      status: 'skipped',
      reason: 'No referrals drafted for this visit.',
    };
  }

  const body: CreateReferralsRequest = {
    sourceVisitId: args.sourceVisitId,
    sourceScribeOutputId: args.sourceScribeOutputId,
    patientId: args.patientId,
    clinicianUserId: args.clinicianUserId,
    letters: parsed.data.referrals,
  };

  const result = await pushFetch<CreateReferralsResponse>({
    method: 'POST',
    path: '/api/internal/referrals',
    body,
  });

  if (!result.ok) {
    return {
      target: 'referrals',
      status: 'error',
      message: result.message || `status ${result.status}`,
      httpStatus: result.status,
    };
  }
  return {
    target: 'referrals',
    status: 'ok',
    summary: `${result.data.documentIds.length} referral letter(s) added to chart.`,
    createdIds: result.data.documentIds,
  };
}
