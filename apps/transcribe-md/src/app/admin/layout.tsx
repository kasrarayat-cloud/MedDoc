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
import { notFound } from 'next/navigation';

import { Product } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { isAdminSessionStale } from '@/lib/admin-session-freshness';
import CinematicAdminHero from '@/components/admin/CinematicAdminHero';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Phase 2 (Clinician remodel) — Batch G — admin chrome opts in to the
// Clinician token scope by wrapping the rendered subtree in `.qm-cl-app`.
// The SUPER_ADMIN gate, the freshness check, the `notFound()` posture,
// and the access audit log above are unchanged — only the JSX shell
// flips. Every admin page below already gets `theme="clinician"`
// threaded through its own Strategy A branch.

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
  let hasSuperAdmin = products?.includes(Product.SUPER_ADMIN) ?? false;
  if (!hasSuperAdmin && session?.user?.id) {
    const prisma = (await import('@meddoc/db')).default;
    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: { products: true },
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    hasSuperAdmin = (user?.products as any[] | undefined)?.includes(
      Product.SUPER_ADMIN
    ) ?? false;
  }

  if (!hasSuperAdmin) {
    notFound();
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

  // The Clinician chrome lives at the layout boundary so every admin
  // page resolves `.qm-cl-*` class lookups against the warm cream
  // token scope without each page wrapping itself. Mirror of how
  // /dashboard layouts opt in via <AppFrame theme="clinician">.
  //
  // Phase 4 (admin cinematic hero) — a short photo band slots in
  // above the existing nav + dashboard chrome. The band is purely
  // visual: it announces the supervisor view via the lamp-glow
  // photo + "Operations." headline + coral SUPER_ADMIN pill, and
  // hosts the .av1-* animation entry points. The SUPER_ADMIN gate,
  // freshness check, and audit-log write above are unchanged — we
  // pass the gate result down so the badge mirrors gate state.
  return (
    <div className="qm-cl-app min-h-screen">
      <CinematicAdminHero hasSuperAdmin={hasSuperAdmin} />
      <main className="min-h-screen text-clinician-ink">{children}</main>
    </div>
  );
}
