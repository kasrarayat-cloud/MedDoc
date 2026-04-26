'use client';

// ============================================================================
// InvestigateDrawer — Phase 6H 480-px right-side panel
// ----------------------------------------------------------------------------
// Posts to /api/admin/threats/[id]/investigate on open. The endpoint
// already writes a THREAT_INVESTIGATED audit row, so opening the
// drawer counts as the audited action — no separate "ack" step.
//
// Renders three stacked sections:
//   1. Threat header (severity pill + summary + detail)
//   2. Actor / IP context (whichever is non-null)
//   3. Audit timeline (last 50 events for the related actor/IP)
//
// Actions land in the footer: Resolve, Dismiss, Close. Both Resolve
// and Dismiss open a child modal owned by the parent — the drawer
// just signals up.
// ============================================================================

import { useEffect, useState } from 'react';
import { Activity, Globe, ShieldOff, User, X, CheckCircle2, AlertTriangle } from 'lucide-react';

import type { InvestigateResponse, Threat } from '../_types';

interface Props {
  threat: Threat;
  onClose: () => void;
  onResolve: () => void;
  onDismiss: () => void;
}

export default function InvestigateDrawer({
  threat,
  onClose,
  onResolve,
  onDismiss,
}: Props) {
  const [data, setData] = useState<InvestigateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    fetch(`/api/admin/threats/${encodeURIComponent(threat.id)}/investigate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as InvestigateResponse;
      })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [threat.id]);

  return (
    <div
      className="fixed inset-0 z-40 bg-slate-900/30"
      onClick={onClose}
      role="dialog"
      aria-label="Investigate threat"
    >
      <aside
        className="fixed right-0 top-0 flex h-full w-[480px] max-w-full flex-col border-l border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span
              className={
                'mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full ' +
                (threat.severity === 'red'
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-amber-100 text-amber-700')
              }
            >
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-slate-900">
                {threat.summary}
              </h2>
              <p className="mt-0.5 text-[11px] text-slate-500">{threat.detail}</p>
              <p className="mt-1 font-mono text-[10px] text-slate-400">{threat.id}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mt-1 -mr-1 inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close drawer"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-[12px] text-slate-500">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
              Loading investigation…
            </div>
          )}
          {error && (
            <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-800">
              Failed to load investigation: {error}
            </div>
          )}
          {data && (
            <>
              {data.user && (
                <Section title="Actor profile" icon={<User className="h-3.5 w-3.5" />}>
                  <Field k="Email" v={data.user.email ?? '—'} mono />
                  <Field k="Name" v={data.user.fullName ?? '—'} />
                  <Field k="Practice" v={data.user.practiceId ?? '—'} mono />
                  <Field k="Active" v={data.user.isActive ? 'yes' : 'NO'} />
                  <Field
                    k="Last login"
                    v={data.user.lastLoginAt ? formatLocal(data.user.lastLoginAt) : 'never'}
                  />
                </Section>
              )}

              {data.ip && (
                <Section
                  title="IP context (last 7d)"
                  icon={<Globe className="h-3.5 w-3.5" />}
                >
                  <Field k="IP address" v={data.ip.ipAddress} mono />
                  <Field
                    k="Total events"
                    v={data.ip.totalEventsLast7d.toLocaleString()}
                  />
                  <Field
                    k="Failed logins"
                    v={data.ip.failedLoginsLast7d.toLocaleString()}
                  />
                  <Field
                    k="Distinct users"
                    v={data.ip.distinctUsersLast7d.toLocaleString()}
                  />
                  <Field
                    k="First seen"
                    v={data.ip.firstSeen ? formatLocal(data.ip.firstSeen) : '—'}
                  />
                  <Field
                    k="Last seen"
                    v={data.ip.lastSeen ? formatLocal(data.ip.lastSeen) : '—'}
                  />
                </Section>
              )}

              <Section
                title={`Audit timeline (${data.timeline.length})`}
                icon={<Activity className="h-3.5 w-3.5" />}
              >
                {data.timeline.length === 0 ? (
                  <p className="text-[11px] text-slate-500">No related audit rows.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {data.timeline.map((row) => (
                      <li
                        key={row.id}
                        className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1.5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={
                              'rounded px-1.5 py-0.5 text-[10px] font-mono ' +
                              (row.success === false
                                ? 'bg-rose-100 text-rose-800'
                                : 'bg-slate-200 text-slate-800')
                            }
                          >
                            {row.action}
                          </span>
                          <span className="text-[10px] tabular-nums text-slate-500">
                            {formatLocal(row.timestamp)}
                          </span>
                        </div>
                        <div className="mt-0.5 text-[11px] text-slate-600">
                          {[
                            row.userEmailSnapshot,
                            row.ipAddress,
                            row.errorCode,
                          ]
                            .filter(Boolean)
                            .join(' · ') || '—'}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </>
          )}
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onDismiss}
              className="inline-flex items-center gap-1.5 rounded border border-amber-300 bg-white px-3 py-1.5 text-[12px] font-medium text-amber-800 hover:bg-amber-50"
            >
              <ShieldOff className="h-3.5 w-3.5" />
              Dismiss
            </button>
            <button
              type="button"
              onClick={onResolve}
              className="inline-flex items-center gap-1.5 rounded bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-emerald-700"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Resolve
            </button>
          </div>
        </footer>
      </aside>
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5">
      <h3 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {icon}
        {title}
      </h3>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function Field({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[12px]">
      <span className="text-slate-500">{k}</span>
      <span
        className={
          'truncate text-right text-slate-800 ' +
          (mono ? 'font-mono text-[11px]' : '')
        }
      >
        {v}
      </span>
    </div>
  );
}

function formatLocal(iso: string): string {
  const d = new Date(iso);
  const yy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${yy}-${mm}-${dd} ${hh}:${mi}`;
}
