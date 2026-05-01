// Visit-specific 404 — fires when visits/[id]/page.tsx calls
// notFound() (the visit doesn't exist OR belongs to another user —
// both cases return 404 to prevent ID enumeration).
//
// Phase 5 (Linear V1) — renders on the dark canvas. not-found.tsx is
// outside the AppFrame boundary so the wrapper sets linear-bg
// directly. Mono "404" tag in linear-text-3, Inter headline in
// linear-text, ghost back link.

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function VisitNotFound() {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--color-linear-bg)',
        color: 'var(--color-linear-text)',
      }}
    >
      <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
        <div
          className="mb-6 font-mono leading-none"
          style={{
            fontSize: 64,
            color: 'var(--color-linear-text-3)',
          }}
        >
          404
        </div>
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 24,
            fontWeight: 500,
            letterSpacing: '-0.012em',
            lineHeight: 1.2,
            color: 'var(--color-linear-text)',
          }}
        >
          Visit not found
        </h1>
        <p
          style={{
            marginTop: 12,
            maxWidth: 420,
            fontSize: 13.5,
            lineHeight: 1.55,
            color: 'var(--color-linear-text-2)',
          }}
        >
          This visit doesn&apos;t exist or you don&apos;t have access to it.
        </p>
        <div className="mt-10">
          <Link href="/dashboard" className="qm-lin-btn">
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to dashboard
          </Link>
        </div>
      </main>
    </div>
  );
}
