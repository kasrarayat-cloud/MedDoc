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

import { notFound } from 'next/navigation';

import { Product } from '@prisma/client';
import { auth } from '@/lib/nextauth';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

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

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      {children}
    </main>
  );
}
