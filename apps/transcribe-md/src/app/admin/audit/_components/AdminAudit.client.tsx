'use client';

// ============================================================================
// /admin/audit — client view over GET /api/admin/audit-logs
// ----------------------------------------------------------------------------
// Filters (action, actor user id, outcome) and cursor paging, both passed
// straight through to the adminApi-gated route — the only place this page's
// data comes from (see page.tsx for why that is the guard design).
//
// Rendered with the users surface's tokens and table idiom; no new design
// language while the admin shell waits for the owner's design pick.
// ============================================================================

import { useCallback, useEffect, useState } from 'react';

import AdminNav from '../../_components/AdminNav.client';
import { cls, relativeTime } from '../../_lib/admin-format';

interface AuditRow {
  id: string;
  timestamp: string;
  action: string;
  userId: string | null;
  userEmail: string | null;
  targetType: string | null;
  targetId: string | null;
  success: boolean;
  errorCode: string | null;
  ipAddress: string | null;
}

interface Filters {
  action: string;
  userId: string;
  success: '' | 'true' | 'false';
}

const PAGE = 50;

function query(f: Filters, cursor: string | null): string {
  const q = new URLSearchParams({ limit: String(PAGE) });
  if (f.action.trim()) q.set('action', f.action.trim().toUpperCase());
  if (f.userId.trim()) q.set('userId', f.userId.trim());
  if (f.success) q.set('success', f.success);
  if (cursor) q.set('cursor', cursor);
  return q.toString();
}

export default function AdminAudit() {
  const [draft, setDraft] = useState<Filters>({ action: '', userId: '', success: '' });
  const [filters, setFilters] = useState<Filters>(draft);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [state, setState] = useState<'loading' | 'idle' | 'error'>('loading');

  const load = useCallback(async (f: Filters, from: string | null) => {
    setState('loading');
    try {
      const res = await fetch(`/api/admin/audit-logs?${query(f, from)}`);
      const data: { logs?: AuditRow[]; nextCursor?: string | null; hasMore?: boolean } = await res
        .json()
        .catch(() => ({}));
      if (!res.ok || !data.logs) {
        setState('error');
        return;
      }
      setRows((prev) => (from ? [...prev, ...data.logs!] : data.logs!));
      setCursor(data.nextCursor ?? null);
      setHasMore(!!data.hasMore);
      setState('idle');
    } catch {
      setState('error');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(filters, null);
  }, [filters, load]);

  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto max-w-[1440px] px-6 py-3">
          <div className="mb-1 font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3">
            Admin · Audit
          </div>
          <h1 className="text-[20px] font-semibold leading-tight tracking-tight text-linear-text">
            Audit trail
          </h1>
          <div className="mt-1 text-[11px] text-linear-text-3">
            Every audited action, newest first. Retained 7 years per HIPAA §164.316(b)(2)(i).
          </div>
        </div>
      </header>
      <AdminNav />

      <main className="mx-auto flex max-w-[1440px] flex-col gap-3 px-6 py-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFilters(draft);
          }}
          className="flex flex-col gap-2 rounded-lg border border-linear-border bg-linear-surface-1 px-3 py-2.5 sm:flex-row sm:items-center"
        >
          <input
            value={draft.action}
            onChange={(e) => setDraft({ ...draft, action: e.target.value })}
            placeholder="Action, e.g. USER_DEACTIVATED"
            maxLength={80}
            aria-label="Filter by action"
            className="block h-8 flex-1 rounded-md border border-linear-border bg-linear-surface-2 px-3 font-mono text-xs text-linear-text placeholder:text-linear-text-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
          />
          <input
            value={draft.userId}
            onChange={(e) => setDraft({ ...draft, userId: e.target.value })}
            placeholder="Actor user id"
            maxLength={64}
            aria-label="Filter by actor user id"
            className="block h-8 flex-1 rounded-md border border-linear-border bg-linear-surface-2 px-3 font-mono text-xs text-linear-text placeholder:text-linear-text-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
          />
          <select
            value={draft.success}
            onChange={(e) => setDraft({ ...draft, success: e.target.value as Filters['success'] })}
            aria-label="Filter by outcome"
            className="h-8 rounded-md border border-linear-border bg-linear-surface-2 px-2.5 text-xs text-linear-text-2"
          >
            <option value="">Any outcome</option>
            <option value="true">Succeeded</option>
            <option value="false">Failed</option>
          </select>
          <button type="submit" className="qm-lin-btn h-8">
            Apply
          </button>
        </form>

        <div className="overflow-x-auto rounded-lg border border-linear-border bg-linear-surface-1">
          {state === 'error' && rows.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-linear-danger">
              Could not load the audit trail. An unknown action name is rejected by the API.
            </div>
          ) : rows.length === 0 && state !== 'loading' ? (
            <div className="px-6 py-12 text-center text-sm text-linear-text-3">No audit rows match.</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left">
                  {['When', 'Action', 'Actor', 'Target', 'Outcome', 'IP'].map((h) => (
                    <th
                      key={h}
                      className="border-b border-linear-border bg-linear-bg px-3 py-2.5 font-mono text-[10px] font-medium uppercase tracking-[0.07em] text-linear-text-3 first:pl-4 last:pr-4"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-linear-border text-xs">
                    <td className="whitespace-nowrap py-2 pl-4 pr-3 font-mono tabular-nums text-linear-text-2" title={r.timestamp}>
                      {relativeTime(r.timestamp)}
                    </td>
                    <td className={cls('py-2 pr-3 font-mono', r.success ? 'text-linear-text' : 'text-linear-danger')}>
                      {r.action}
                    </td>
                    <td className="py-2 pr-3 font-mono text-linear-text-2">{r.userEmail ?? r.userId ?? '—'}</td>
                    <td className="py-2 pr-3 font-mono text-linear-text-3">
                      {r.targetType && r.targetId ? `${r.targetType}:${r.targetId.slice(0, 12)}` : '—'}
                    </td>
                    <td className="py-2 pr-3">
                      {r.success ? (
                        <span className="text-linear-sage-bright">ok</span>
                      ) : (
                        <span className="text-linear-danger">{r.errorCode ?? 'failed'}</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 font-mono tabular-nums text-linear-text-3">{r.ipAddress ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {(hasMore || state === 'loading') && (
            <div className="flex justify-center border-t border-linear-border px-4 py-2">
              <button
                type="button"
                disabled={state === 'loading'}
                onClick={() => void load(filters, cursor)}
                className="qm-lin-btn h-7"
              >
                {state === 'loading' ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
