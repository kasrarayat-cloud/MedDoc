'use client';

// ============================================================================
// Back-link variants for visit + patient detail pages
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. A single `.qm-lin-btn`-shaped pill
// link with a back arrow. Cmd/Ctrl/Shift-click and right-click still
// bypass to native nav.
// ============================================================================

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

type BackLinkTheme = 'legacy' | 'clinician';

const LINK_CLASSES =
  'relative z-10 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium text-linear-text-2 border border-linear-border transition-colors hover:border-linear-border-strong hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg';

function BackLink({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: BackLinkTheme;
}) {
  if (patientId === null) {
    return <BackLink href="/dashboard" label="Back to dashboard" />;
  }
  return (
    <BackLink href={`/patients/${patientId}`} label="Back to patient" />
  );
}

/** Back link for /patients/[id]. Parent is the dashboard. */
export function BackToDashboardLink(
  _props: {
    /** @deprecated kept for back-compat; Linear V1 is single-theme. */
    theme?: BackLinkTheme;
  } = {}
) {
  return <BackLink href="/dashboard" label="Back to dashboard" />;
}
