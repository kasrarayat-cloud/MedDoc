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
// Defense-in-depth: the auth() call below is a server-side read of the
// JWT cookie; the Product.SUPER_ADMIN presence is re-checked on every
// request. No cached-layout bypass is possible.
// ============================================================================

import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import { hasSuperAdminProduct } from '@/lib/super-admin';
import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { isAdminSessionStale } from '@/lib/admin-session-freshness';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Phase 5 (Linear V1 Faithful) — admin chrome inherits the same dark
// canvas as the rest of the product. The SUPER_ADMIN gate, the freshness
// check, the `notFound()` posture, and the access audit log below are
// unchanged — only the JSX shell flips. The Phase 4 cinematic hero has
// been retired in favour of Linear-density admin layouts (KPI strip,
// users table, threat list).

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const products = (session?.user as any)?.products as string[] | undefined;

  // `products` isn't in the NextAuth session shape today — fall back to
  // a DB read when the JWT doesn't carry it. Same strategy as Phase 1B
  // admin APIs will use; kept local to the layout so we don't leak the
  // Prisma dependency into every admin page.
  // ONE predicate, shared with the API gate and the MFA-disable lock
  // (lib/super-admin.ts). It is array-only: a bare string no longer passes
  // by substring the way `'SUPER_ADMIN'.includes('SUPER_ADMIN')` did.
  let hasSuperAdmin = hasSuperAdminProduct(products);
  if (!hasSuperAdmin && session?.user?.id) {
    const prisma = (await import('@meddoc/db')).default;
    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: { products: true },
    });
    hasSuperAdmin = hasSuperAdminProduct(user?.products);
  }

  if (!hasSuperAdmin) {
    notFound();
  }

  // SUPER_ADMIN MFA gate (closes shadow-audit HIPAA_FINDING_001).
  // SUPER_ADMINs MUST have MFA enrolled before reaching any /admin/*
  // page. We redirect to the enrollment surface rather than 404 so
  // the operator can self-recover; the redirect URL itself doesn't
  // leak the admin gate (the user is already authenticated at this
  // point + already known to be SUPER_ADMIN). DB read is fresh — we
  // don't trust a JWT-cached mfaEnabled flag because enrollment
  // happens in-session.
  if (session?.user?.id) {
    const prismaForMfa = (await import('@meddoc/db')).default;
    const mfaUser = await prismaForMfa.user.findUnique({
      where: { id: session.user.id },
      select: { mfaEnabled: true },
    });
    if (!mfaUser?.mfaEnabled) {
      redirect('/settings/security/mfa?reason=super_admin_required');
    }
  }

  // Phase 19 — h16-admin-session-7day. Cookie itself stays 7 days
  // (so app.quillmd.com doesn't bounce doctors hourly), but admin
  // pages enforce a 12-h freshness ceiling on top of the SUPER_ADMIN
  // gate. Stale → notFound (same disclosure-minimising posture).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sessionId = (session?.user as any)?.sessionId as string | undefined;
  if (await isAdminSessionStale(sessionId)) {
    notFound();
  }

  // "Who watched the watcher" audit — every /admin/* render by a
  // SUPER_ADMIN gets a row. Path resolves from the Next-URL header
  // (populated by the Next.js runtime on every RSC request); falls
  // back to the bare `/admin` when that header isn't set (shouldn't
  // happen in production but keeps the audit call best-effort).
  const h = await headers();
  const nextUrlHeader =
    h.get('next-url') ??
    h.get('x-invoke-path') ??
    h.get('x-pathname') ??
    '/admin';
  // Some Next.js versions embed query string + segment trees in the
  // `next-url` header. Slice to the first space / newline / query
  // marker so we record only the path.
  const path = nextUrlHeader.split(/[\s?#]/)[0];
  void logAudit({
    action: 'ADMIN_DASHBOARD_ACCESS',
    targetType: 'AdminDashboard',
    targetId: path,
    metadata: { path },
  });

  // Phase 5 — Linear V1 chrome lives at the layout boundary so every
  // admin page renders against the dark canvas without each page
  // wrapping itself. The SUPER_ADMIN gate, freshness check, and
  // audit-log write above are unchanged.
  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <main className="min-h-screen">{children}</main>
    </div>
  );
}
