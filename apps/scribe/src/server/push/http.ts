// ============================================================================
// Shared HTTP helper for M6 push modules
// ----------------------------------------------------------------------------
// Wraps fetch with:
//   - Bearer SCRIBE_SERVICE_TOKEN header
//   - One automatic retry on 5xx / network errors with a ~500ms backoff
//     (M6 D4 — no retry on 4xx since those are data problems)
//   - Returns a discriminated result so push modules can map to PushOutcome
//
// The retry is deliberate: MedDoc Pro may be rebooting, Caddy may flap.
// We NEVER retry 4xx — those are stable "this payload is wrong" signals.
// ============================================================================

const MEDDOC_PRO_INTERNAL_URL =
  process.env.MEDDOC_PRO_INTERNAL_URL?.trim() || 'http://meddoc-pro:3000';

const RETRY_BACKOFF_MS = 500;

function getInternalToken(): string {
  const token = process.env.SCRIBE_SERVICE_TOKEN;
  if (!token) throw new Error('SCRIBE_SERVICE_TOKEN is not set.');
  return token;
}

export interface PushFetchOk<T> {
  ok: true;
  status: number;
  data: T;
}

export interface PushFetchFail {
  ok: false;
  status: number; // 0 = transport error
  message: string;
}

export type PushFetchResult<T> = PushFetchOk<T> | PushFetchFail;

export async function pushFetch<T>(args: {
  path: string;        // e.g. /api/internal/patients/abc/tasks
  method: 'POST' | 'PATCH';
  body: unknown;
}): Promise<PushFetchResult<T>> {
  const url = `${MEDDOC_PRO_INTERNAL_URL}${args.path}`;
  const init: RequestInit = {
    method: args.method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getInternalToken()}`,
    },
    body: JSON.stringify(args.body),
    cache: 'no-store',
  };

  const attempt = async (): Promise<PushFetchResult<T>> => {
    try {
      const resp = await fetch(url, init);
      const raw = await resp.text();
      if (!resp.ok) {
        return { ok: false, status: resp.status, message: raw.slice(0, 400) };
      }
      // 204 is unusual here; any non-empty 2xx should carry JSON.
      if (!raw) return { ok: true, status: resp.status, data: {} as T };
      return { ok: true, status: resp.status, data: JSON.parse(raw) as T };
    } catch (err) {
      return {
        ok: false,
        status: 0,
        message: err instanceof Error ? err.message : String(err),
      };
    }
  };

  const first = await attempt();
  // Retry only on 5xx or transport (status=0). 4xx is a data problem —
  // the second attempt would return the same thing.
  if (first.ok) return first;
  if (first.status >= 400 && first.status < 500) return first;
  await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS));
  return attempt();
}
