// ============================================================================
// /settings/security/mfa — MFA enrollment + management surface
// ----------------------------------------------------------------------------
// Closes the BLOCKING_TIER_1 finding HIPAA_FINDING_001 from the
// 2026-05-10 baseline shadow audit (zero MFA coverage on 49 active
// accounts).
//
// Server-rendered shell that decides which client surface to mount:
//   - mfaEnabled=false → enrollment flow (QR + 6-digit verify + recovery codes)
//   - mfaEnabled=true  → "MFA is on" panel + disable + re-issue recovery codes
//
// SUPER_ADMINs land here automatically when they reach /admin/* without
// an enrolled factor — see admin/layout.tsx redirect path. The
// `?reason=super_admin_required` query param triggers a banner
// explaining why they're here.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { MfaEnrollmentPanel } from './mfa-enrollment-panel';
import { MfaManagementPanel } from './mfa-management-panel';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export const metadata: Metadata = {
  title: 'Two-factor authentication · QuillMD',
};

export default async function MfaSettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      id: true,
      email: true,
      role: true,
      mfaEnabled: true,
      mfaVerifiedAt: true,
    },
  });
  if (!user) redirect('/login');

  const params = await searchParams;
  const isSuperAdminGated =
    params.reason === 'super_admin_required' && !user.mfaEnabled;

  return (
    <AppFrame>
      {/* THE BRIDGE, ADOPTED. `/settings/security/mfa` is its OWN route leaf —
          there is no `settings/layout.tsx`, so this page inherits nothing from
          `/settings` and cannot pick up that page's host. This div is the
          highest element the route owns (`AppFrame` is shared chrome for every
          authenticated surface and is not C1-e's to repaint), so the host goes
          here. Applied UNCONDITIONALLY: every rule behind these two classes is
          prefixed `[data-skin='rounds']`, so with the flag off they select
          nothing and the surface renders exactly what it renders today. */}
      <div
        className="qm-rounds-host qm-rounds-settings"
        style={{
          maxWidth: 640,
          margin: '0 auto',
          padding: '24px 24px 80px',
        }}
      >
        {isSuperAdminGated && (
          <div
            role="alert"
            style={{
              marginBottom: 20,
              padding: '12px 14px',
              border: '1px solid rgba(212, 165, 116, 0.36)',
              background: 'rgba(212, 165, 116, 0.08)',
              borderRadius: 8,
              fontFamily: 'var(--font-sans)',
              fontSize: 13,
              lineHeight: 1.5,
              color: 'var(--color-linear-text)',
            }}
          >
            <strong style={{ display: 'block', marginBottom: 4 }}>
              Two-factor authentication required
            </strong>
            <span style={{ color: 'var(--color-linear-text-2)' }}>
              SUPER_ADMIN accounts must enroll a TOTP factor before accessing
              the platform-admin surface. Complete enrollment below to
              continue.
            </span>
          </div>
        )}

        <header style={{ marginBottom: 20 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 600,
              color: 'var(--color-linear-text)',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Two-factor authentication
          </h1>
          <p
            style={{
              margin: '6px 0 0',
              fontSize: 13,
              color: 'var(--color-linear-text-2)',
              fontFamily: 'var(--font-sans)',
            }}
          >
            Adds a 6-digit code from your authenticator app to every sign-in.
            HIPAA §164.312(d) authentication factor.
          </p>
        </header>

        {user.mfaEnabled ? (
          <MfaManagementPanel
            userRole={user.role}
            verifiedAt={user.mfaVerifiedAt?.toISOString() ?? null}
          />
        ) : (
          <MfaEnrollmentPanel userEmail={user.email} />
        )}
      </div>
    </AppFrame>
  );
}
