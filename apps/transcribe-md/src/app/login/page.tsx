import type { Metadata } from "next";
import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

import { auth } from "@/lib/nextauth";
import prisma from "@meddoc/db";
import { isAdminRequestHost } from "@/lib/admin-host";
import {
  TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH,
  templateTwinAdminLandingPath,
} from "@/lib/template-twin/admin-app-service";
import { AuthShell } from "@/components/ui/auth-shell";
import { LoginForm } from "./login-form";
import { VerifyToast } from "./verify-toast";

// Root layout noindexes all of app.quillmd.com; re-enable for /login
// so the public entry page can be surfaced via search.
export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: true, follow: true },
};

export default async function LoginPage() {
  const session = await auth();
  if (session?.user?.id) {
    // Host-aware redirect: an admin-process session lands on one of the two
    // exact isolated surfaces selected from fresh role/product authority,
    // never the broad physician `/admin` or `/dashboard` routes.
    const h = await headers();
    if (isAdminRequestHost(h)) {
      const currentUser = await prisma.user.findUnique({
        where: { id: session.user.id },
        select: {
          role: true,
          products: true,
          mfaEnabled: true,
          mfaSecret: true,
          mfaVerifiedAt: true,
        },
      });
      redirect(
        (currentUser && templateTwinAdminLandingPath(currentUser)) ??
          TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH,
      );
    }
    redirect("/dashboard");
  }

  return (
    <>
      <Suspense fallback={null}>
        <VerifyToast />
      </Suspense>
      <AuthShell
        eyebrow="Welcome back"
        title={
          <>
            Sign <em>in</em>
          </>
        }
        subtitle="Continue to your clinical workspace."
      >
        <LoginForm />
      </AuthShell>
    </>
  );
}
