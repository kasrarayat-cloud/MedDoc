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
// Phase 5 (Linear V1 Faithful) — drawer renders against linear-surface-2
// with a hairline left border, sage/warning/danger toned action chips,
// and mono columns for IDs/timestamps. Earlier dual-theme branching has
// been retired; the `theme` prop survives as an ignored compat shim.
// ============================================================================

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  X,
  Crown,
  KeyRound,
  LogOut,
  MonitorSmartphone,
  PauseCircle,
  Pencil,
  PlayCircle,
  ShieldOff,
  Trash2,
  UserCheck,
  UserPlus,
  UserX,
} from 'lucide-react';

import {
  cls,
  daysSince,
  formatCount,
  formatUsd,
  initials,
  PROVIDER_LABEL,
  relativeTime,
} from '../../_lib/admin-format';
import type { ConfirmKind, UserDetail, UserListRow } from '../_types';

import EditProfileModal from './EditProfileModal.client';

/** One `user_sessions` row as GET /api/admin/users/[id]/sessions returns it —
 *  never the bearer token, which the route does not select. */
interface SessionRow {
  id: string;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: string;
  lastActiveAt: string;
  expiresAt: string;
  status: 'active' | 'expired' | 'invalidated';
}

interface Props {
  user: UserListRow;
  currentUserId: string;
  onClose: () => void;
  onConfirm: (kind: ConfirmKind, user: UserListRow) => void;
  /** Bumped by parent after a successful action — we re-fetch detail. */
  refetchKey: number;
  /** Parent calls this after a non-confirm action so the list re-renders. */
  onActed: () => void;
  /** Opens "Add user" pre-filled with this user's practice. */
  onAddUser?: (practiceId: string) => void;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

export default function UserDetailDrawer({
  user,
  currentUserId,
  onClose,
  onConfirm,
  refetchKey,
  onActed,
  onAddUser,
}: Props) {
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  // Sessions load on demand — the list is a user_sessions read, not part of
  // the detail round-trip.
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [sessionsState, setSessionsState] = useState<'idle' | 'loading' | 'error'>('idle');

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
        // Reactivation reports the promo grant's outcome; say it rather than
        // swallow it, because 'failed' is something an operator must see.
        const promo = (data as { promo?: string }).promo;
        if (promo === 'failed') {
          toast.warning(`${label}: ok — but the promo grant failed`, {
            description: 'Recorded on the audit row; the backfill re-run repairs it.',
          });
        } else {
          toast.success(`${label}: ok`, { description: promo ? `promo: ${promo}` : undefined });
        }
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

  async function loadSessions() {
    setSessionsState('loading');
    try {
      const res = await fetch(`/api/admin/users/${user.id}/sessions`);
      const data: { ok?: boolean; sessions?: SessionRow[] } = await res.json().catch(() => ({}));
      if (res.ok && data.ok && data.sessions) {
        setSessions(data.sessions);
        setSessionsState('idle');
      } else {
        setSessionsState('error');
      }
    } catch {
      setSessionsState('error');
    }
  }

  async function revokeOne(sid: string) {
    setBusyAction(`revoke:${sid}`);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/sessions/${sid}/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      const data: { ok?: boolean; error?: string } = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success('Session revoked');
        await loadSessions();
        onActed();
      } else {
        toast.error('Revoke failed', { description: data.error ?? `HTTP ${res.status}` });
      }
    } catch (err) {
      toast.error('Revoke failed', { description: err instanceof Error ? err.message : 'network error' });
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-30 bg-black/60 backdrop-blur-[2px]"
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label={`User detail: ${user.fullName}`}
        className="fixed right-0 top-0 z-40 flex h-full w-full max-w-[480px] flex-col border-l border-linear-border bg-linear-surface-2 text-linear-text shadow-[-12px_0_32px_rgba(0,0,0,0.5)]"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-linear-border px-5 py-4">
          <div className="flex items-start gap-3">
            <Avatar user={user} size={40} />
            <div className="min-w-0">
              <div className="truncate text-base font-semibold text-linear-text">
                {user.fullName}
              </div>
              <div className="truncate font-mono text-xs text-linear-text-3">
                {user.email}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-linear-text-2">
                <span className="font-mono font-medium uppercase tracking-[0.05em]">{user.role}</span>
                <span className="text-linear-text-3">·</span>
                <StatusInline user={user} />
                <span className="text-linear-text-3">·</span>
                <span className="text-linear-text-3">{user.practiceName}</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-linear-text-3 hover:bg-linear-row-hover hover:text-linear-text"
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
              <ActionChip
                icon={Pencil}
                label="Edit"
                tone="neutral"
                onClick={() => {
                  if (!isSelf) setEditing(true);
                }}
                disabled={busyAction !== null || isSelf || user.status === 'soft_deleted'}
                selfBlock={isSelf}
              />
              {onAddUser && (
                <ActionChip
                  icon={UserPlus}
                  label="Add user to this practice"
                  tone="neutral"
                  onClick={() => onAddUser(user.practiceId)}
                  disabled={busyAction !== null}
                />
              )}
            </ActionGroup>
            <ActionGroup label="Reversible">
              {user.isDeactivated ? (
                <ActionChip
                  icon={UserCheck}
                  label={busyAction === 'Reactivate' ? 'Working…' : 'Reactivate account'}
                  tone="neutral"
                  onClick={() => {
                    if (!isSelf) actionPost('Reactivate', 'reactivate');
                  }}
                  disabled={busyAction !== null || isSelf || user.status === 'soft_deleted'}
                  selfBlock={isSelf}
                />
              ) : (
                <ActionChip
                  icon={UserX}
                  label="Deactivate account"
                  tone="rose"
                  onClick={() => onConfirm('deactivate', user)}
                  disabled={busyAction !== null || isSelf || user.status === 'soft_deleted'}
                  selfBlock={isSelf}
                />
              )}
              {user.isSuspended ? (
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

          {/* Sessions — user_sessions, revocable one row at a time */}
          <DrawerSection label="Sessions">
            {sessions === null ? (
              <button
                type="button"
                onClick={loadSessions}
                disabled={sessionsState === 'loading'}
                className="qm-lin-btn h-7"
              >
                <MonitorSmartphone className="mr-1 h-3 w-3" />
                {sessionsState === 'loading' ? 'Loading…' : 'Show sessions'}
              </button>
            ) : sessions.length === 0 ? (
              <div className="text-xs text-linear-text-3">No sessions on record</div>
            ) : (
              <ul className="space-y-1.5">
                {sessions.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center justify-between gap-3 border-b border-linear-border pb-1.5 text-[11px] last:border-b-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-mono text-linear-text-2">
                        {s.ipAddress ?? 'unknown IP'}
                        <span className="mx-1.5 text-linear-text-3">·</span>
                        <span
                          className={cls(
                            s.status === 'active' ? 'text-linear-sage-bright' : 'text-linear-text-3'
                          )}
                        >
                          {s.status}
                        </span>
                      </div>
                      <div className="truncate text-linear-text-3" title={s.userAgent ?? undefined}>
                        last seen {relativeTime(s.lastActiveAt)}
                        {s.userAgent ? ` · ${s.userAgent}` : ''}
                      </div>
                    </div>
                    {s.status === 'active' && (
                      <button
                        type="button"
                        onClick={() => revokeOne(s.id)}
                        disabled={busyAction !== null || isSelf}
                        title={isSelf ? 'Use Sign out for your own session' : undefined}
                        className="qm-lin-btn h-6 shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busyAction === `revoke:${s.id}` ? 'Working…' : 'Revoke'}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {sessionsState === 'error' && (
              <div className="mt-2 text-xs text-linear-danger">Could not load sessions</div>
            )}
          </DrawerSection>

          {/* This month */}
          <DrawerSection label="This month">
            <div className="mb-3 flex items-baseline justify-between">
              <div className="font-mono text-2xl font-semibold tabular-nums text-linear-text">
                {formatUsd(totalSpend)}
              </div>
              <div className="text-[11px] text-linear-text-3">
                <span className="font-mono tabular-nums text-linear-text-2">
                  {monthVisits}
                </span>{' '}
                visits
                {monthVisits > 0 && (
                  <>
                    {' '}
                    <span className="mx-1.5 text-linear-text-3">·</span>
                    avg{' '}
                    <span className="font-mono tabular-nums text-linear-text-2">
                      ${avgPerVisit.toFixed(2)}
                    </span>{' '}
                    /visit
                  </>
                )}
              </div>
            </div>
            {providerEntries.length === 0 ? (
              <div className="rounded-md border border-dashed border-linear-border px-3 py-4 text-center text-xs text-linear-text-3">
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
                      <span className="text-linear-text-3">
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
                        <span className="text-linear-text-3">
                          from <span className="font-mono">{user.lastLoginIp}</span>
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-linear-text-3">never</span>
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
              <div className="text-xs text-linear-text-3">Loading…</div>
            ) : !detail ? (
              <div className="text-xs text-linear-danger">Could not load detail</div>
            ) : detail.ipHistory.length === 0 ? (
              <div className="text-xs text-linear-text-3">No login history</div>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {detail.ipHistory.map((ip) => (
                  <li
                    key={ip.ipAddress}
                    className="flex items-baseline justify-between border-b border-linear-border pb-1.5 last:border-b-0 last:pb-0"
                  >
                    <span className="font-mono text-xs tabular-nums text-linear-text-2">
                      {ip.ipAddress}
                    </span>
                    <span className="text-[11px] text-linear-text-3">
                      <span className="font-mono tabular-nums text-linear-text-2">
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
              <div className="text-xs text-linear-text-3">Loading…</div>
            ) : !detail ? (
              <div className="text-xs text-linear-danger">Could not load detail</div>
            ) : detail.recentActivity.length === 0 ? (
              <div className="text-xs text-linear-text-3">No activity</div>
            ) : (
              <ul className="space-y-1 font-mono text-[11px] tabular-nums">
                {detail.recentActivity.slice(0, 20).map((a) => (
                  <li
                    key={a.id}
                    className="flex items-baseline gap-3 text-linear-text-2"
                  >
                    <span className="w-12 shrink-0 text-linear-text-3">
                      {a.timestamp.slice(11, 16)}
                    </span>
                    <span
                      className={cls(
                        'w-44 shrink-0 truncate',
                        a.action === 'LOGIN_FAILED' || !a.success
                          ? 'text-linear-danger'
                          : 'text-linear-text'
                      )}
                    >
                      {a.action}
                    </span>
                    {a.targetType && a.targetId && (
                      <span className="truncate text-linear-text-3">
                        {a.targetType}:{a.targetId.slice(0, 8)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </DrawerSection>

          <div className="px-5 pb-6 pt-2 text-[11px] text-linear-text-3">
            All admin actions on this user are logged to the audit trail.
            {isSelf && (
              <span className="ml-2 text-linear-text-2">
                You can&apos;t suspend, deactivate, edit, delete, or revoke your own
                admin access — ask a peer.
              </span>
            )}
          </div>
        </div>
      </aside>
      {editing && (
        <EditProfileModal
          user={user}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            onActed();
          }}
        />
      )}
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
  const isAdmin = user.isSuperAdmin;
  const isSuspended = user.status === 'suspended';
  const isDeleted = user.status === 'soft_deleted';
  const tones: Array<{ bg: string; fg: string }> = [
    { bg: 'linear-gradient(135deg,#9bc2ab,#6f9b85)', fg: '#0b1611' },
    { bg: 'linear-gradient(135deg,#a5c8dd,#6e95ad)', fg: '#0a1820' },
    { bg: 'linear-gradient(135deg,#e2bd92,#b88752)', fg: '#1c1409' },
    { bg: 'linear-gradient(135deg,#d99a90,#b06b60)', fg: '#fff' },
    { bg: 'linear-gradient(135deg,#b9b2d9,#7e76a8)', fg: '#fff' },
  ];
  const tone = tones[(user.id.charCodeAt(0) || 0) % tones.length]!;
  return (
    <div className="relative inline-block" style={{ width: size, height: size }}>
      <div
        className="flex h-full w-full items-center justify-center rounded-md font-semibold tracking-tight"
        style={{
          background: tone.bg,
          color: tone.fg,
          fontSize: Math.max(10, size * 0.4),
        }}
      >
        {initials(user.fullName)}
      </div>
      {isAdmin && (
        <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-warning ring-1 ring-linear-surface-2">
          <Crown className="h-2 w-2 text-linear-bg" strokeWidth={2.5} />
        </span>
      )}
      {isSuspended && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-warning ring-1 ring-linear-surface-2">
          <PauseCircle className="h-2.5 w-2.5 text-linear-bg" strokeWidth={2.5} />
        </span>
      )}
      {isDeleted && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-danger ring-1 ring-linear-surface-2">
          <X className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
        </span>
      )}
    </div>
  );
}

function StatusInline({ user }: { user: UserListRow }) {
  if (user.status === 'active')
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-sage-bright">
        <span className="h-1.5 w-1.5 rounded-full bg-linear-sage" />
        Active
      </span>
    );
  if (user.status === 'suspended')
    return (
      <span
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-warning"
        title={user.suspendedReason ?? undefined}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-linear-warning" />
        Suspended
      </span>
    );
  if (user.status === 'deactivated')
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-text-3">
        <span className="h-1.5 w-1.5 rounded-full bg-linear-text-3" />
        Deactivated
      </span>
    );
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-danger"
      title={
        user.softDeletedAt
          ? `Soft-deleted ${user.softDeletedAt.slice(0, 10)} by ${user.softDeletedBy ?? '—'}`
          : undefined
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-linear-danger" />
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
    <section className="border-b border-linear-border px-5 py-4 last:border-b-0">
      <div className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3">
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
      <div className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.10em] text-linear-text-3">
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
  // Linear V1 chip palette: neutral surface, warning amber, danger coral.
  const toneStyle: Record<string, React.CSSProperties> = {
    neutral: {
      background: 'var(--color-linear-surface-3)',
      color: 'var(--color-linear-text)',
      boxShadow: 'inset 0 0 0 1px var(--color-linear-border)',
    },
    amber: {
      background: 'rgba(212, 164, 55, 0.15)',
      color: 'var(--color-linear-warning)',
      boxShadow: 'inset 0 0 0 1px rgba(212, 164, 55, 0.30)',
    },
    rose: {
      background: 'rgba(212, 87, 74, 0.15)',
      color: 'var(--color-linear-danger)',
      boxShadow: 'inset 0 0 0 1px rgba(212, 87, 74, 0.30)',
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
        disabled && 'cursor-not-allowed opacity-50'
      )}
      style={toneStyle[tone]}
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
        <span className="font-medium text-linear-text-2">{label}</span>
        <span className="text-linear-text-3">
          <span className="font-mono tabular-nums text-linear-text">${cost.toFixed(2)}</span>
          <span className="mx-1.5 text-linear-text-3">·</span>
          <span className="font-mono tabular-nums">{sub}</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-linear-surface-3">
        <div
          className="h-full rounded-full bg-linear-sage"
          style={{ width: `${pct}%` }}
        />
      </div>
    </li>
  );
}

function DefList({
  rows,
}: {
  rows: { k: string; v: React.ReactNode }[];
}) {
  return (
    <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map((r, i) => (
        <div key={r.k + i} className="contents">
          <dt className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
            {r.k}
          </dt>
          <dd className="text-linear-text">{r.v}</dd>
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
