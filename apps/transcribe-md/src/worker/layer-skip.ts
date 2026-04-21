// ============================================================================
// Pipeline resumability — per-layer skip gating (T-M13)
// ----------------------------------------------------------------------------
// Every layer in the transcribe-md pipeline persists its output into a
// dedicated TranscribeVisit column. Those writes are our implicit
// checkpoints: if a column is populated, that layer already succeeded
// in a prior attempt, and a retry can skip straight to the next.
//
// This module owns the mapping from layer name to "is this layer's
// column populated?" — no runtime knowledge leaks into worker.ts,
// which just calls isLayerComplete(visit, 'L4') and gets a boolean.
//
// Failure semantics
//   - L1-L6 (sequential): on throw, the outer processVisit catch
//     writes FAILED. Their column state on the row depends on how
//     far the layer got. Worst case: column was written partially
//     and the skip check returns true for a "bad" value. Mitigation:
//     the downstream layer that consumes it will re-throw on parse,
//     which fails the attempt → retry → same skip → same failure
//     → FAILED after `attempts: 3`. Acceptable; the user can re-submit.
//   - L7a-e (parallel): individual failures are caught by the
//     Promise.allSettled wrapper in worker.ts AND by clearAutomationColumn
//     which nulls the column on failure. So a failed L7 layer always
//     has a null column going into the next attempt → skip check
//     correctly returns false → it re-runs.
// ============================================================================

/** Shape of a TranscribeVisit row trimmed to the columns the skip
 *  logic needs. Intentionally permissive — callers can pass a wider
 *  row; this type pins just the checkpoint columns. */
export interface LayerSkipState {
  transcriptRaw: unknown;
  transcriptText: string | null;
  speakerMap: unknown;
  entities: unknown;
  soapDraft: string | null;
  critique: unknown;
  soapFinal: string | null;
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
  referrals: unknown;
  patientSummary: string | null;
  /** T-M24: JSON-serialised token → content dict from L7f. Present only
   *  when the visit's templateId is set and L7f ran. Populated (even as
   *  "{}") marks L7f complete so BullMQ retries don't re-invoke the
   *  fill layer unnecessarily. */
  filledTemplate: string | null;
}

/** All sequential-stage layers. Names align with the comments in
 *  worker.ts and the docs so cross-referencing stays obvious. */
export type SequentialLayer =
  | 'L1'   // audio-mode transcribe
  | 'L1b'  // voice-dictation transcribe
  | 'L2'   // speaker roles
  | 'L3'   // extract entities
  | 'L4'   // generate SOAP
  | 'L5'   // self-critique
  | 'L6';  // polish

export type AutomationLayer =
  | 'L7a'  // ICD coding
  | 'L7b'  // CPT coding
  | 'L7c'  // Rx drafting
  | 'L7d'  // referrals
  | 'L7e'  // patient summary
  | 'L7f'; // T-M24: custom-template fill (opt-in, gated on visit.templateId)

export type PipelineLayer = SequentialLayer | AutomationLayer;

function hasContent(v: unknown): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === 'string') return v.trim().length > 0;
  // Prisma JSONB returns parsed objects. Empty {} and [] count as
  // "present" — the layer wrote something, even if empty. That's
  // intentional: Layer 2's fallback writes an empty-ish map and
  // still counts as completed.
  return true;
}

/** True when `layer` has already written its checkpoint column on the
 *  visit row. The caller is expected to pass a freshly-read row so a
 *  mid-pipeline skip honors writes from prior iterations of the same
 *  attempt. */
export function isLayerComplete(
  state: LayerSkipState,
  layer: PipelineLayer
): boolean {
  switch (layer) {
    // L1 and L1b share transcriptRaw — both transcription layers write
    // the same column, and the caller only runs one of them per visit.
    case 'L1':
    case 'L1b':
      return hasContent(state.transcriptRaw);
    case 'L2':
      return hasContent(state.speakerMap);
    case 'L3':
      return hasContent(state.entities);
    case 'L4':
      return hasContent(state.soapDraft);
    case 'L5':
      return hasContent(state.critique);
    case 'L6':
      return hasContent(state.soapFinal);
    case 'L7a':
      return hasContent(state.icdCodes);
    case 'L7b':
      return hasContent(state.cptCodes);
    case 'L7c':
      return hasContent(state.rxDrafts);
    case 'L7d':
      return hasContent(state.referrals);
    case 'L7e':
      return hasContent(state.patientSummary);
    case 'L7f':
      return hasContent(state.filledTemplate);
  }
}

import { log } from '@/lib/log';

const SCOPE = 'layer-skip';

/** Uniform log line for a skipped layer so cost-recovered attempts
 *  are grepable. `attempt` comes from BullMQ's job.attemptsMade — the
 *  first attempt should never hit a skip path (all columns null), so
 *  seeing skips on attempt 1 is a signal to investigate. */
export function logSkippedLayer(
  visitId: string,
  layer: PipelineLayer,
  attempt: number
): void {
  log.info(SCOPE, 'skipped layer (column already populated)', {
    visitId,
    layer,
    attempt,
  });
}

/** Summary line emitted once at the end of an attempt. Empty `skipped`
 *  logs nothing (no noise on happy-path first attempts). */
export function logSkipSummary(
  visitId: string,
  attempt: number,
  skipped: PipelineLayer[]
): void {
  if (skipped.length === 0) return;
  log.info(SCOPE, 'resumed attempt — layers skipped', {
    visitId,
    attempt,
    skippedCount: skipped.length,
    skipped,
  });
}
