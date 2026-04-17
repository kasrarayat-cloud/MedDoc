'use client';

// ============================================================================
// ScribeAuditTable — interactive filter + per-row diff expand (M7 D2 add)
// ----------------------------------------------------------------------------
// Each row can expand to show the full diff JSON blob + offers a
// "Download JSON" button so sign failures can be forensically reviewed
// post-incident without hitting Prisma directly.
// ============================================================================

import { useMemo, useState } from 'react';

export interface ScribeAuditRow {
  id: string;
  practiceId: string;
  visitId: string;
  actorId: string;
  action: string;
  diff: unknown;
  createdAt: string;
}

interface Props {
  rows: ScribeAuditRow[];
}

function downloadJson(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function isoToLocal(iso: string): string {
  const d = new Date(iso);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}

function truthyFilter(value: string, needle: string): boolean {
  if (!needle) return true;
  return value.toLowerCase().includes(needle.toLowerCase());
}

export default function ScribeAuditTable({ rows }: Props) {
  const [visitFilter, setVisitFilter] = useState('');
  const [actorFilter, setActorFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const uniqueActions = useMemo(() => {
    const s = new Set(rows.map((r) => r.action));
    return Array.from(s).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (!truthyFilter(r.visitId, visitFilter)) return false;
      if (!truthyFilter(r.actorId, actorFilter)) return false;
      if (actionFilter && r.action !== actionFilter) return false;
      if (dateFrom && new Date(r.createdAt) < new Date(dateFrom)) return false;
      if (dateTo && new Date(r.createdAt) > new Date(`${dateTo}T23:59:59.999Z`)) return false;
      return true;
    });
  }, [rows, visitFilter, actorFilter, actionFilter, dateFrom, dateTo]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-sm">
        <label className="block">
          <span className="text-xs text-slate-400">Visit ID</span>
          <input
            value={visitFilter}
            onChange={(e) => setVisitFilter(e.target.value)}
            placeholder="e.g. cviz1…"
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono text-xs"
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">Actor (user) ID</span>
          <input
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono text-xs"
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">Action</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
          >
            <option value="">(all)</option>
            {uniqueActions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">From (date)</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">To (date)</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
          />
        </label>
      </div>

      <div className="text-xs text-slate-500">
        Showing {filtered.length} of {rows.length} events.
      </div>

      <div className="border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-900/60 text-xs text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">When</th>
              <th className="px-3 py-2 text-left">Action</th>
              <th className="px-3 py-2 text-left">Visit</th>
              <th className="px-3 py-2 text-left">Actor</th>
              <th className="px-3 py-2 text-left">Practice</th>
              <th className="px-3 py-2 text-right">Diff</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {filtered.map((r) => (
              <>
                <tr key={r.id} className="hover:bg-slate-900/30">
                  <td className="px-3 py-2 text-xs text-slate-300 whitespace-nowrap">
                    {isoToLocal(r.createdAt)}
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-200">
                      {r.action}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">{r.visitId}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">{r.actorId}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">
                    {r.practiceId}
                  </td>
                  <td className="px-3 py-2 text-right space-x-2">
                    {r.diff !== null && r.diff !== undefined ? (
                      <>
                        <button
                          type="button"
                          onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                          className="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700"
                        >
                          {expandedId === r.id ? 'Hide' : 'Expand'}
                        </button>
                        <button
                          type="button"
                          onClick={() => downloadJson(`scribe-audit-${r.id}.json`, r)}
                          className="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700"
                        >
                          Download
                        </button>
                      </>
                    ) : (
                      <span className="text-xs text-slate-600">(none)</span>
                    )}
                  </td>
                </tr>
                {expandedId === r.id && r.diff !== null && (
                  <tr key={`${r.id}-diff`} className="bg-slate-900/40">
                    <td colSpan={6} className="px-3 py-2">
                      <pre className="text-xs font-mono whitespace-pre-wrap break-words text-slate-300 bg-slate-950/60 border border-slate-800 rounded p-3 max-h-80 overflow-auto">
                        {JSON.stringify(r.diff, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-6 text-center text-sm text-slate-500"
                >
                  No events match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
