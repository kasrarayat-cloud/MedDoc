// Visit-specific 404 — fires when visits/[id]/page.tsx calls
// notFound() (the visit doesn't exist OR belongs to another user —
// both cases return 404 to prevent ID enumeration).

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function VisitNotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
      <div className="mb-6 font-mono text-[64px] leading-none text-text-muted">
        404
      </div>
      <h1 className="type-h1 text-text-primary">Visit not found</h1>
      <p className="mt-3 max-w-md text-[14px] leading-relaxed text-text-tertiary">
        This visit doesn&apos;t exist or you don&apos;t have access to it.
      </p>
      <div className="mt-10">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
