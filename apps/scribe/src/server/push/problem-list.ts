// ============================================================================
// Push — SOAP.assessment → Patient.briefHistory (M6)
// ----------------------------------------------------------------------------
// Appends one formatted string per assessment item to the patient's
// existing briefHistory list. Idempotent on the server side via exact-
// string presence check (M6 D8).
// ============================================================================

import {
  SoapNoteSchema,
  type UpdateProblemListRequest,
  type UpdateProblemListResponse,
} from '@meddoc/types';
import { pushFetch } from './http';
import type { PushOutcome } from './types';
import { extractProblemLinesFromSoap, todayYmd } from './extractors';

export interface RunProblemListPushArgs {
  patientId: string;
  sourceVisitId: string;
  sourceScribeOutputId: string;
  rawSoapContent: unknown;
}

export async function runProblemListPush(
  args: RunProblemListPushArgs
): Promise<PushOutcome> {
  const parsed = SoapNoteSchema.safeParse(args.rawSoapContent);
  if (!parsed.success) {
    return {
      target: 'problem_list',
      status: 'skipped',
      reason: 'SOAP output not available for problem-list update.',
    };
  }
  if (parsed.data.assessment.length === 0) {
    return {
      target: 'problem_list',
      status: 'skipped',
      reason: 'No assessment items — nothing to add to the problem list.',
    };
  }

  const problemLines = extractProblemLinesFromSoap(
    parsed.data,
    args.sourceVisitId,
    todayYmd()
  );

  const body: UpdateProblemListRequest = {
    sourceVisitId: args.sourceVisitId,
    sourceScribeOutputId: args.sourceScribeOutputId,
    problemLines,
  };

  const result = await pushFetch<UpdateProblemListResponse>({
    method: 'PATCH',
    path: `/api/internal/patients/${args.patientId}/problem-list`,
    body,
  });

  if (!result.ok) {
    return {
      target: 'problem_list',
      status: 'error',
      message: result.message || `status ${result.status}`,
      httpStatus: result.status,
    };
  }
  const summary =
    result.data.appendedCount === 0
      ? 'Problem list unchanged — all entries already present.'
      : `${result.data.appendedCount} new diagnosis entry(ies) added to problem list.`;
  return {
    target: 'problem_list',
    status: 'ok',
    summary,
  };
}
