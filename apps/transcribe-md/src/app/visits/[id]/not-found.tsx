// Visit-specific 404 — fires when visits/[id]/page.tsx calls
// notFound() (the visit doesn't exist OR belongs to another user —
// both cases return 404 to prevent ID enumeration).
//
// Phase 2 (Clinician remodel) — the visit-detail route opts into the
// Clinician chrome via `<AppFrame theme="clinician">`. This not-found
// route falls outside that boundary (Next renders not-found.tsx as a
// route fallback, not a child of the page that mounts AppFrame), so
// we wrap it directly in `.qm-cl-app` so the cream canvas + warm
// charcoal ink resolve correctly. Mockup-aligned: serif headline, ink-3
// body, sage-deep "Back to dashboard" link.

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function VisitNotFound() {
  return (
    <div className="qm-cl-app min-h-screen bg-clinician-cream">
      <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
        <div className="mb-6 font-mono text-[64px] leading-none text-clinician-ink-4">
          404
        </div>
        <h1 className="qm-cl-serif text-[28px] font-medium leading-tight text-clinician-ink">
          Visit not found
        </h1>
        <p className="mt-3 max-w-md text-[14px] leading-relaxed text-clinician-ink-3">
          This visit doesn&apos;t exist or you don&apos;t have access to it.
        </p>
        <div className="mt-10">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-clinician-ink-2 transition-colors hover:bg-clinician-cream-2 hover:text-clinician-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to dashboard
          </Link>
        </div>
      </main>
    </div>
  );
}
