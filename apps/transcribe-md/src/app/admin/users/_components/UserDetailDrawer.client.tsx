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
//
// Phase 3 (Wave 1 Subagent 4) — inner sections previously rendered
// flat slate-* utility classes that bled through both themes. They
// are now branched the same way the outer chrome was: Clinician
// swaps to cream/ink/sage tokens via inline style + qm-cl-pill-*
// utilities; legacy stays byte-for-byte (slate-on-white preserved).
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
            <Avatar user={user} size={40} isClinician={isClinician} />
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
                <StatusInline user={user} isClinician={isClinician} />
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
          <DrawerSection label="Actions" isClinician={isClinician}>
            <ActionGroup label="Standard" isClinician={isClinician}>
              <ActionChip
                icon={KeyRound}
                label={busyAction === 'Reset password' ? 'Working…' : 'Reset password'}
                tone="neutral"
                onClick={() =>
                  actionPost('Reset password', 'reset-password')
                }
                disabled={busyAction !== null}
                isClinician={isClinician}
              />
              <ActionChip
                icon={LogOut}
                label={busyAction === 'Force logout' ? 'Working…' : 'Force logout'}
                tone="neutral"
                onClick={() => actionPost('Force logout', 'force-logout')}
                disabled={busyAction !== null}
                isClinician={isClinician}
              />
            </ActionGroup>
            <ActionGroup label="Reversible" isClinician={isClinician}>
              {user.status === 'suspended' ? (
                <ActionChip
                  icon={PlayCircle}
                  label="Reinstate account"
                  tone="neutral"
                  onClick={() => actionPost('Reinstate', 'unsuspend')}
                  disabled={busyAction !== null}
                  isClinician={isClinician}
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
                  isClinician={isClinician}
                />
              )}
            </ActionGroup>
            <ActionGroup label="Privileges" isClinician={isClinician}>
              {isAdmin ? (
                <ActionChip
                  icon={ShieldOff}
                  label="Revoke admin"
                  tone="rose"
                  onClick={() => onConfirm('revoke_admin', user)}
                  disabled={busyAction !== null || isSelf}
                  selfBlock={isSelf}
                  isClinician={isClinician}
                />
              ) : (
                <ActionChip
                  icon={Crown}
                  label="Grant admin"
                  tone="amber"
                  onClick={() => onConfirm('grant_admin', user)}
                  disabled={busyAction !== null}
                  isClinician={isClinician}
                />
              )}
            </ActionGroup>
            <ActionGroup label="Destructive — confirmation required" isClinician={isClinician}>
              <ActionChip
                icon={Trash2}
                label="Soft delete account"
                tone="rose"
                onClick={() => onConfirm('soft_delete', user)}
                disabled={busyAction !== null || isSelf || user.status === 'soft_deleted'}
                selfBlock={isSelf}
                isClinician={isClinician}
              />
            </ActionGroup>
          </DrawerSection>

          {/* This month */}
          <DrawerSection label="This month" isClinician={isClinician}>
            <div className="mb-3 flex items-baseline justify-between">
              <div
                className={
                  isClinician
                    ? 'font-mono text-2xl font-semibold tabular-nums'
                    : 'font-mono text-2xl font-semibold tabular-nums text-slate-900'
                }
                style={isClinician ? { color: 'var(--ink)' } : undefined}
              >
                {formatUsd(totalSpend)}
              </div>
              <div
                className={isClinician ? 'text-[11px]' : 'text-[11px] text-slate-500'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                <span
                  className={
                    isClinician
                      ? 'font-mono tabular-nums'
                      : 'font-mono tabular-nums text-slate-700'
                  }
                  style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                >
                  {monthVisits}
                </span>{' '}
                visits
                {monthVisits > 0 && (
                  <>
                    {' '}
                    <span
                      className={isClinician ? 'mx-1.5' : 'mx-1.5 text-slate-300'}
                      style={isClinician ? { color: 'var(--ink-4)' } : undefined}
                    >
                      ·
                    </span>
                    avg{' '}
                    <span
                      className={
                        isClinician
                          ? 'font-mono tabular-nums'
                          : 'font-mono tabular-nums text-slate-700'
                      }
                      style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                    >
                      ${avgPerVisit.toFixed(2)}
                    </span>{' '}
                    /visit
                  </>
                )}
              </div>
            </div>
            {providerEntries.length === 0 ? (
              <div
                className={
                  isClinician
                    ? 'rounded-md border border-dashed px-3 py-4 text-center text-xs'
                    : 'rounded-md border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-500'
                }
                style={
                  isClinician
                    ? { borderColor: 'var(--line)', color: 'var(--ink-3)' }
                    : undefined
                }
              >
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
                    isClinician={isClinician}
                  />
                ))}
              </ul>
            )}
          </DrawerSection>

          {/* Account info */}
          <DrawerSection label="Account info" isClinician={isClinician}>
            <DefList
              isClinician={isClinician}
              rows={[
                {
                  k: 'Created',
                  v: (
                    <>
                      {user.createdAt.slice(0, 10)}{' '}
                      <span
                        className={isClinician ? '' : 'text-slate-400'}
                        style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                      >
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
                        <span
                          className={isClinician ? '' : 'text-slate-400'}
                          style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                        >
                          from <span className="font-mono">{user.lastLoginIp}</span>
                        </span>
                      )}
                    </>
                  ) : (
                    <span
                      className={isClinician ? '' : 'text-slate-400'}
                      style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                    >
                      never
                    </span>
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
          <DrawerSection label="IP history (last 30 days)" isClinician={isClinician}>
            {loading ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-slate-400'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                Loading…
              </div>
            ) : !detail ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-rose-500'}
                style={isClinician ? { color: 'var(--coral-deep)' } : undefined}
              >
                Could not load detail
              </div>
            ) : detail.ipHistory.length === 0 ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-slate-500'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                No login history
              </div>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {detail.ipHistory.map((ip) => (
                  <li
                    key={ip.ipAddress}
                    className={
                      isClinician
                        ? 'flex items-baseline justify-between border-b pb-1.5 last:border-b-0 last:pb-0'
                        : 'flex items-baseline justify-between border-b border-slate-100 pb-1.5 last:border-b-0 last:pb-0'
                    }
                    style={isClinician ? { borderColor: 'var(--line)' } : undefined}
                  >
                    <span
                      className={
                        isClinician
                          ? 'font-mono text-xs tabular-nums'
                          : 'font-mono text-xs tabular-nums text-slate-700'
                      }
                      style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                    >
                      {ip.ipAddress}
                    </span>
                    <span
                      className={isClinician ? 'text-[11px]' : 'text-[11px] text-slate-500'}
                      style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                    >
                      <span
                        className={
                          isClinician
                            ? 'font-mono tabular-nums'
                            : 'font-mono tabular-nums text-slate-700'
                        }
                        style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                      >
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
          <DrawerSection label="Recent activity" isClinician={isClinician}>
            {loading ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-slate-400'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                Loading…
              </div>
            ) : !detail ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-rose-500'}
                style={isClinician ? { color: 'var(--coral-deep)' } : undefined}
              >
                Could not load detail
              </div>
            ) : detail.recentActivity.length === 0 ? (
              <div
                className={isClinician ? 'text-xs' : 'text-xs text-slate-500'}
                style={isClinician ? { color: 'var(--ink-3)' } : undefined}
              >
                No activity
              </div>
            ) : (
              <ul className="space-y-1 font-mono text-[11px] tabular-nums">
                {detail.recentActivity.slice(0, 20).map((a) => (
                  <li
                    key={a.id}
                    className={
                      isClinician
                        ? 'flex items-baseline gap-3'
                        : 'flex items-baseline gap-3 text-slate-700'
                    }
                    style={isClinician ? { color: 'var(--ink-2)' } : undefined}
                  >
                    <span
                      className={
                        isClinician
                          ? 'w-12 shrink-0'
                          : 'w-12 shrink-0 text-slate-400'
                      }
                      style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                    >
                      {a.timestamp.slice(11, 16)}
                    </span>
                    <span
                      className={cls(
                        'w-44 shrink-0 truncate',
                        a.action === 'LOGIN_FAILED' || !a.success
                          ? isClinician
                            ? ''
                            : 'text-rose-600'
                          : isClinician
                            ? ''
                            : 'text-slate-700'
                      )}
                      style={
                        isClinician
                          ? {
                              color:
                                a.action === 'LOGIN_FAILED' || !a.success
                                  ? 'var(--coral-deep)'
                                  : 'var(--ink-2)',
                            }
                          : undefined
                      }
                    >
                      {a.action}
                    </span>
                    {a.targetType && a.targetId && (
                      <span
                        className={isClinician ? 'truncate' : 'truncate text-slate-500'}
                        style={isClinician ? { color: 'var(--ink-3)' } : undefined}
                      >
                        {a.targetType}:{a.targetId.slice(0, 8)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </DrawerSection>

          <div
            className={
              isClinician
                ? 'px-5 pb-6 pt-2 text-[11px]'
                : 'px-5 pb-6 pt-2 text-[11px] text-slate-400'
            }
            style={isClinician ? { color: 'var(--ink-3)' } : undefined}
          >
            All admin actions on this user are logged to the audit trail.
            {isSelf && (
              <span
                className={isClinician ? 'ml-2' : 'ml-2 text-slate-500'}
                style={isClinician ? { color: 'var(--ink-2)' } : undefined}
              >
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
  isClinician = false,
}: {
  user: { id: string; fullName: string; isSuperAdmin: boolean; status: string };
  size?: number;
  isClinician?: boolean;
}) {
  const pal = avatarPalette(user.id);
  const isAdmin = user.isSuperAdmin;
  const isSuspended = user.status === 'suspended';
  const isDeleted = user.status === 'soft_deleted';
  // Clinician indicator backgrounds map admin/suspended → --amber, deleted → --coral.
  // Ring becomes cream-card (the drawer surface) so the indicator reads as a small lozenge
  // floating on warm paper rather than a hard ring on white.
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
        <span
          className={
            isClinician
              ? 'absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full ring-1'
              : 'absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500 ring-1 ring-white'
          }
          style={
            isClinician
              ? { background: 'var(--amber)', boxShadow: '0 0 0 1px var(--cream-card)' }
              : undefined
          }
        >
          <Crown
            className={isClinician ? 'h-2 w-2' : 'h-2 w-2 text-white'}
            strokeWidth={2.5}
            style={isClinician ? { color: '#FFFCF5' } : undefined}
          />
        </span>
      )}
      {isSuspended && (
        <span
          className={
            isClinician
              ? 'absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full ring-1'
              : 'absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500 ring-1 ring-white'
          }
          style={
            isClinician
              ? { background: 'var(--amber)', boxShadow: '0 0 0 1px var(--cream-card)' }
              : undefined
          }
        >
          <PauseCircle
            className={isClinician ? 'h-2.5 w-2.5' : 'h-2.5 w-2.5 text-white'}
            strokeWidth={2.5}
            style={isClinician ? { color: '#FFFCF5' } : undefined}
          />
        </span>
      )}
      {isDeleted && (
        <span
          className={
            isClinician
              ? 'absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full ring-1'
              : 'absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-rose-500 ring-1 ring-white'
          }
          style={
            isClinician
              ? { background: 'var(--coral)', boxShadow: '0 0 0 1px var(--cream-card)' }
              : undefined
          }
        >
          <X
            className={isClinician ? 'h-2.5 w-2.5' : 'h-2.5 w-2.5 text-white'}
            strokeWidth={2.5}
            style={isClinician ? { color: '#FFFCF5' } : undefined}
          />
        </span>
      )}
    </div>
  );
}

function StatusInline({
  user,
  isClinician = false,
}: {
  user: UserListRow;
  isClinician?: boolean;
}) {
  // Clinician palette: emerald → sage, amber → amber, rose → coral.
  if (user.status === 'active')
    return (
      <span
        className={
          isClinician
            ? 'inline-flex items-center gap-1.5 text-[11px] font-medium'
            : 'inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700'
        }
        style={isClinician ? { color: 'var(--sage-deep)' } : undefined}
      >
        <span
          className={isClinician ? 'h-1.5 w-1.5 rounded-full' : 'h-1.5 w-1.5 rounded-full bg-emerald-500'}
          style={isClinician ? { background: 'var(--sage)' } : undefined}
        />
        Active
      </span>
    );
  if (user.status === 'suspended')
    return (
      <span
        className={
          isClinician
            ? 'inline-flex items-center gap-1.5 text-[11px] font-medium'
            : 'inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-800'
        }
        style={isClinician ? { color: 'var(--amber-deep)' } : undefined}
        title={user.suspendedReason ?? undefined}
      >
        <span
          className={isClinician ? 'h-1.5 w-1.5 rounded-full' : 'h-1.5 w-1.5 rounded-full bg-amber-500'}
          style={isClinician ? { background: 'var(--amber)' } : undefined}
        />
        Suspended
      </span>
    );
  return (
    <span
      className={
        isClinician
          ? 'inline-flex items-center gap-1.5 text-[11px] font-medium'
          : 'inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-700'
      }
      style={isClinician ? { color: 'var(--coral-deep)' } : undefined}
      title={
        user.softDeletedAt
          ? `Soft-deleted ${user.softDeletedAt.slice(0, 10)} by ${user.softDeletedBy ?? '—'}`
          : undefined
      }
    >
      <span
        className={isClinician ? 'h-1.5 w-1.5 rounded-full' : 'h-1.5 w-1.5 rounded-full bg-rose-500'}
        style={isClinician ? { background: 'var(--coral)' } : undefined}
      />
      Deleted
    </span>
  );
}

function DrawerSection({
  label,
  children,
  isClinician = false,
}: {
  label: string;
  children: React.ReactNode;
  isClinician?: boolean;
}) {
  return (
    <section
      className={
        isClinician
          ? 'border-b px-5 py-4 last:border-b-0'
          : 'border-b border-slate-100 px-5 py-4 last:border-b-0'
      }
      style={isClinician ? { borderColor: 'var(--line)' } : undefined}
    >
      <div
        className={
          isClinician
            ? 'mb-3 text-[11px] font-medium uppercase tracking-wide'
            : 'mb-3 text-[11px] font-medium uppercase tracking-wide text-slate-500'
        }
        style={isClinician ? { color: 'var(--ink-3)', letterSpacing: '0.08em' } : undefined}
      >
        {label}
      </div>
      {children}
    </section>
  );
}

function ActionGroup({
  label,
  children,
  isClinician = false,
}: {
  label: string;
  children: React.ReactNode;
  isClinician?: boolean;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <div
        className={
          isClinician
            ? 'mb-1.5 text-[10px] font-medium uppercase tracking-wider'
            : 'mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-400'
        }
        style={isClinician ? { color: 'var(--ink-4)', letterSpacing: '0.10em' } : undefined}
      >
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
  isClinician = false,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  tone: 'neutral' | 'amber' | 'rose';
  onClick: () => void;
  disabled?: boolean;
  selfBlock?: boolean;
  isClinician?: boolean;
}) {
  // Legacy tone classes (slate-on-white).
  const legacyTones: Record<string, string> = {
    neutral:
      'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-slate-200/70 hover:ring-slate-300',
    amber:
      'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-amber-50 hover:ring-amber-300',
    rose: 'bg-slate-100 text-slate-800 ring-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:ring-rose-300',
  };
  // Clinician inline-style chip per tone — cream-soft base for neutral,
  // tinted for amber/coral. Hover background is bumped via a CSS var
  // toggle in inline style; framework lacks `hover:` for inline styles
  // so we settle for a one-step background and a thin ring that is the
  // same colour family as the tone (sage/amber/coral) at rest.
  const clinicianToneStyle: Record<string, React.CSSProperties> = {
    neutral: {
      background: 'var(--cream-2)',
      color: 'var(--ink)',
      boxShadow: 'inset 0 0 0 1px var(--line)',
    },
    amber: {
      background: 'var(--amber-tint)',
      color: 'var(--amber-deep)',
      boxShadow: 'inset 0 0 0 1px rgba(212, 165, 116, 0.30)',
    },
    rose: {
      background: 'var(--coral-tint)',
      color: 'var(--coral-deep)',
      boxShadow: 'inset 0 0 0 1px rgba(201, 123, 110, 0.28)',
    },
  };
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={selfBlock ? 'Disabled — cannot act on your own account' : undefined}
      className={cls(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
        isClinician ? '' : 'ring-1',
        isClinician ? '' : legacyTones[tone],
        disabled && 'cursor-not-allowed opacity-50'
      )}
      style={isClinician ? clinicianToneStyle[tone] : undefined}
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
  isClinician = false,
}: {
  label: string;
  cost: number;
  total: number;
  sub: string;
  isClinician?: boolean;
}) {
  const pct = total > 0 ? (cost / total) * 100 : 0;
  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
        <span
          className={isClinician ? 'font-medium' : 'font-medium text-slate-700'}
          style={isClinician ? { color: 'var(--ink-2)' } : undefined}
        >
          {label}
        </span>
        <span
          className={isClinician ? '' : 'text-slate-500'}
          style={isClinician ? { color: 'var(--ink-3)' } : undefined}
        >
          <span
            className={
              isClinician
                ? 'font-mono tabular-nums'
                : 'font-mono tabular-nums text-slate-800'
            }
            style={isClinician ? { color: 'var(--ink)' } : undefined}
          >
            ${cost.toFixed(2)}
          </span>
          <span
            className={isClinician ? 'mx-1.5' : 'mx-1.5 text-slate-300'}
            style={isClinician ? { color: 'var(--ink-4)' } : undefined}
          >
            ·
          </span>
          <span className="font-mono tabular-nums">{sub}</span>
        </span>
      </div>
      <div
        className={
          isClinician
            ? 'h-1.5 overflow-hidden rounded-full'
            : 'h-1.5 overflow-hidden rounded-full bg-slate-100'
        }
        style={isClinician ? { background: 'var(--cream-2)' } : undefined}
      >
        <div
          className={isClinician ? 'h-full rounded-full' : 'h-full rounded-full bg-slate-400'}
          style={
            isClinician
              ? { width: `${pct}%`, background: 'var(--sage)' }
              : { width: `${pct}%` }
          }
        />
      </div>
    </li>
  );
}

function DefList({
  rows,
  isClinician = false,
}: {
  rows: { k: string; v: React.ReactNode }[];
  isClinician?: boolean;
}) {
  return (
    <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map((r, i) => (
        <div key={r.k + i} className="contents">
          <dt
            className={
              isClinician
                ? 'text-[11px] uppercase tracking-wide'
                : 'text-[11px] uppercase tracking-wide text-slate-500'
            }
            style={isClinician ? { color: 'var(--ink-3)' } : undefined}
          >
            {r.k}
          </dt>
          <dd
            className={isClinician ? '' : 'text-slate-800'}
            style={isClinician ? { color: 'var(--ink)' } : undefined}
          >
            {r.v}
          </dd>
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
