'use client';

// ============================================================================
// User detail drawer — right-side slide-in (480px) with action chips
// ----------------------------------------------------------------------------
// The list row's data is shown immediately; an enriched fetch to
// /api/admin/users/[id] then back-fills `recentActivity` + `ipHistory`.
// Until that round-trip lands, those sections render skeleton text.
//
// Action wiring:
//   non-confirm actions (reset-password, force-logout, suspend, unsuspend)
//     POST directly with `await actionPost(...)`.
//   confirm actions (soft-delete, grant-admin, revoke-admin) bubble
//     `onConfirm(kind, user)` to the parent which mounts the
//     ConfirmationModal.
//
// Self-action guard: when the drawer subject is the currently-signed-in
// admin, suspend / soft-delete / revoke-admin chips are visibly disabled.
// The server already 403s self-revoke and self-suspend would just lock
// the admin out; this is defense in depth + better UX.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white drawer.
// Clinician branch swaps the canvas to cream-card, ink-toned text,
// and recolors the AlertTriangle/CheckCircle accents to the soft
// sage/amber/coral palette. State machine + server-action calls are
// unchanged.
// ============================================================================

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  X,
  Crown,
  KeyRound,
  LogOut,
  PauseCircle,
  PlayCircle,
  ShieldOff,
  Trash2,
} from 'lucide-react';

import {
  avatarPalette,
  cls,
  daysSince,
  formatCount,
  formatUsd,
  initials,
  PROVIDER_LABEL,
  relativeTime,
} from '../../_lib/admin-format';
import type { ConfirmKind, UserDetail, UserListRow } from '../_types';

type UserDetailDrawerTheme = 'legacy' | 'clinician';

interface Props {
  user: UserListRow;
  currentUserId: string;
  onClose: () => void;
  onConfirm: (kind: ConfirmKind, user: UserListRow) => void;
  /** Bumped by parent after a successful action — we re-fetch detail. */
  refetchKey: number;
  /** Parent calls this after a non-confirm action so the list re-renders. */
  onActed: () => void;
  theme?: UserDetailDrawerTheme;
}

export default function UserDetailDrawer({
  user,
  currentUserId,
  onClose,
  onConfirm,
  refetchKey,
  onActed,
  theme = 'legacy',
}: Props) {
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  // Esc-to-close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Fetch enriched detail (recentActivity, ipHistory) on open + after refresh.
  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetch(`/api/admin/users/${user.id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        // The endpoint returns its own shape; merge what we need into the
        // list-row baseline so the drawer always has both the list view
        // (instant) and the detail view (after round-trip).
        const merged: UserDetail = {
          ...user,
          recentActivity: data.recentActivity ?? [],
          ipHistory: data.ipHistory ?? [],
          activeSessions: data.activeSessions ?? user.activeSessions,
          monthSpend: data.monthSpend
            ? {
                totalCostUsd: data.monthSpend.totalCostUsd ?? 0,
                byProvider: foldProviderShape(data.monthSpend.byProvider ?? {}),
              }
            : user.monthSpend,
        };
        setDetail(merged);
      })
      .catch(() => {
        // Leave detail null — UI shows "Could not load detail" inline
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user.id, refetchKey, user]);

  const totalSpend = (detail ?? user).monthSpend.totalCostUsd;
  const providerEntries = useMemo(
    () =>
      Object.entries((detail ?? user).monthSpend.byProvider).sort(
        (a, b) => b[1].costUsd - a[1].costUsd
      ),
    [detail, user]
  );
  const monthVisits = (detail ?? user).monthVisits;
  const avgPerVisit = monthVisits > 0 ? totalSpend / monthVisits : 0;
  const isAdmin = user.isSuperAdmin;
  const isSelf = currentUserId === user.id;

  async function actionPost(
    label: string,
    path: string,
    body: Record<string, unknown> = {}
  ) {
    setBusyAction(label);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success(`${label}: ok`);
        onActed();
      } else {
        toast.error(`${label} failed`, {
          description: data.error ?? `HTTP ${res.status}`,
        });
      }
    } catch (err) {
      toast.error(`${label} failed`, {
        description: err instanceof Error ? err.message : 'network error',
      });
    } finally {
      setBusyAction(null);
    }
  }

  const isClinician = theme === 'clinician';

  return (
    <>
      <div
        onClick={onClose}
        className={
          isClinician
            ? 'fixed inset-0 z-30'
            : 'fixed inset-0 z-30 bg-slate-900/20 backdrop-blur-[2px]'
        }
        style={
          isClinician
            ? {
                background: 'rgba(43, 38, 32, 0.20)',
                backdropFilter: 'blur(2px)',
              }
            : undefined
        }
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label={`User detail: ${user.fullName}`}
        className={
          isClinician
            ? 'fixed right-0 top-0 z-40 flex h-full w-full max-w-[480px] flex-col'
            : 'fixed right-0 top-0 z-40 flex h-full w-full max-w-[480px] flex-col border-l border-slate-200 bg-white shadow-xl'
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
      >
        {/* Header */}
        <div
          className={
            isClinician
              ? 'flex items-start justify-between px-5 py-4'
              : 'flex items-start justify-between border-b border-slate-200 px-5 py-4'
          }
          style={isClinician ? { borderBottom: '1px solid var(--line)' } : undefined}
        >
          <div className="flex items-start gap-3">
            <Avatar user={user} size={40} />
            <div className="min-w-0">
              <div
                className="truncate"
                style={
                  isClinician
                    ? { fontSize: 16, fontWeight: 600, color: 'var(--ink)' }
                    : undefined
                }
              >
                <span
                  className={
                    isClinician
                      ? 'qm-cl-serif'
                      : 'text-base font-semibold text-slate-900'
                  }
                  style={isClinician ? { fontSize: 18, color: 'var(--ink)' } : undefined}
                >
                  {user.fullName}
                </span>
              </div>
              <div
                className={isClinician ? 'truncate text-xs' : 'truncate text-xs text-slate-500'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                {user.email}
              </div>
              <div
                className={
                  isClinician
                    ? 'mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5'
                    : 'mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-600'
                }
                style={isClinician ? { fontSize: 11, color: 'var(--ink-2)' } : undefined}
              >
                <span className="font-medium uppercase tracking-wide">{user.role}</span>
                <span style={isClinician ? { color: 'var(--ink-4)' } : undefined} className={isClinician ? '' : 'text-slate-300'}>·</span>
                <StatusInline user={user} />
                <span style={isClinician ? { color: 'var(--ink-4)' } : undefined} className={isClinician ? '' : 'text-slate-300'}>·</span>
                <span style={isClinician ? { color: 'var(--ink-3)' } : undefined} className={isClinician ? '' : 'text-slate-500'}>{user.practiceName}</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className={
              isClinician
                ? 'rounded p-1'
                : 'rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700'
            }
            style={isClinician ? { color: 'var(--ink-3)', background: 'transparent' } : undefined}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Actions */}
          <DrawerSection label="Actions">
            <ActionGroup label="Standard">
              <ActionChip
                icon={KeyRound}
                label={busyAction === 'Reset password' ? 'Working…' : 'Reset password'}
                tone="neutral"
                onClick={() =>
                  actionPost('Reset password', 'reset-password')
                }
                disabled={busyAction !== null}
              />
              <ActionChip
                icon={LogOut}
                label={busyAction === 'Force logout' ? 'Working…' : 'Force logout'}
                tone="neutral"
                onClick={() => actionPost('Force logout', 'force-logout')}
                disabled={busyAction !== null}
              />
            </ActionGroup>
            <ActionGroup label="Reversible">
              {user.status === 'suspended' ? (
                <ActionChip
                  icon={PlayCircle}
                  label="Reinstate account"
                  tone="neutral"
                  onClick={() => actionPost('Reinstate', 'unsuspend')}
                  disabled={busyAction !== null}
                />
              ) : (
                <ActionChip
                  icon={PauseCircle}
                  label="Suspend account"
                  tone="amber"
                  onClick={() => {
                    if (isSelf) return;
                    const reason =
                      window.prompt(
                        `Suspend ${user.email}?\n\nOptional reason (leave blank for none):`
                      ) ?? null;
                    if (reason === null) return;
                    actionPost('Suspend', 'suspend', { reason: reason || undefined });
                  }}
                  disabled={busyAction !== null || isSelf}
                  selfBlock={isSelf}
                />
              )}
            </ActionGroup>
            <ActionGroup label="Privileges">
              {isAdmin ? (
                <ActionChip
                  icon={ShieldOff}
                  label="Revoke admin"
                  tone="rose"
                  onClick={() => onConfirm('revoke_admin', user)}
                  disabled={busyAction !== null || isSelf}
                  selfBlock={isSelf}
                />
              ) : (
                <ActionChip
                  icon={Crown}
                  label="Grant admin"
                  tone="amber"
                  onClick={() => onConfirm('grant_admin', user)}
                  disabled={busyAction !== null}
                />
              )}
            </ActionGroup>
            <ActionGroup label="Destructive — confirmation required">
              <ActionChip
                icon={Trash2}
                label="Soft delete account"
                tone="rose"
                onClick={() => onConfirm('soft_delete', user)}
                disabled={busyAction !== null || isSelf || user.status === 'soft_deleted'}
                selfBlock={isSelf}
              />
            </ActionGroup>
          </DrawerSection>

          {/* This month */}
          <DrawerSection label="This month">
            <div className="mb-3 flex items-baseline justify-between">
              <div className="font-mono text-2xl font-semibold tabular-nums text-slate-900">
                {formatUsd(totalSpend)}
              </div>
              <div className="text-[11px] text-slate-500">
                <span className="font-mono tabular-nums text-slate-700">{monthVisits}</span> visits
                {monthVisits > 0 && (
                  <>
                    {' '}
                    <span className="mx-1.5 text-slate-300">·</span>avg{' '}
                    <span className="font-mono tabular-nums text-slate-700">
                      ${avgPerVisit.toFixed(2)}
                    </span>{' '}
                    /visit
                  </>
                )}
              </div>
            </div>
            {providerEntries.length === 0 ? (
              <div className="rounded-md border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-500">
                No usage this month
              </div>
            ) : (
              <ul className="space-y-2">
                {providerEntries.map(([k, v]) => (
                  <ProviderBar
                    key={k}
                    label={PROVIDER_LABEL[k] ?? k}
                    cost={v.costUsd}
                    total={totalSpend}
                    sub={`${formatCount(v.unitCount)} ${v.unitLabel}`}
                  />
                ))}
              </ul>
            )}
          </DrawerSection>

          {/* Account info */}
          <DrawerSection label="Account info">
            <DefList
              rows={[
                {
                  k: 'Created',
                  v: (
                    <>
                      {user.createdAt.slice(0, 10)}{' '}
                      <span className="text-slate-400">
                        ({daysSince(user.createdAt)} days ago)
                      </span>
                    </>
                  ),
                },
                { k: 'Practice', v: user.practiceName },
                {
                  k: 'Last login',
                  v: user.lastLoginAt ? (
                    <>
                      {relativeTime(user.lastLoginAt)}{' '}
                      {user.lastLoginIp && (
                        <span className="text-slate-400">
                          from <span className="font-mono">{user.lastLoginIp}</span>
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-slate-400">never</span>
                  ),
                },
                {
                  k: 'Active sessions',
                  v: (
                    <span className="font-mono tabular-nums">
                      {(detail ?? user).activeSessions}
                    </span>
                  ),
                },
              ]}
            />
          </DrawerSection>

          {/* IP history */}
          <DrawerSection label="IP history (last 30 days)">
            {loading ? (
              <div className="text-xs text-slate-400">Loading…</div>
            ) : !detail ? (
              <div className="text-xs text-rose-500">Could not load detail</div>
            ) : detail.ipHistory.length === 0 ? (
              <div className="text-xs text-slate-500">No login history</div>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {detail.ipHistory.map((ip) => (
                  <li
                    key={ip.ipAddress}
                    className="flex items-baseline justify-between border-b border-slate-100 pb-1.5 last:border-b-0 last:pb-0"
                  >
                    <span className="font-mono text-xs tabular-nums text-slate-700">
                      {ip.ipAddress}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      <span className="font-mono tabular-nums text-slate-700">
                        {ip.count}
                      </span>{' '}
                      logins · last {relativeTime(ip.lastSeen)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </DrawerSection>

          {/* Recent activity */}
          <DrawerSection label="Recent activity">
            {loading ? (
              <div className="text-xs text-slate-400">Loading…</div>
            ) : !detail ? (
              <div className="text-xs text-rose-500">Could not load detail</div>
            ) : detail.recentActivity.length === 0 ? (
              <div className="text-xs text-slate-500">No activity</div>
            ) : (
              <ul className="space-y-1 font-mono text-[11px] tabular-nums">
                {detail.recentActivity.slice(0, 20).map((a) => (
                  <li
                    key={a.id}
                    className="flex items-baseline gap-3 text-slate-700"
                  >
                    <span className="w-12 shrink-0 text-slate-400">
                      {a.timestamp.slice(11, 16)}
                    </span>
                    <span
                      className={cls(
                        'w-44 shrink-0 truncate',
                        a.action === 'LOGIN_FAILED' || !a.success
                          ? 'text-rose-600'
                          : 'text-slate-700'
                      )}
                    >
                      {a.action}
                    </span>
                    {a.targetType && a.targetId && (
                      <span className="truncate text-slate-500">
                        {a.targetType}:{a.targetId.slice(0, 8)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </DrawerSection>

          <div className="px-5 pb-6 pt-2 text-[11px] text-slate-400">
            All admin actions on this user are logged to the audit trail.
            {isSelf && (
              <span className="ml-2 text-slate-500">
                You can&apos;t suspend, delete, or revoke your own admin access — ask
                a peer.
              </span>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Avatar({
  user,
  size = 28,
}: {
  user: { id: string; fullName: string; isSuperAdmin: boolean; status: string };
  size?: number;
}) {
  const pal = avatarPalette(user.id);
  const isAdmin = user.isSuperAdmin;
  const isSuspended = user.status === 'suspended';
  const isDeleted = user.status === 'soft_deleted';
  return (
    <div className="relative inline-block" style={{ width: size, height: size }}>
      <div
        className={cls(
          'flex h-full w-full items-center justify-center rounded-full ring-1',
          pal.bg,
          pal.text,
          pal.ring
        )}
        style={{ fontSize: Math.max(10, size * 0.4) }}
      >
        <span className="font-semibold tracking-tight">{initials(user.fullName)}</span>
      </div>
      {isAdmin && (
        <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500 ring-1 ring-white">
          <Crown className="h-2 w-2 text-white" strokeWidth={2.5} />
        </span>
      )}
      {isSuspended && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500 ring-1 ring-white">
          <PauseCircle className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
        </span>
      )}
      {isDeleted && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-rose-500 ring-1 ring-white">
          <X className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
        </span>
      )}
    </div>
  );
}

function StatusInline({ user }: { user: UserListRow }) {
  if (user.status === 'active')
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
        Active
      </span>
    );
  if (user.status === 'suspended')
    return (
      <span
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-800"
        title={user.suspendedReason ?? undefined}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
        Suspended
      </span>
    );
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-700"
      title={
        user.softDeletedAt
          ? `Soft-deleted ${user.softDeletedAt.slice(0, 10)} by ${user.softDeletedBy ?? '—'}`
          : undefined
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
      Deleted
    </span>
  );
}

function DrawerSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-slate-100 px-5 py-4 last:border-b-0">
      <div className="mb-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      {children}
    </section>
  );
}

function ActionGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function ActionChip({
  icon: Icon,
  label,
  tone,
  onClick,
  disabled,
  selfBlock,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  tone: 'neutral' | 'amber' | 'rose';
  onClick: () => void;
  disabled?: boolean;
  selfBlock?: boolean;
}) {
  const tones: Record<string, string> = {
    neutral:
      'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-slate-200/70 hover:ring-slate-300',
    amber:
      'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-amber-50 hover:ring-amber-300',
    rose: 'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:ring-rose-300',
  };
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={selfBlock ? 'Disabled — cannot act on your own account' : undefined}
      className={cls(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium ring-1 transition-colors',
        tones[tone],
        disabled && 'cursor-not-allowed opacity-50'
      )}
    >
      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

function ProviderBar({
  label,
  cost,
  total,
  sub,
}: {
  label: string;
  cost: number;
  total: number;
  sub: string;
}) {
  const pct = total > 0 ? (cost / total) * 100 : 0;
  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="text-slate-500">
          <span className="font-mono tabular-nums text-slate-800">${cost.toFixed(2)}</span>
          <span className="mx-1.5 text-slate-300">·</span>
          <span className="font-mono tabular-nums">{sub}</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-slate-400" style={{ width: `${pct}%` }} />
      </div>
    </li>
  );
}

function DefList({ rows }: { rows: { k: string; v: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map((r, i) => (
        <div key={r.k + i} className="contents">
          <dt className="text-[11px] uppercase tracking-wide text-slate-500">{r.k}</dt>
          <dd className="text-slate-800">{r.v}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------------------
// Helpers — fold the API endpoint's monthSpend.byProvider shape (a flat
// `{ provider: cost }` map) into the drawer's expected shape (with
// per-provider unit metadata). The list-level fetcher already returns
// the richer shape; this only matters when the detail endpoint shape
// differs.
// ---------------------------------------------------------------------------

function foldProviderShape(
  byProvider: Record<string, number | { costUsd: number; unitCount: number; unitLabel: string }>
): Record<string, { costUsd: number; unitCount: number; unitLabel: string }> {
  const out: Record<string, { costUsd: number; unitCount: number; unitLabel: string }> = {};
  for (const [k, v] of Object.entries(byProvider)) {
    if (typeof v === 'number') {
      out[k] = { costUsd: v, unitCount: 0, unitLabel: '' };
    } else {
      out[k] = v;
    }
  }
  return out;
}
