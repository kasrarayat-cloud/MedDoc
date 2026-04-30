'use client';

// ============================================================================
// Back-link variants for visit + patient detail pages
// ----------------------------------------------------------------------------
// Two shapes, one file, shared chrome. Used by /visits/[id] and
// /patients/[id] — the former's natural parent is the patient
// (T-M17.3 UX call; doctors mostly open a visit from a patient's
// timeline), the latter's natural parent is the dashboard.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark violet-ring focus +
// `text-text-tertiary` rendering verbatim. Migrated routes (visit
// detail) pass `theme="clinician"`, swapping to a quiet `.qm-cl-btn-
// ghost`-style inline link with sage-deep hover ink and a sage focus
// ring. Both branches share the same `useRouter` push semantics so
// Cmd/Ctrl/Shift-click and right-click still bypass to native nav.
// ============================================================================

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

type BackLinkTheme = 'legacy' | 'clinician';

const LEGACY_LINK_CLASSES =
  'relative z-10 inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base';

// Clinician variant: inline link styled like a `.qm-cl-btn-ghost`
// chip. Cream-2 hover lift, ink-2 → ink on hover, sage focus ring.
// Padding/radius mirrors the small-button rhythm of the visit-detail
// mockup's breadcrumb back-link affordance.
const CLINICIAN_LINK_CLASSES =
  'relative z-10 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-clinician-ink-2 transition-colors hover:bg-clinician-cream-2 hover:text-clinician-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream';

function BackLink({
  href,
  label,
  theme = 'legacy',
}: {
  href: string;
  label: string;
  theme?: BackLinkTheme;
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
      className={
        theme === 'clinician' ? CLINICIAN_LINK_CLASSES : LEGACY_LINK_CLASSES
      }
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
  theme = 'legacy',
}: {
  patientId: string | null;
  theme?: BackLinkTheme;
}) {
  if (patientId === null) {
    return (
      <BackLink href="/dashboard" label="Back to dashboard" theme={theme} />
    );
  }
  return (
    <BackLink
      href={`/patients/${patientId}`}
      label="Back to patient"
      theme={theme}
    />
  );
}

/** Back link for /patients/[id]. Parent is the dashboard. */
export function BackToDashboardLink({
  theme = 'legacy',
}: {
  theme?: BackLinkTheme;
} = {}) {
  return <BackLink href="/dashboard" label="Back to dashboard" theme={theme} />;
}
