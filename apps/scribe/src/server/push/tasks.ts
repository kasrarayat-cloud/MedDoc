// ============================================================================
// Push — SOAP-derived follow-up tasks → Task (M6)
// ----------------------------------------------------------------------------
// Heuristic extraction from SOAP.plan: one Task per actionable plan
// section, capped at MAX_TASKS. Always creates at least one "URGENT"
// Task when SOAP.requires_immediate_follow_up is set (psych SAFETY
// CLAUSE).
// ============================================================================

import {
  SoapNoteSchema,
  type CreateTasksRequest,
  type CreateTasksResponse,
} from '@meddoc/types';
import { pushFetch } from './http';
import type { PushOutcome } from './types';
import { extractTasksFromSoap } from './extractors';

export interface RunTasksPushArgs {
  patientId: string;
  patientDisplayName: string;
  sourceVisitId: string;
  /**
   * The SOAP ScribeOutput.id — tasks are sourced from the SOAP plan,
   * not from a dedicated output.
   */
  sourceScribeOutputId: string;
  clinicianUserId: string;
  rawSoapContent: unknown;
}

export async function runTasksPush(
  args: RunTasksPushArgs
): Promise<PushOutcome> {
  const parsed = SoapNoteSchema.safeParse(args.rawSoapContent);
  if (!parsed.success) {
    return {
      target: 'tasks',
      status: 'skipped',
      reason: 'SOAP output not available for task extraction.',
    };
  }
  const tasks = extractTasksFromSoap(parsed.data, args.patientDisplayName);
  if (tasks.length === 0) {
    return {
      target: 'tasks',
      status: 'skipped',
      reason: 'No actionable plan items — nothing to schedule.',
    };
  }

  const body: CreateTasksRequest = {
    sourceVisitId: args.sourceVisitId,
    sourceScribeOutputId: args.sourceScribeOutputId,
    assignedUserId: args.clinicianUserId,
    createdByUserId: args.clinicianUserId,
    tasks,
  };

  const result = await pushFetch<CreateTasksResponse>({
    method: 'POST',
    path: `/api/internal/patients/${args.patientId}/tasks`,
    body,
  });

  if (!result.ok) {
    return {
      target: 'tasks',
      status: 'error',
      message: result.message || `status ${result.status}`,
      httpStatus: result.status,
    };
  }
  return {
    target: 'tasks',
    status: 'ok',
    summary: `${result.data.taskIds.length} follow-up task(s) created.`,
    createdIds: result.data.taskIds,
  };
}
