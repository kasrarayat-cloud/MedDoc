// ============================================================================
// /admin/users — server entry
// ----------------------------------------------------------------------------
// SUPER_ADMIN gate + access audit: requireAdminPage() FIRST (ruling #310 —
// the layout is skipped on an RSC refetch). Then it just reads the
// URL search params, fetches the matching page, and hands the result to
// the client orchestrator.
// ============================================================================

import type { Metadata } from 'next';

import { requireAdminPage } from '../_lib/admin-gate';

import AdminUsers from './_components/AdminUsers.client';
import {
  fetchUserListPage,
  fetchUserStats,
} from './_lib/users-data';
import type { ListParams, ProductFilter, RoleFilter, StatusFilter } from './_types';

export const metadata: Metadata = {
  title: 'Users · QuillMD Admin',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function UsersPage({ searchParams }: Props) {
  const session = await requireAdminPage();
  const sp = await searchParams;
  const params: ListParams = {
    search: typeof sp.search === 'string' ? sp.search : '',
    status: parseStatus(sp.status),
    role: parseRole(sp.role),
    product: parseProduct(sp.product),
    page: parsePage(sp.page),
  };

  const [page, stats] = await Promise.all([
    fetchUserListPage(params),
    fetchUserStats(),
  ]);

  return (
    <AdminUsers
      page={page}
      stats={stats}
      params={params}
      currentUserId={session.user.id}
      currentUserEmail={session.user.email ?? 'admin'}
      theme="clinician"
    />
  );
}

function parseStatus(v: string | string[] | undefined): StatusFilter {
  const s = typeof v === 'string' ? v : '';
  if (s === 'active' || s === 'suspended' || s === 'deleted') return s;
  return 'all';
}
function parseRole(v: string | string[] | undefined): RoleFilter {
  const s = typeof v === 'string' ? v : '';
  if (s === 'doctor' || s === 'admin') return s;
  return 'all';
}
function parseProduct(v: string | string[] | undefined): ProductFilter {
  const s = typeof v === 'string' ? v : '';
  if (s === 'transcribe' || s === 'meddoc' || s === 'both') return s;
  return 'all';
}
function parsePage(v: string | string[] | undefined): number {
  const n = typeof v === 'string' ? Number.parseInt(v, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : 1;
}
