// ============================================================================
// Pure `icdCodes` jsonb → rows extractor. CLIENT-SAFE LEAF.
// ----------------------------------------------------------------------------
// This lived in `displayed-level.ts`, which is fine for server callers but
// unusable from a client component: displayed-level imports `./score`, which
// reaches `llm-mdm` → `lib/redis` → ioredis, so a client import drags dns/net/
// tls/fs into the browser bundle and the Turbopack build fails outright.
//
// The extractor itself has no dependencies at all — it is a shape normaliser
// over `unknown`. Splitting it into this leaf lets the signed-visit document
// view (a client component) read ICD rows without pulling the scoring engine,
// while `displayed-level.ts` re-exports it so there is still exactly ONE
// implementation and the two can never drift.
//
// Do NOT add imports to this file beyond types.
// ============================================================================

import type { IcdCodeRow } from './fallback-mdm';

/** icdCodes jsonb → engine rows. Handles BOTH shapes seen across migrations:
 *  Layer 7a's `{ codes: [{ code, description }] }` AND legacy bare arrays. */
export function extractIcdRows(raw: unknown): IcdCodeRow[] {
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
  if (typeof raw === 'object') {
    const blob = raw as { codes?: unknown };
    if (Array.isArray(blob.codes)) return extractIcdRows(blob.codes);
  }
  return [];
}
