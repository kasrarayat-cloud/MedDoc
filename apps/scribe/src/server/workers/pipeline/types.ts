// ============================================================================
// apps/scribe — Pipeline module shared types
// ----------------------------------------------------------------------------
// Each M4 extraction (coding / rx / referrals / patient-summary) returns
// a PipelineOutcome so the finalize-visit orchestrator can fan out with
// Promise.allSettled and persist either the validated output or the
// OutputError sentinel without ever throwing past the orchestrator.
// ============================================================================

export type PipelineErrorCode =
  | 'SCHEMA_FAIL'
  | 'PROVIDER_ERROR'
  | 'FLAG_OFF'
  | 'UNKNOWN';

export interface PipelineErrorInfo {
  code: PipelineErrorCode;
  message: string;
  attempts: number;
  occurredAt: string;
}

export interface PipelineSuccess<T> {
  ok: true;
  output: T;
  modelUsed: string;
}

export interface PipelineFailure {
  ok: false;
  error: PipelineErrorInfo;
  modelUsed: string;
}

export type PipelineOutcome<T> = PipelineSuccess<T> | PipelineFailure;

/**
 * Feature flag lookup for per-output-type disablement (spec §18 + M4 D10).
 * Env names:
 *   SCRIBE_EXTRACT_CODING           (default: on)
 *   SCRIBE_EXTRACT_RX               (default: on)
 *   SCRIBE_EXTRACT_REFERRALS        (default: on)
 *   SCRIBE_EXTRACT_PATIENT_SUMMARY  (default: on)
 *
 * Any value other than "false" (case-insensitive) leaves extraction on.
 */
export function isExtractionEnabled(
  name: 'CODING' | 'RX' | 'REFERRALS' | 'PATIENT_SUMMARY'
): boolean {
  const val = process.env[`SCRIBE_EXTRACT_${name}`];
  if (val === undefined) return true;
  return val.trim().toLowerCase() !== 'false';
}
