// ============================================================================
// @meddoc/types — ScribeOutput error sentinel
// ----------------------------------------------------------------------------
// Spec §11: "on second fail, mark that output ERROR and surface to reviewer."
//
// M4 design decision D2 (per-PR plan): we don't add a status column to
// ScribeOutput. Instead, on a double schema-fail the extraction wrapper
// persists `{ _error: {...} }` into ScribeOutput.content. The review UI
// type-guards with isOutputError() and renders an ERROR tab.
//
// Every success-shape schema (CodingOutputSchema / RxOutputSchema / etc.)
// is `.strict()` so an error-shaped payload can't accidentally pass its
// validator — the two shapes are mutually exclusive by construction.
// ============================================================================

import { z } from 'zod';

export const OutputErrorSchema = z.object({
  _error: z.object({
    /** Coarse reason — SCHEMA_FAIL | PROVIDER_ERROR | FLAG_OFF | UNKNOWN. */
    code: z.string().min(1),
    /** Human-readable detail; should not contain PHI. */
    message: z.string().min(1),
    /** How many generation attempts were made before giving up. */
    attempts: z.number().int().min(0),
    /** ISO-8601 timestamp the wrapper captured the failure. */
    occurredAt: z.string().datetime(),
  }),
}).strict();
export type OutputError = z.infer<typeof OutputErrorSchema>;

/**
 * Narrow guard — safe to call on any `ScribeOutput.content` blob before
 * rendering. Uses safeParse so non-object inputs don't throw.
 */
export function isOutputError(value: unknown): value is OutputError {
  return OutputErrorSchema.safeParse(value).success;
}
