import Link from 'next/link';

import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { AnimatedGrid } from '@/components/animated-grid';

export default function NotFound() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
      <AnimatedGrid />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[600px]"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(139,92,246,0.18) 0%, rgba(124,58,237,0.05) 45%, transparent 75%)',
        }}
      />
      <div className="relative z-10">
        <div className="mb-4 text-[12px] font-medium tracking-wider text-text-muted">
          404
        </div>
        <h1 className="type-display mb-4">
          <GradientText>Not here.</GradientText>
        </h1>
        <p className="mx-auto mb-8 max-w-md text-[15px] text-text-tertiary">
          We couldn&apos;t find that page. It may have moved, or you may not have
          access.
        </p>
        <div className="flex items-center justify-center gap-3">
          <SpecularButton href="/dashboard" variant="primary" size="md">
            Go to dashboard
          </SpecularButton>
          <Link
            href="/login"
            className="text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
          >
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
