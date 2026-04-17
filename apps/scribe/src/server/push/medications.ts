// ============================================================================
// Push — Rx drafts → Patient's active medications (M6)
// ----------------------------------------------------------------------------
// Invoked when RX ScribeOutput content parses as a valid RxOutput. The
// MedDoc Pro endpoint dedupes by (patientId, sourceScribeOutputId,
// lowered drug name).
// ============================================================================

import {
  RxOutputSchema,
  type AppendMedicationsRequest,
  type AppendMedicationsResponse,
} from '@meddoc/types';
import { pushFetch } from './http';
import type { PushOutcome } from './types';

export interface RunMedicationsPushArgs {
  patientId: string;
  sourceVisitId: string;
  sourceScribeOutputId: string;
  clinicianUserId: string;
  rawContent: unknown;
}

export async function runMedicationsPush(
  args: RunMedicationsPushArgs
): Promise<PushOutcome> {
  const parsed = RxOutputSchema.safeParse(args.rawContent);
  if (!parsed.success) {
    return {
      target: 'medications',
      status: 'skipped',
      reason: 'Rx output is missing or stored as an error sentinel.',
    };
  }
  if (parsed.data.prescriptions.length === 0) {
    return {
      target: 'medications',
      status: 'skipped',
      reason: 'No prescriptions drafted for this visit.',
    };
  }

  const body: AppendMedicationsRequest = {
    sourceVisitId: args.sourceVisitId,
    sourceScribeOutputId: args.sourceScribeOutputId,
    clinicianUserId: args.clinicianUserId,
    prescriptions: parsed.data.prescriptions,
  };

  const result = await pushFetch<AppendMedicationsResponse>({
    method: 'POST',
    path: `/api/internal/patients/${args.patientId}/medications`,
    body,
  });

  if (!result.ok) {
    return {
      target: 'medications',
      status: 'error',
      message: result.message || `status ${result.status}`,
      httpStatus: result.status,
    };
  }
  const added = result.data.medicationIds.length - result.data.dedupedCount;
  const summary =
    result.data.dedupedCount > 0
      ? `${added} medication(s) added to active list, ${result.data.dedupedCount} deduped.`
      : `${added} medication(s) added to active list.`;
  return {
    target: 'medications',
    status: 'ok',
    summary,
    createdIds: result.data.medicationIds,
  };
}
