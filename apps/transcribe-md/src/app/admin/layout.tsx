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
// This layout is an outer-shell and MFA-routing defense only. Next can reuse a
// mounted layout during client navigation, so every page invokes the fresh
// database-backed gate again before reading protected data.
// ============================================================================

import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { auth } from "@/lib/nextauth";
import { isAdminRequestHost } from "@/lib/admin-host";
import { verifyFreshPlatformAdminSession } from "@/lib/admin-session-freshness";

export const dynamic = "force-dynamic";
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
  const h = await headers();
  if (!isAdminRequestHost(h)) notFound();

  const session = await auth().catch(() => null);
  const verified = await verifyFreshPlatformAdminSession({
    claimedUserId: session?.user?.id,
    sessionId: session?.user?.sessionId,
    requireMfa: false,
  });
  if (!verified) notFound();

  // SUPER_ADMIN MFA gate (closes shadow-audit HIPAA_FINDING_001).
  // SUPER_ADMINs MUST have MFA enrolled before reaching any /admin/*
  // page. We redirect to the enrollment surface rather than 404 so
  // the operator can self-recover; the redirect URL itself doesn't
  // leak the admin gate (the user is already authenticated at this
  // point + already known to be SUPER_ADMIN). DB read is fresh — we
  // don't trust a JWT-cached mfaEnabled flag because enrollment
  // happens in-session.
  if (!verified.mfaEnabled || !verified.mfaVerifiedAt) {
    redirect("/settings/security/mfa?reason=super_admin_required");
  }

  // Phase 19 — h16-admin-session-7day. Cookie itself stays 7 days
  // (so app.quillmd.com doesn't bounce doctors hourly), but admin
  // pages enforce a 12-h freshness ceiling on top of the SUPER_ADMIN
  // gate. Stale → notFound (same disclosure-minimising posture).
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
