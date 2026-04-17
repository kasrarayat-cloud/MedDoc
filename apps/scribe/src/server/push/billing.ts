// ============================================================================
// Push — ICD-10 + CPT coding → BillingEvent (M6)
// ----------------------------------------------------------------------------
// Invoked per signed visit when the ICD10_CPT ScribeOutput content parses
// as a valid CodingOutput. Best-effort: failures don't block SIGNED.
// ============================================================================

import {
  CodingOutputSchema,
  type CreateBillingEventRequest,
  type CreateBillingEventResponse,
} from '@meddoc/types';
import { pushFetch } from './http';
import type { PushOutcome } from './types';

export interface RunBillingPushArgs {
  patientId: string;
  sourceVisitId: string;
  sourceScribeOutputId: string;
  clinicianUserId: string;
  rawContent: unknown; // ScribeOutput.content blob
}

export async function runBillingPush(
  args: RunBillingPushArgs
): Promise<PushOutcome> {
  const parsed = CodingOutputSchema.safeParse(args.rawContent);
  if (!parsed.success) {
    return {
      target: 'billing',
      status: 'skipped',
      reason: 'Coding output is missing or stored as an error sentinel.',
    };
  }
  if (parsed.data.icd10.length === 0 && parsed.data.cpt.length === 0) {
    return {
      target: 'billing',
      status: 'skipped',
      reason: 'No codes to bill — both ICD-10 and CPT arrays empty.',
    };
  }

  const body: CreateBillingEventRequest = {
    sourceVisitId: args.sourceVisitId,
    sourceScribeOutputId: args.sourceScribeOutputId,
    clinicianUserId: args.clinicianUserId,
    coding: parsed.data,
  };

  const result = await pushFetch<CreateBillingEventResponse>({
    method: 'POST',
    path: `/api/internal/patients/${args.patientId}/billing-events`,
    body,
  });

  if (!result.ok) {
    return {
      target: 'billing',
      status: 'error',
      message: result.message || `status ${result.status}`,
      httpStatus: result.status,
    };
  }
  return {
    target: 'billing',
    status: 'ok',
    summary: `Billing event created (${parsed.data.icd10.length} ICD-10, ${parsed.data.cpt.length} CPT).`,
    createdIds: [result.data.billingEventId],
  };
}
