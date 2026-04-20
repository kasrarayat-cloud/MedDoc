import type { Metadata } from 'next';

import { AnimatedGrid } from '@/components/animated-grid';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { CheckEmailResend } from './check-email-resend';

export const metadata: Metadata = { title: 'Check your email' };

interface PageProps {
  searchParams: Promise<{ email?: string | string[] }>;
}

export default async function CheckEmailPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const rawEmail = Array.isArray(sp.email) ? sp.email[0] : sp.email;
  const email = typeof rawEmail === 'string' ? rawEmail : '';

  return (
    <main className="relative min-h-screen overflow-hidden">
      <AnimatedGrid />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[600px]"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(139,92,246,0.2) 0%, rgba(124,58,237,0.05) 45%, transparent 75%)',
        }}
      />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-16">
        <GradientBorder className="w-full">
          <div className="p-8">
            <div className="mb-6 text-center">
              <div className="mb-3 flex items-center justify-center gap-2 text-[13px] font-semibold tracking-tight text-text-primary">
                <span
                  aria-hidden
                  className="inline-block h-3 w-3 rounded-full bg-[radial-gradient(circle_at_30%_30%,#C4B5FD_0%,#7C3AED_55%,#4C1D95_100%)] shadow-[0_0_12px_rgba(139,92,246,0.6)]"
                />
                TranscribeMD
              </div>
              <h1 className="type-h1">
                <GradientText>Check your email</GradientText>
              </h1>
              <p className="mt-2 text-[13px] text-text-tertiary">
                {email
                  ? `We sent a verification link to ${email}.`
                  : 'We sent a verification link to your email.'}
              </p>
              <p className="mt-1 text-[13px] text-text-muted">
                It expires in 24 hours. Click it to activate your account.
              </p>
            </div>

            <CheckEmailResend email={email} />
          </div>
        </GradientBorder>
      </div>
    </main>
  );
}
