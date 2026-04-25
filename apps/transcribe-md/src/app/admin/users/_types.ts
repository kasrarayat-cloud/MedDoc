// ============================================================================
// Shared types for the /admin/users surface
// ----------------------------------------------------------------------------
// Imported by both the server-side data layer and the client components.
// ============================================================================

export type UserStatus = 'active' | 'suspended' | 'soft_deleted';

/** UI role label — derived from `User.role` + `Product.SUPER_ADMIN`
 *  presence in `User.products`. The row shows `DOCTOR+ADMIN` for the
 *  common case where a clinician has been granted platform-admin. */
export type UserRoleLabel = 'DOCTOR' | 'ADMIN' | 'STAFF' | 'DOCTOR+ADMIN' | 'STAFF+ADMIN';

export interface UserListRow {
  id: string;
  email: string;
  fullName: string;
  role: UserRoleLabel;
  /** True iff `Product.SUPER_ADMIN` is in `products[]` — drives the
   *  Crown overlay on the avatar and the privilege chip. */
  isSuperAdmin: boolean;
  products: string[];
  status: UserStatus;
  suspendedReason: string | null;
  softDeletedAt: string | null;
  softDeletedBy: string | null;
  practiceId: string;
  practiceName: string;
  createdAt: string;
  lastLoginAt: string | null;
  lastLoginIp: string | null;
  activeSessions: number;
  monthSpend: {
    totalCostUsd: number;
    byProvider: Record<
      string,
      { costUsd: number; unitCount: number; unitLabel: string }
    >;
  };
  monthVisits: number;
}

export interface UserListPage {
  users: UserListRow[];
  totalPages: number;
  totalCount: number;
  page: number;
}

export interface UserStats {
  total: number;
  admins: number;
  suspended: number;
}

export type StatusFilter = 'all' | 'active' | 'suspended' | 'deleted';
export type RoleFilter = 'all' | 'doctor' | 'admin';
/** Phase 6D — kasra is the founder of both products and needs to see
 *  both populations by default. The dashboard table also surfaces a
 *  Product column so it's obvious at a glance which app each user
 *  belongs to. */
export type ProductFilter = 'all' | 'transcribe' | 'meddoc' | 'both';

export interface ListParams {
  search: string;
  status: StatusFilter;
  role: RoleFilter;
  product: ProductFilter;
  page: number;
}

export type ConfirmKind = 'soft_delete' | 'grant_admin' | 'revoke_admin';

/** Detail drawer extras — fetched on-demand from the existing
 *  GET /api/admin/users/[id] endpoint. */
export interface UserDetail extends UserListRow {
  recentActivity: Array<{
    id: string;
    timestamp: string;
    action: string;
    targetType: string | null;
    targetId: string | null;
    success: boolean;
    errorCode: string | null;
    ipAddress: string | null;
  }>;
  ipHistory: Array<{
    ipAddress: string;
    firstSeen: string;
    lastSeen: string;
    count: number;
  }>;
}
