import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { auth } from "@/lib/nextauth";
import { AuthShell } from "@/components/ui/auth-shell";
import { ResetPasswordForm } from "./reset-password-form";

export const metadata: Metadata = {
  title: "Set new password",
  referrer: "no-referrer",
};

interface PageProps {
  searchParams: Promise<{ token?: string | string[] }>;
}

export default async function ResetPasswordPage({ searchParams }: PageProps) {
  const session = await auth();
  if (session?.user?.id) redirect("/dashboard");

  const sp = await searchParams;
  const rawToken = Array.isArray(sp.token) ? sp.token[0] : sp.token;
  const token = typeof rawToken === "string" ? rawToken : "";

  return (
    <AuthShell
      eyebrow="Account recovery"
      title={
        <>
          Set new <em>password</em>
        </>
      }
      subtitle="Pick a new password. You'll be signed out everywhere when it saves."
    >
      <ResetPasswordForm token={token} />
    </AuthShell>
  );
}
