// ============================================================================
// confidenceScores Zod schema + JSON-safe serializer (FIND-P1-012).
// ----------------------------------------------------------------------------
// FIND-P1-012 (comprehensive-audit 2026-05-14): the worker writes
// `confidenceScores` as a plain object cast to Prisma's Json type at
// `worker.ts:906`. Prisma's JSONB adapter silently coerces non-
// serializable values (Map → `{}`, function → undefined-drop, Date
// without `.toISOString()` → stringified weird) or throws an opaque
// "Inconsistent column data" error on Map/Set/circular refs.
//
// Defense-in-depth:
//   1. Zod parse against `ConfidenceScores` — catches shape drift
//      (status enum + reason required when failed).
//   2. JSON round-trip (`JSON.parse(JSON.stringify(...))`) — catches
//      non-JSON-serializable values inside `metadata: z.unknown()`
//      that Zod's `unknown` accepts but Prisma silently coerces.
//
// On any failure the caller writes `null` (matches the first-attempt
// initial-state shape at `worker.ts:297`) — visit still progresses,
// the Pipeline tab just shows no per-layer status block. Schema-
// failure log goes to stderr so ops sees the drift without breaking
// the worker.
// ============================================================================

import { z } from 'zod';

/** Per-task status published from the worker's automation fan-out at
 *  `worker.ts:777`. Three variants:
 *    - 'ok':       layer ran or skipped a resumed-ok checkpoint
 *    - 'skipped':  layer disabled (feature flag or specialty filter)
 *    - 'failed':   load-bearing layer threw; reason carries the
 *                  (truncated, scrubbed) error message
 *  Metadata is open (`z.unknown()`) so future layers can attach
 *  per-layer telemetry without a schema bump. The JSON round-trip
 *  in `sanitizeConfidenceScores` guards against non-serializable
 *  values leaking in. */
export const LayerStatus = z.discriminatedUnion('status', [
  z.object({
    status: z.literal('ok'),
    metadata: z.unknown().optional(),
  }),
  z.object({ status: z.literal('skipped') }),
  z.object({
    status: z.literal('failed'),
    reason: z.string(),
  }),
]);
export type LayerStatus = z.infer<typeof LayerStatus>;

/** Map of layer-task key (icd_coding / cpt_coding / rx_drafting /
 *  referrals / patient_summary) → status. */
export const ConfidenceScores = z.record(z.string(), LayerStatus);
export type ConfidenceScores = z.infer<typeof ConfidenceScores>;

/** Parse + JSON-round-trip. Returns the sanitized shape or `null` if
 *  the input is malformed OR carries non-serializable values. The
 *  caller writes the result to Prisma JSON; `null` is a safe fallback
 *  (matches `worker.ts:297` first-attempt initial state).
 *
 *  Never throws. Drift surfaces via the returned-null branch which
 *  the caller logs.
 */
export function sanitizeConfidenceScores(
  raw: unknown
): ConfidenceScores | null {
  const parsed = ConfidenceScores.safeParse(raw);
  if (!parsed.success) return null;
  try {
    // Round-trip catches non-JSON values inside metadata (Map, Set,
    // function, circular ref) that `z.unknown()` accepts but Prisma
    // silently coerces. The throw path here means the worker writes
    // null rather than a coerced shape that L2/L7 would later choke on.
    return JSON.parse(JSON.stringify(parsed.data)) as ConfidenceScores;
  } catch {
    return null;
  }
}
