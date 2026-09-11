// ============================================================================
// /admin gate — ONE verdict, read close to the data (owner ruling #310)
// ----------------------------------------------------------------------------
// WHY THIS EXISTS. `app/admin/layout.tsx` used to be the ONLY gate for every
// /admin page. Next 16 does not re-run a layout on an RSC subtree refetch: a
// request carrying `RSC: 1` and a `Next-Router-State-Tree` that marks /admin as
// already rendered (leaf marked "refetch") renders ONLY the page. Verified on
// the shipped QA image with no cookie at all: GET /admin/hipaa came back 200
// with the hipaaFinding rows in the flight payload, and the layout's
// SUPER_ADMIN / MFA / 12h-freshness checks and its ADMIN_DASHBOARD_ACCESS audit
// never ran. The framework's own guide says so — node_modules/next/dist/docs/
// 01-app/02-guides/authentication.md, "Layouts and auth checks": do the check
// close to the data, not in the layout.
//
// SO THE CHECK NOW LIVES IN THREE PLACES THAT SHARE ONE VERDICT:
//   - the layout            → requireAdminPage()   (full renders)
//   - every admin page.tsx  → requireAdminPage()   FIRST, before any data call
//   - every admin data fn   → assertSuperAdminCaller() FIRST
// A derived test (src/lib/__tests__/gate-310-admin-gate-derived.test.ts) reads
// the filesystem and reds on any page or data function without its gate call.
//
// ONE READ PER REQUEST. `readAdminVerdict` is wrapped in React `cache()`, so a
// full render (layout + page + N data helpers) does one auth() + one user row
// read + one freshness read. The access audit is cached the same way, so a full
// render writes ONE ADMIN_DASHBOARD_ACCESS row even though both the layout and
// the page call requireAdminPage(). Outside a React render (an adminApi route
// handler) `cache()` has no request scope and simply calls through — every
// assertSuperAdminCaller() then re-reads fresh, which is the safe direction.
//
// ORDER MATCHES THE LAYOUT AS IT STOOD: not a SUPER_ADMIN → 404, then MFA not
// enrolled → redirect to enrolment, then session older than 12h → 404. A
// non-admin therefore never learns /admin exists from a redirect.
// ============================================================================

import 'server-only';

import { cache } from 'react';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { Product } from '@prisma/client';

import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { isAdminSessionStale } from '@/lib/admin-session-freshness';
import type { AdminSession } from '@/lib/admin-api-gate';
import { AdminAccessDeniedError } from '@/lib/admin-access-denied';

export { AdminAccessDeniedError };

/** The one answer every /admin door acts on. Only `ok` carries a session. */
export type AdminVerdict =
  | {
      kind: 'denied';
      reason: 'no-session' | 'no-user' | 'inactive' | 'not-super-admin';
    }
  | { kind: 'mfa-required' }
  | { kind: 'stale' }
  | { kind: 'ok'; session: AdminSession };

/** The MFA enrolment redirect, byte-for-byte what the layout issued on main. */
export const SUPER_ADMIN_MFA_REDIRECT =
  '/settings/security/mfa?reason=super_admin_required';

/**
 * Fresh read of the caller: session via auth(), then the user row's
 * products / isActive / mfaEnabled from the DB (never the JWT — a revoked
 * SUPER_ADMIN or an in-session MFA enrolment must take effect immediately),
 * then the 12h freshness ceiling via the SAME helper the layout and adminApi
 * use. Request-cached.
 */
export const readAdminVerdict = cache(async (): Promise<AdminVerdict> => {
  // Fail closed: an auth() that throws is treated as no session (adminApi's
  // posture), never as a pass.
  const session = await auth().catch(() => null);
  const userId = session?.user?.id;
  if (!userId) return { kind: 'denied', reason: 'no-session' };

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { products: true, isActive: true, mfaEnabled: true },
  });
  if (!user) return { kind: 'denied', reason: 'no-user' };
  if (!user.isActive) return { kind: 'denied', reason: 'inactive' };
  const products: readonly unknown[] = Array.isArray(user.products)
    ? user.products
    : [];
  if (!products.includes(Product.SUPER_ADMIN)) {
    return { kind: 'denied', reason: 'not-super-admin' };
  }

  // SUPER_ADMIN MFA gate (shadow-audit HIPAA_FINDING_001). Read fresh from
  // the row above — enrolment happens in-session, so a JWT flag is stale
  // exactly when it matters.
  if (!user.mfaEnabled) return { kind: 'mfa-required' };

  // Phase 19 — h16-admin-session-7day. The 12h ceiling on top of the 7-day
  // cookie. Same helper as the layout used and as adminApi uses.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const u = session!.user as any;
  const sessionId = u.sessionId as string | undefined;
  if (await isAdminSessionStale(sessionId)) return { kind: 'stale' };

  return {
    kind: 'ok',
    session: {
      user: {
        id: userId,
        email: u.email ?? null,
        role: u.role ?? null,
        practiceId: u.practiceId ?? null,
      },
    },
  };
});

/**
 * "Who watched the watcher" — one ADMIN_DASHBOARD_ACCESS row per request.
 * Request-cached so the layout and the page (both of which call
 * requireAdminPage on a full render) produce a single row. The path logic is
 * the layout's, unchanged.
 */
const recordAdminPageAccess = cache(async (): Promise<void> => {
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
});

/**
 * PAGE semantics. Call as the FIRST statement of every /admin page.tsx (and
 * the layout). Not a SUPER_ADMIN / inactive / stale → notFound() (the
 * disclosure-minimising 404); SUPER_ADMIN without MFA → redirect to
 * enrolment; otherwise writes the access audit once and returns the session.
 */
export async function requireAdminPage(): Promise<AdminSession> {
  const verdict = await readAdminVerdict();
  if (verdict.kind === 'mfa-required') {
    redirect(SUPER_ADMIN_MFA_REDIRECT);
  }
  if (verdict.kind !== 'ok') {
    notFound();
  }
  await recordAdminPageAccess();
  return verdict.session;
}

/**
 * DATA semantics. Call as the FIRST statement of every exported async data
 * function under app/admin/**\/_lib. Throws AdminAccessDeniedError for any
 * verdict but `ok` — no notFound()/redirect(), so it is equally correct under
 * a page render and under an adminApi route handler (which maps the error to
 * its silent 404). Writes no audit: pages audit via requireAdminPage and
 * adminApi writes ADMIN_API_ACCESS itself.
 */
export async function assertSuperAdminCaller(): Promise<AdminSession> {
  const verdict = await readAdminVerdict();
  if (verdict.kind !== 'ok') {
    throw new AdminAccessDeniedError(verdict.kind);
  }
  return verdict.session;
}
