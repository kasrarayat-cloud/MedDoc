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
//
// Phase 3 Wave 1 Subagent 4 — body content (loading/error/timeline
// row) and the Section/Field helpers now branch on isClinician the
// same way the outer chrome / header / footer were already migrated
// in Phase 2 Batch G. Legacy slate-on-white branch is preserved
// byte-for-byte; the Clinician branch swaps to cream/ink/coral tokens.
// ============================================================================

import { useEffect, useState } from 'react';
import { Activity, Globe, ShieldOff, User, X, CheckCircle2, AlertTriangle } from 'lucide-react';

import type { InvestigateResponse, Threat } from '../_types';

type InvestigateDrawerTheme = 'legacy' | 'clinician';

interface Props {
  threat: Threat;
  onClose: () => void;
  onResolve: () => void;
  onDismiss: () => void;
  theme?: InvestigateDrawerTheme;
}

export default function InvestigateDrawer({
  threat,
  onClose,
  onResolve,
  onDismiss,
  theme = 'legacy',
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

  const isClinician = theme === 'clinician';

  return (
    <div
      className={isClinician ? 'fixed inset-0 z-40' : 'fixed inset-0 z-40 bg-slate-900/30'}
      style={isClinician ? { background: 'rgba(43, 38, 32, 0.30)', backdropFilter: 'blur(2px)' } : undefined}
      onClick={onClose}
      role="dialog"
      aria-label="Investigate threat"
    >
      <aside
        className={
          isClinician
            ? 'fixed right-0 top-0 flex h-full w-[480px] max-w-full flex-col'
            : 'fixed right-0 top-0 flex h-full w-[480px] max-w-full flex-col border-l border-slate-200 bg-white shadow-2xl'
        }
        style={
          isClinician
            ? {
                background: 'var(--cream-card)',
                borderLeft: '1px solid var(--line)',
                boxShadow: '-12px 0 32px rgba(43, 38, 32, 0.08)',
                color: 'var(--ink)',
              }
            : undefined
        }
        onClick={(e) => e.stopPropagation()}
      >
        <header
          className={
            isClinician
              ? 'flex items-start justify-between gap-3 px-5 py-4'
              : 'flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4'
          }
          style={isClinician ? { borderBottom: '1px solid var(--line)' } : undefined}
        >
          <div className="flex items-start gap-2.5">
            <span
              className={
                isClinician
                  ? 'mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full'
                  : 'mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full ' +
                    (threat.severity === 'red'
                      ? 'bg-rose-100 text-rose-700'
                      : 'bg-amber-100 text-amber-700')
              }
              style={
                isClinician
                  ? {
                      background:
                        threat.severity === 'red' ? 'var(--coral-tint)' : 'var(--amber-tint)',
                      color: threat.severity === 'red' ? 'var(--coral-deep)' : 'var(--amber-deep)',
                    }
                  : undefined
              }
            >
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <h2
                className={isClinician ? 'qm-cl-serif' : 'text-sm font-semibold tracking-tight text-slate-900'}
                style={isClinician ? { fontSize: 16, fontWeight: 500, color: 'var(--ink)', letterSpacing: '-0.005em' } : undefined}
              >
                {threat.summary}
              </h2>
              <p
                className={isClinician ? 'mt-0.5' : 'mt-0.5 text-[11px] text-slate-500'}
                style={isClinician ? { fontSize: 11, color: 'var(--ink-3)' } : undefined}
              >
                {threat.detail}
              </p>
              <p
                className={isClinician ? 'qm-cl-mono' : 'mt-1 font-mono text-[10px] text-slate-400'}
                style={isClinician ? { marginTop: 4, fontSize: 10, color: 'var(--ink-4)' } : undefined}
              >
                {threat.id}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={
              isClinician
                ? '-mt-1 -mr-1 inline-flex h-7 w-7 items-center justify-center rounded'
                : '-mt-1 -mr-1 inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700'
            }
            style={isClinician ? { color: 'var(--ink-3)', background: 'transparent' } : undefined}
            aria-label="Close drawer"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div
              className={
                isClinician
                  ? 'flex items-center gap-2 text-[12px]'
                  : 'flex items-center gap-2 text-[12px] text-slate-500'
              }
              style={isClinician ? { color: 'var(--ink-3)' } : undefined}
            >
              <span
                className={
                  isClinician
                    ? 'inline-block h-1.5 w-1.5 animate-pulse rounded-full'
                    : 'inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400'
                }
                style={isClinician ? { background: 'var(--ink-3)' } : undefined}
              />
              Loading investigation…
            </div>
          )}
          {error && (
            <div
              className={
                isClinician
                  ? 'rounded border px-3 py-2 text-[12px]'
                  : 'rounded border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-800'
              }
              style={
                isClinician
                  ? {
                      borderColor: 'rgba(201, 123, 110, 0.28)',
                      background: 'var(--coral-tint)',
                      color: 'var(--coral-deep)',
                    }
                  : undefined
              }
            >
              Failed to load investigation: {error}
            </div>
          )}
          {data && (
            <>
              {data.user && (
                <Section
                  title="Actor profile"
                  icon={<User className="h-3.5 w-3.5" />}
                  isClinician={isClinician}
                >
                  <Field k="Email" v={data.user.email ?? '—'} mono isClinician={isClinician} />
                  <Field k="Name" v={data.user.fullName ?? '—'} isClinician={isClinician} />
                  <Field
                    k="Practice"
                    v={data.user.practiceId ?? '—'}
                    mono
                    isClinician={isClinician}
                  />
                  <Field
                    k="Active"
                    v={data.user.isActive ? 'yes' : 'NO'}
                    isClinician={isClinician}
                  />
                  <Field
                    k="Last login"
                    v={data.user.lastLoginAt ? formatLocal(data.user.lastLoginAt) : 'never'}
                    isClinician={isClinician}
                  />
                </Section>
              )}

              {data.ip && (
                <Section
                  title="IP context (last 7d)"
                  icon={<Globe className="h-3.5 w-3.5" />}
                  isClinician={isClinician}
                >
                  <Field k="IP address" v={data.ip.ipAddress} mono isClinician={isClinician} />
                  <Field
                    k="Total events"
                    v={data.ip.totalEventsLast7d.toLocaleString()}
                    isClinician={isClinician}
                  />
                  <Field
                    k="Failed logins"
                    v={data.ip.failedLoginsLast7d.toLocaleString()}
                    isClinician={isClinician}
                  />
                  <Field
                    k="Distinct users"
                    v={data.ip.distinctUsersLast7d.toLocaleString()}
                    isClinician={isClinician}
                  />
                  <Field
                    k="First seen"
                    v={data.ip.firstSeen ? formatLocal(data.ip.firstSeen) : '—'}
                    isClinician={isClinician}
                  />
                  <Field
                    k="Last seen"
                    v={data.ip.lastSeen ? formatLocal(data.ip.lastSeen) : '—'}
                    isClinician={isClinician}
                  />
                </Section>
              )}

              <Section
                title={`Audit timeline (${data.timeline.length})`}
                icon={<Activity className="h-3.5 w-3.5" />}
                isClinician={isClinician}
              >
                {data.timeline.length === 0 ? (
                  <p
                    className={isClinician ? 'text-[11px]' : 'text-[11px] text-slate-500'}
                    style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                  >
                    No related audit rows.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {data.timeline.map((row) => (
                      <li
                        key={row.id}
                        className={
                          isClinician
                            ? 'rounded border px-2.5 py-1.5'
                            : 'rounded border border-slate-200 bg-slate-50 px-2.5 py-1.5'
                        }
                        style={
                          isClinician
                            ? {
                                borderColor: 'var(--line)',
                                background: 'var(--cream-2)',
                              }
                            : undefined
                        }
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={
                              'rounded px-1.5 py-0.5 text-[10px] font-mono ' +
                              (isClinician
                                ? ''
                                : row.success === false
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-slate-200 text-slate-800')
                            }
                            style={
                              isClinician
                                ? row.success === false
                                  ? {
                                      background: 'var(--coral-tint)',
                                      color: 'var(--coral-deep)',
                                    }
                                  : {
                                      background: 'var(--cream-card)',
                                      color: 'var(--ink)',
                                      boxShadow: 'inset 0 0 0 1px var(--line)',
                                    }
                                : undefined
                            }
                          >
                            {row.action}
                          </span>
                          <span
                            className={
                              isClinician
                                ? 'text-[10px] tabular-nums'
                                : 'text-[10px] tabular-nums text-slate-500'
                            }
                            style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                          >
                            {formatLocal(row.timestamp)}
                          </span>
                        </div>
                        <div
                          className={
                            isClinician
                              ? 'mt-0.5 text-[11px]'
                              : 'mt-0.5 text-[11px] text-slate-600'
                          }
                          style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                        >
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

        <footer
          className={
            isClinician
              ? 'flex items-center justify-between gap-2 px-5 py-3'
              : 'flex items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3'
          }
          style={
            isClinician
              ? { borderTop: '1px solid var(--line)', background: 'var(--cream-2)' }
              : undefined
          }
        >
          <button
            type="button"
            onClick={onClose}
            className={
              isClinician
                ? 'qm-cl-btn qm-cl-btn-ghost'
                : 'rounded border border-slate-300 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-700 hover:bg-slate-50'
            }
            style={isClinician ? { height: 32, padding: '0 14px', fontSize: 12 } : undefined}
          >
            Close
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onDismiss}
              className={
                isClinician
                  ? 'qm-cl-btn qm-cl-btn-soft'
                  : 'inline-flex items-center gap-1.5 rounded border border-amber-300 bg-white px-3 py-1.5 text-[12px] font-medium text-amber-800 hover:bg-amber-50'
              }
              style={
                isClinician
                  ? {
                      height: 32,
                      padding: '0 14px',
                      fontSize: 12,
                      gap: 6,
                      color: 'var(--amber-deep)',
                      background: 'var(--amber-tint)',
                    }
                  : undefined
              }
            >
              <ShieldOff className="h-3.5 w-3.5" />
              Dismiss
            </button>
            <button
              type="button"
              onClick={onResolve}
              className={
                isClinician
                  ? 'qm-cl-btn qm-cl-btn-primary'
                  : 'inline-flex items-center gap-1.5 rounded bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-emerald-700'
              }
              style={isClinician ? { height: 32, padding: '0 14px', fontSize: 12, gap: 6 } : undefined}
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
  isClinician = false,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  isClinician?: boolean;
}) {
  return (
    <section className="mb-5">
      <h3
        className={
          isClinician
            ? 'mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider'
            : 'mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500'
        }
        style={isClinician ? { color: 'var(--ink-3)', letterSpacing: '0.10em' } : undefined}
      >
        {icon}
        {title}
      </h3>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function Field({
  k,
  v,
  mono,
  isClinician = false,
}: {
  k: string;
  v: string;
  mono?: boolean;
  isClinician?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[12px]">
      <span
        className={isClinician ? '' : 'text-slate-500'}
        style={isClinician ? { color: 'var(--ink-3)' } : undefined}
      >
        {k}
      </span>
      <span
        className={
          (isClinician ? 'truncate text-right ' : 'truncate text-right text-slate-800 ') +
          (mono ? 'font-mono text-[11px]' : '')
        }
        style={isClinician ? { color: 'var(--ink)' } : undefined}
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
