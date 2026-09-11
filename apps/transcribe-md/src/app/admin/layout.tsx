// ============================================================================
// Platform-admin layout (Phase 1A scaffolding)
// ----------------------------------------------------------------------------
// Gate for the new /admin/* surface. Only a user with Product.SUPER_ADMIN
// on their account can reach these pages. Everyone else — unauthenticated
// visitors, doctors, practice admins, anonymous crawlers — gets a 404.
// We deliberately use `notFound()` rather than `redirect('/login')` so
// the existence of /admin isn't revealed to someone probing routes.
//
// This is distinct from /system-admin, which is a practice-admin surface
// gated on `user.role === 'ADMIN' | 'SUPER_ADMIN'` (an RBAC role on the
// User model). The new /admin surface is platform-wide and gated on a
// Product-level entitlement; the intersection is not empty but the
// permissions aren't identical — a practice ADMIN is not a SUPER_ADMIN.
//
// ⚠️ RULING #310 — THIS LAYOUT IS **NOT** THE GATE ANY MORE, AND NEVER WAS
// A SUFFICIENT ONE. Next 16 does not re-run a layout on an RSC subtree
// refetch (`RSC: 1` + a Next-Router-State-Tree marking /admin as already
// rendered): only the page renders. With the checks living here alone, an
// unauthenticated request got /admin/hipaa's data back with a 200 and no
// audit row. The checks now live in `_lib/admin-gate.ts` and are called
// FIRST by every page and every data helper. This layout calls the SAME
// verdict (requireAdminPage) so a full render behaves exactly as before —
// 404 for non-admins, the MFA enrolment redirect, 404 on a >12h session,
// one ADMIN_DASHBOARD_ACCESS row (request-cached, so the page's own call
// does not write a second one).
// ============================================================================

import { requireAdminPage } from './_lib/admin-gate';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Phase 5 (Linear V1 Faithful) — admin chrome inherits the same dark
// canvas as the rest of the product. The SUPER_ADMIN gate, the freshness
// check, the `notFound()` posture, and the access audit log are
// unchanged in behaviour — only where they are defined moved (ruling #310).

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // SUPER_ADMIN (fresh DB read) → notFound; MFA not enrolled → redirect to
  // enrolment; session older than 12h → notFound; then the access audit.
  await requireAdminPage();

  // Phase 5 — Linear V1 chrome lives at the layout boundary so every
  // admin page renders against the dark canvas without each page
  // wrapping itself.
  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <main className="min-h-screen">{children}</main>
    </div>
  );
}
