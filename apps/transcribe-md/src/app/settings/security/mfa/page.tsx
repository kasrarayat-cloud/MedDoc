// ============================================================================
// /settings/security/mfa — MFA enrollment + management surface
// ----------------------------------------------------------------------------
// Closes the BLOCKING_TIER_1 finding HIPAA_FINDING_001 from the
// 2026-05-10 baseline shadow audit (zero MFA coverage on 49 active
// accounts).
//
// Server-rendered shell that decides which client surface to mount:
//   - mfaEnabled=false → enrollment flow (QR + 6-digit verify + recovery codes)
//   - complete enrollment → "MFA is on" panel (platform admins cannot disable)
//   - inconsistent enabled record → fail-closed controlled-repair guidance
//
// SUPER_ADMINs land here automatically when they reach /admin/* without
// an enrolled factor — see admin/layout.tsx redirect path. The
// `?reason=super_admin_required` query param triggers a banner
// explaining why they're here.
// ============================================================================

import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

import prisma from "@meddoc/db";
import { Product } from "@prisma/client";
import { auth } from "@/lib/nextauth";
import { isAdminRequestHost } from "@/lib/admin-host";
import { requireFreshPlatformAdminPage } from "@/lib/admin-page-gate";
import { AppFrame } from "@/components/ui/app-frame";
import { MfaEnrollmentPanel } from "./mfa-enrollment-panel";
import { MfaManagementPanel } from "./mfa-management-panel";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Two-factor authentication · QuillMD",
};

export default async function MfaSettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const requestHeaders = await headers();
  const isAdminHost = isAdminRequestHost(requestHeaders);
  let userId: string;
  if (isAdminHost) {
    const verified = await requireFreshPlatformAdminPage({
      routeKey: "/settings/security/mfa",
      requireMfa: false,
    });
    userId = verified.userId;
  } else {
    const session = await auth();
    if (!session?.user?.id) redirect("/login");
    userId = session.user.id;
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      products: true,
      mfaEnabled: true,
      mfaSecret: true,
      mfaVerifiedAt: true,
    },
  });
  if (!user) {
    if (isAdminHost) notFound();
    redirect("/login");
  }

  const params = await searchParams;
  const hasCompleteMfaEnrollment =
    user.mfaEnabled && !!user.mfaSecret && user.mfaVerifiedAt !== null;
  const hasInconsistentMfaEnrollment =
    user.mfaEnabled && !hasCompleteMfaEnrollment;
  const isSuperAdminGated =
    isAdminHost ||
    (params.reason === "super_admin_required" && !hasCompleteMfaEnrollment);

  const content = (
    <div
      style={{
        maxWidth: 640,
        margin: "0 auto",
        padding: "24px 24px 80px",
      }}
    >
      {isSuperAdminGated && !hasCompleteMfaEnrollment && (
        <div
          role="alert"
          style={{
            marginBottom: 20,
            padding: "12px 14px",
            border: "1px solid rgba(212, 165, 116, 0.36)",
            background: "rgba(212, 165, 116, 0.08)",
            borderRadius: 8,
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            lineHeight: 1.5,
            color: "var(--color-linear-text)",
          }}
        >
          <strong style={{ display: "block", marginBottom: 4 }}>
            Two-factor authentication required
          </strong>
          <span style={{ color: "var(--color-linear-text-2)" }}>
            Platform administrators must enroll a TOTP factor before accessing
            administrative data. Complete enrollment below to continue.
          </span>
        </div>
      )}

      <header style={{ marginBottom: 20 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 600,
            color: "var(--color-linear-text)",
            fontFamily: "var(--font-sans)",
          }}
        >
          Two-factor authentication
        </h1>
        <p
          style={{
            margin: "6px 0 0",
            fontSize: 13,
            color: "var(--color-linear-text-2)",
            fontFamily: "var(--font-sans)",
          }}
        >
          Adds a 6-digit code from your authenticator app to every sign-in.
          HIPAA §164.312(d) authentication factor.
        </p>
      </header>

      {hasInconsistentMfaEnrollment ? (
        <section
          role="alert"
          style={{
            background: "var(--color-linear-surface-1)",
            border: "1px solid rgba(212, 165, 116, 0.36)",
            borderRadius: 10,
            padding: 22,
          }}
        >
          <h2
            style={{
              margin: "0 0 8px",
              color: "var(--color-linear-text)",
              fontFamily: "var(--font-sans)",
              fontSize: 16,
              fontWeight: 600,
            }}
          >
            MFA configuration requires controlled repair
          </h2>
          <p
            style={{
              margin: 0,
              color: "var(--color-linear-text-2)",
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              lineHeight: 1.55,
            }}
          >
            Administrative access remains blocked because the enrolled-factor
            record is incomplete. Sign out and contact the designated security
            or operations owner. This page cannot disable, replace, or infer
            the missing factor.
          </p>
        </section>
      ) : isAdminHost && hasCompleteMfaEnrollment ? (
        <section
          style={{
            background: "var(--color-linear-surface-1)",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 10,
            padding: 22,
          }}
        >
          <p
            style={{
              margin: "0 0 16px",
              color: "var(--color-linear-text-2)",
              fontFamily: "var(--font-sans)",
              fontSize: 13,
            }}
          >
            MFA is enrolled. Administrative MFA cannot be disabled from this
            recovery surface.
          </p>
          <Link href="/admin" className="qm-lin-btn-primary">
            Continue to admin
          </Link>
        </section>
      ) : hasCompleteMfaEnrollment ? (
        <MfaManagementPanel
          isPlatformAdmin={user.products.includes(Product.SUPER_ADMIN)}
          verifiedAt={user.mfaVerifiedAt?.toISOString() ?? null}
        />
      ) : (
        <MfaEnrollmentPanel
          userEmail={user.email}
          completionHref={isAdminHost ? "/admin" : "/settings"}
        />
      )}
    </div>
  );

  if (isAdminHost) {
    return (
      <main className="min-h-screen bg-linear-bg text-linear-text">
        {content}
      </main>
    );
  }
  return <AppFrame>{content}</AppFrame>;
}
