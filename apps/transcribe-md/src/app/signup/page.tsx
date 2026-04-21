import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import { auth } from '@/lib/nextauth';
import { AnimatedGrid } from '@/components/animated-grid';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SignupForm } from './signup-form';

export const metadata: Metadata = { title: 'Sign up' };

export default async function SignupPage() {
  const session = await auth();
  if (session?.user?.id) {
    redirect('/dashboard');
  }

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

      <div className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-12">
        <GradientBorder className="w-full">
          <div className="p-8">
          <div className="mb-6 text-center">
            <div className="mb-3 flex items-center justify-center gap-2 text-[13px] font-semibold tracking-tight text-text-primary">
              <span
                aria-hidden
                className="inline-block h-3 w-3 rounded-full bg-[radial-gradient(circle_at_30%_30%,#C4B5FD_0%,#7C3AED_55%,#4C1D95_100%)] shadow-[0_0_12px_rgba(139,92,246,0.6)]"
              />
              QuillMD
            </div>
            <h1 className="type-h1">
              <GradientText>Create your account</GradientText>
            </h1>
            <p className="mt-2 text-[13px] text-text-tertiary">
              Free for 14 days. No credit card.
            </p>
          </div>

          <SignupForm />
          </div>
        </GradientBorder>
      </div>
    </main>
  );
}
