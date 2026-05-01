'use client';

// ============================================================================
// /admin/users — list orchestrator
// ----------------------------------------------------------------------------
// Filters + pagination live in URL search params (so back/forward,
// reload, and link-sharing all work). Search input has a 250ms
// debounce before being committed to the URL. The drawer + confirmation
// modal are pure local state.
//
// After any successful destructive action:
//   1. `router.refresh()` — re-runs the server `page.tsx` and re-fetches
//      the list with current filters (single round-trip, RSC pattern).
//   2. `setRefetchKey(k => k + 1)` — bumps a key the open drawer
//      depends on, so its `/api/admin/users/[id]` detail call also
//      re-runs.
//
// Phase 5 (Linear V1 Faithful) — table + filter rail rendered against
// the dark canvas with mono email/usage/timestamp columns, sage active
// pills, and hairline row separators. The legacy slate-on-white branch
// has been removed; the `theme` prop survives as an ignored compat
// shim.
// ============================================================================

import { useEffect, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  Search,
  Filter,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Crown,
  PauseCircle,
  X,
} from 'lucide-react';

import {
  cls,
  formatUsd,
  initials,
  relativeTime,
} from '../../_lib/admin-format';
import AdminNav from '../../_components/AdminNav.client';
import type {
  ConfirmKind,
  ListParams,
  ProductFilter,
  RoleFilter,
  StatusFilter,
  UserListPage,
  UserListRow,
  UserStats,
} from '../_types';

import ConfirmationModal from './ConfirmationModal.client';
import UserDetailDrawer from './UserDetailDrawer.client';

const PAGE_SIZE = 20;

interface Props {
  page: UserListPage;
  stats: UserStats;
  params: ListParams;
  currentUserId: string;
  currentUserEmail: string;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

export default function AdminUsers({
  page,
  stats,
  params,
  currentUserId,
  currentUserEmail,
}: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [, startTransition] = useTransition();

  const [searchInput, setSearchInput] = useState(params.search);
  const [selected, setSelected] = useState<UserListRow | null>(null);
  const [confirm, setConfirm] = useState<{ kind: ConfirmKind; user: UserListRow } | null>(null);
  const [refetchKey, setRefetchKey] = useState(0);

  // Debounce search → URL
  useEffect(() => {
    const trimmed = searchInput.trim();
    if (trimmed === params.search) return;
    const t = window.setTimeout(() => {
      pushUrl({ search: trimmed, page: 1 });
    }, 250);
    return () => window.clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  function pushUrl(patch: Partial<ListParams>) {
    const next = new URLSearchParams(sp.toString());
    const set = (k: string, v: string | number) => {
      const s = String(v);
      if (s === '' || s === 'all' || (k === 'page' && s === '1')) {
        next.delete(k);
      } else {
        next.set(k, s);
      }
    };
    set('search', patch.search ?? params.search);
    set('status', patch.status ?? params.status);
    set('role', patch.role ?? params.role);
    set('product', patch.product ?? params.product);
    set('page', patch.page ?? params.page);
    startTransition(() => {
      router.push(`/admin/users?${next.toString()}`);
    });
  }

  function clearFilters() {
    setSearchInput('');
    startTransition(() => router.push('/admin/users'));
  }

  function refresh() {
    startTransition(() => {
      router.refresh();
      setRefetchKey((k) => k + 1);
    });
  }

  async function handleConfirm() {
    if (!confirm) return;
    const path =
      confirm.kind === 'soft_delete'
        ? 'soft-delete'
        : confirm.kind === 'grant_admin'
          ? 'grant-admin'
          : 'revoke-admin';
    try {
      const res = await fetch(`/api/admin/users/${confirm.user.id}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmEmail: confirm.user.email }),
      });
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success(
          confirm.kind === 'soft_delete'
            ? 'User soft-deleted'
            : confirm.kind === 'grant_admin'
              ? 'Admin granted'
              : 'Admin revoked'
        );
        setConfirm(null);
        // Keep drawer open so the admin sees the updated state.
        refresh();
      } else {
        toast.error('Action failed', { description: data.error ?? `HTTP ${res.status}` });
      }
    } catch (err) {
      toast.error('Action failed', {
        description: err instanceof Error ? err.message : 'network error',
      });
    }
  }

  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3 mb-1">
              Admin · Users
            </div>
            <h1 className="text-[20px] font-semibold tracking-tight text-linear-text leading-tight">
              People with access
            </h1>
            <div className="mt-1 text-[11px] text-linear-text-3">
              <span className="font-mono tabular-nums text-linear-text-2">{stats.total}</span> total
              <span className="mx-1.5 text-linear-text-3">·</span>
              <span className="font-mono tabular-nums text-linear-text-2">{stats.admins}</span>{' '}
              admin{stats.admins === 1 ? '' : 's'}
              <span className="mx-1.5 text-linear-text-3">·</span>
              <span className="font-mono tabular-nums text-linear-text-2">{stats.suspended}</span>{' '}
              suspended
            </div>
          </div>
          <div className="text-[11px] text-linear-text-3">
            signed in as <span className="font-mono text-linear-text-2">{currentUserEmail}</span>
          </div>
        </div>
      </header>
      <AdminNav />

      <main className="mx-auto max-w-[1440px] px-6 py-5 flex flex-col gap-3">
        <div className="flex flex-col gap-2 rounded-lg border border-linear-border bg-linear-surface-1 px-3 py-2.5 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-linear-text-3" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search name, email, practice…"
              className="block h-8 w-full rounded-md border border-linear-border bg-linear-surface-2 pl-8 pr-3 text-sm text-linear-text placeholder:text-linear-text-3 focus-visible:border-linear-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
            />
          </div>
          <div className="flex items-center gap-2">
            <SelectChip
              value={params.status}
              onChange={(v) => pushUrl({ status: v as StatusFilter, page: 1 })}
              options={[
                { value: 'all', label: 'All status' },
                { value: 'active', label: 'Active' },
                { value: 'suspended', label: 'Suspended' },
                { value: 'deleted', label: 'Deleted' },
              ]}
            />
            <SelectChip
              value={params.role}
              onChange={(v) => pushUrl({ role: v as RoleFilter, page: 1 })}
              options={[
                { value: 'all', label: 'All roles' },
                { value: 'doctor', label: 'Doctors' },
                { value: 'admin', label: 'Admins only' },
              ]}
            />
            <SelectChip
              value={params.product}
              onChange={(v) => pushUrl({ product: v as ProductFilter, page: 1 })}
              options={[
                { value: 'all', label: 'All products' },
                { value: 'transcribe', label: 'QuillMD only' },
                { value: 'meddoc', label: 'MedDoc Pro only' },
                { value: 'both', label: 'Both products' },
              ]}
            />
            <button
              type="button"
              className="qm-lin-btn h-8"
            >
              <Filter className="mr-1 h-3 w-3" />
              More
            </button>
          </div>
        </div>

        <div className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1">
          {page.users.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-linear-surface-2 border border-linear-border">
                <Search className="h-4 w-4 text-linear-text-3" />
              </div>
              <div className="text-sm font-medium text-linear-text-2">
                No users match your filters
              </div>
              <div className="mt-1 text-xs text-linear-text-3">
                Try a different search or clear active filters.
              </div>
              <button
                type="button"
                onClick={clearFilters}
                className="qm-lin-btn mt-4"
              >
                Clear filters
              </button>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left">
                  <Th />
                  <Th>User</Th>
                  <Th>Role</Th>
                  <Th>Product</Th>
                  <Th>Status</Th>
                  <Th>This month</Th>
                  <Th>Last active</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {page.users.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    selected={selected?.id === u.id}
                    onClick={() => setSelected(u)}
                  />
                ))}
              </tbody>
            </table>
          )}
          {page.users.length > 0 && (
            <div className="flex items-center justify-between border-t border-linear-border bg-linear-surface-2/40 px-4 py-2 text-xs">
              <div className="text-linear-text-3">
                Showing{' '}
                <span className="font-mono tabular-nums text-linear-text-2">
                  {(page.page - 1) * PAGE_SIZE + 1}–
                  {Math.min(page.page * PAGE_SIZE, page.totalCount)}
                </span>{' '}
                of{' '}
                <span className="font-mono tabular-nums text-linear-text-2">
                  {page.totalCount}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page.page <= 1}
                  onClick={() => pushUrl({ page: page.page - 1 })}
                  className="qm-lin-btn h-7"
                >
                  <ChevronLeft className="h-3 w-3" />
                  Prev
                </button>
                <span className="font-mono tabular-nums text-linear-text-2">
                  Page {page.page} of {page.totalPages}
                </span>
                <button
                  type="button"
                  disabled={page.page >= page.totalPages}
                  onClick={() => pushUrl({ page: page.page + 1 })}
                  className="qm-lin-btn h-7"
                >
                  Next
                  <ChevronRight className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}
        </div>

        <footer className="pt-4 text-[11px] text-linear-text-3">
          All admin actions on this page are logged. Audit logs retained 7 years per HIPAA
          §164.316(b)(2)(i).
        </footer>
      </main>

      {selected && (
        <UserDetailDrawer
          user={selected}
          currentUserId={currentUserId}
          onClose={() => setSelected(null)}
          onConfirm={(kind, user) => setConfirm({ kind, user })}
          onActed={refresh}
          refetchKey={refetchKey}
        />
      )}
      {confirm && (
        <ConfirmationModal
          kind={confirm.kind}
          user={confirm.user}
          onCancel={() => setConfirm(null)}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components — kept inline because they're only ever used here.
// ---------------------------------------------------------------------------

function Th({ children }: { children?: React.ReactNode }) {
  return (
    <th className="bg-linear-bg py-2.5 px-3 first:pl-4 last:pr-4 font-mono text-[10px] font-medium uppercase tracking-[0.07em] text-linear-text-3 border-b border-linear-border text-left">
      {children}
    </th>
  );
}

function UserRow({
  user,
  selected,
  onClick,
}: {
  user: UserListRow;
  selected: boolean;
  onClick: () => void;
}) {
  const dim = user.status === 'soft_deleted';
  const roleLabel = user.isSuperAdmin ? (
    <span>
      DOCTOR <span className="text-linear-text-3">·</span>{' '}
      <span className="font-medium text-linear-warning">ADMIN</span>
    </span>
  ) : (
    user.role
  );
  return (
    <tr
      onClick={onClick}
      className={cls(
        'cursor-pointer border-t border-linear-border transition-colors',
        selected ? 'bg-linear-row-active' : 'hover:bg-linear-row-hover',
        dim && 'opacity-60'
      )}
    >
      <td className="py-2.5 pl-4 pr-2">
        <Avatar user={user} />
      </td>
      <td className="py-2.5 pr-3">
        <div className="text-sm font-medium text-linear-text">{user.fullName}</div>
        <div className="font-mono text-xs text-linear-text-3">{user.email}</div>
      </td>
      <td className="py-2.5 pr-3 font-mono text-[10px] font-medium uppercase tracking-[0.05em] text-linear-text-2">
        {roleLabel}
      </td>
      <td className="py-2.5 pr-3">
        <ProductCell products={user.products} />
      </td>
      <td className="py-2.5 pr-3">
        <StatusCell user={user} />
      </td>
      <td className="py-2.5 pr-3">
        <div className="font-mono text-sm tabular-nums text-linear-text">
          {formatUsd(user.monthSpend.totalCostUsd)}
        </div>
        {user.monthVisits > 0 && (
          <div className="font-mono text-[11px] tabular-nums text-linear-text-3">
            {user.monthVisits} visits
          </div>
        )}
      </td>
      <td className="py-2.5 pr-3 font-mono text-xs tabular-nums text-linear-text-2">
        {relativeTime(user.lastLoginAt)}
      </td>
      <td className="py-2.5 pr-4 text-right">
        <ChevronRight className="inline h-3.5 w-3.5 text-linear-text-3" />
      </td>
    </tr>
  );
}

function Avatar({ user }: { user: UserListRow }) {
  const isAdmin = user.isSuperAdmin;
  const isSuspended = user.status === 'suspended';
  const isDeleted = user.status === 'soft_deleted';
  const size = 28;
  // Pick a Linear V1 avatar tone deterministically from id char-code.
  // Mirror admin-v1.html's row-initials gradient palette.
  const tones: Array<{ bg: string; fg: string }> = [
    { bg: 'linear-gradient(135deg,#9bc2ab,#6f9b85)', fg: '#0b1611' }, // sage
    { bg: 'linear-gradient(135deg,#a5c8dd,#6e95ad)', fg: '#0a1820' }, // sky
    { bg: 'linear-gradient(135deg,#e2bd92,#b88752)', fg: '#1c1409' }, // amber
    { bg: 'linear-gradient(135deg,#d99a90,#b06b60)', fg: '#fff' }, // coral
    { bg: 'linear-gradient(135deg,#b9b2d9,#7e76a8)', fg: '#fff' }, // violet
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
        <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-warning ring-1 ring-linear-bg">
          <Crown className="h-2 w-2 text-linear-bg" strokeWidth={2.5} />
        </span>
      )}
      {isSuspended && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-warning ring-1 ring-linear-bg">
          <PauseCircle className="h-2.5 w-2.5 text-linear-bg" strokeWidth={2.5} />
        </span>
      )}
      {isDeleted && (
        <span className="absolute -right-0.5 -bottom-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-linear-danger ring-1 ring-linear-bg">
          <X className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
        </span>
      )}
    </div>
  );
}

function StatusCell({ user }: { user: UserListRow }) {
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
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-danger">
      <span className="h-1.5 w-1.5 rounded-full bg-linear-danger" />
      Deleted
    </span>
  );
}

function ProductCell({ products }: { products: string[] }) {
  const hasTm = products.includes('TRANSCRIBE_MD');
  const hasMp = products.includes('MEDDOC_PRO');
  if (!hasTm && !hasMp) return <span className="text-[11px] text-linear-text-3">—</span>;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {hasTm && (
        <span
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium"
          style={{
            background: 'rgba(91, 163, 180, 0.15)',
            color: 'var(--color-linear-teal)',
          }}
        >
          QuillMD
        </span>
      )}
      {hasMp && (
        <span
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium"
          style={{
            background: 'rgba(116, 168, 201, 0.15)',
            color: 'var(--color-linear-sky)',
          }}
        >
          MedDoc Pro
        </span>
      )}
    </div>
  );
}

function SelectChip({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 cursor-pointer appearance-none rounded-md border border-linear-border bg-linear-surface-2 py-0 pl-2.5 pr-7 text-xs font-medium text-linear-text-2 hover:border-linear-border-strong hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-linear-surface-2 text-linear-text">
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-linear-text-3" />
    </div>
  );
}
