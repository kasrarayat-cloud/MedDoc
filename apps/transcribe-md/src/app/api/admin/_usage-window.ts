// ============================================================================
// Shared window resolver for the /api/admin/usage/* endpoints.
// ----------------------------------------------------------------------------
// Centralizes the `?window=` parser so all four endpoints agree on what
// "30d" means down to the millisecond. The `offset` option lets callers
// jump back one window for a vs-last-period comparison.
// ============================================================================

export type WindowKey = '24h' | '7d' | '30d' | 'month';

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

interface ResolveOpts {
  /** 0 = current window (default), 1 = the immediately-prior window of
   *  the same length, 2 = the one before that, etc. Used for
   *  vs-last-period comparisons. */
  offset?: number;
}

export interface WindowRange {
  since: Date;
  until: Date;
  spanMs: number;
}

export function resolveWindow(key: WindowKey, opts: ResolveOpts = {}): WindowRange {
  const offset = opts.offset ?? 0;
  const now = new Date();

  if (key === 'month') {
    // "month" = current calendar month UTC. offset=1 → previous month.
    const baseYear = now.getUTCFullYear();
    const baseMonth = now.getUTCMonth() - offset;
    const since = new Date(Date.UTC(baseYear, baseMonth, 1));
    const until = new Date(Date.UTC(baseYear, baseMonth + 1, 1));
    return { since, until, spanMs: until.getTime() - since.getTime() };
  }

  let spanMs = DAY_MS;
  if (key === '24h') spanMs = 24 * HOUR_MS;
  else if (key === '7d') spanMs = 7 * DAY_MS;
  else if (key === '30d') spanMs = 30 * DAY_MS;

  const until = new Date(now.getTime() - offset * spanMs);
  const since = new Date(until.getTime() - spanMs);
  return { since, until, spanMs };
}
