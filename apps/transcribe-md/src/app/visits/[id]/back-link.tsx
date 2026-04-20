'use client';

// ============================================================================
// Back-link variants for visit + patient detail pages
// ----------------------------------------------------------------------------
// Two shapes, one file, shared chrome. Used by /visits/[id] and
// /patients/[id] — the former's natural parent is the patient
// (T-M17.3 UX call; doctors mostly open a visit from a patient's
// timeline), the latter's natural parent is the dashboard.
// ============================================================================

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

const LINK_CLASSES =
  'relative z-10 inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base';

function BackLink({ href, label }: { href: string; label: string }) {
  const router = useRouter();
  return (
    <a
      href={href}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        router.push(href);
      }}
      className={LINK_CLASSES}
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      {label}
    </a>
  );
}

/** Back link for /visits/[id]. Defaults to the patient detail page
 *  (where the doctor most likely opened this visit from). Falls back
 *  to /dashboard when `patientId` is null — defensive against legacy
 *  rows that pre-date the T-M17.2 NOT NULL tightening, even though
 *  the schema forbids that state today. */
export function BackToPatientLink({
  patientId,
}: {
  patientId: string | null;
}) {
  if (patientId === null) {
    return <BackLink href="/dashboard" label="Back to dashboard" />;
  }
  return <BackLink href={`/patients/${patientId}`} label="Back to patient" />;
}

/** Back link for /patients/[id]. Parent is the dashboard. */
export function BackToDashboardLink() {
  return <BackLink href="/dashboard" label="Back to dashboard" />;
}
