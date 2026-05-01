// ============================================================================
// Phase 5 — Linear V1 Faithful drafts-ready list.
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html section header pattern + row list.
//
// Up to three READY-but-unsigned visits surfaced under the patient list
// as preview rows. Each row carries:
//
//   ▎ patient name + relative drafted time
//   ▎ specialty pill
//   ▎ italic-free SOAP first-line preview
//   ▎ status pill (sage Drafted / amber Needs review)
//
// The Phase 4 cream-card grid + Source Serif italic patient names are
// gone; this is a flat row list on the dark canvas.
// ============================================================================

import Link from 'next/link';

import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';

export type DraftReadyVisit = {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string | null;
  /** ISO 8601 UTC. */
  draftedAt: string;
  /** Server-clipped to ~80 chars. */
  previewLine: string | null;
  /** Sage "Drafted" vs amber "Needs review" pill driver. */
  needsReview: boolean;
};

interface DraftsReadyProps {
  drafts: DraftReadyVisit[];
}

export function DraftsReady({ drafts }: DraftsReadyProps) {
  return (
    <section style={{ padding: '4px 24px 32px' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          margin: '20px 0 6px',
          paddingBottom: 6,
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12.5,
            color: 'var(--color-linear-text)',
            fontWeight: 500,
            letterSpacing: '-0.005em',
          }}
        >
          Drafts ready to sign
        </div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--color-linear-text-3)',
          }}
        >
          {drafts.length} draft{drafts.length === 1 ? '' : 's'}
        </div>
      </header>

      {drafts.length === 0 ? (
        <EmptyDrafts />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {drafts.map((d) => (
            <DraftRow key={d.id} draft={d} />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyDrafts() {
  return (
    <div
      style={{
        padding: '22px 16px',
        fontFamily: 'var(--font-sans)',
        fontSize: 12.5,
        color: 'var(--color-linear-text-3)',
      }}
    >
      No drafts in flight.
    </div>
  );
}

function DraftRow({ draft }: { draft: DraftReadyVisit }) {
  const displayName =
    draft.patientName ?? draft.patientFallback ?? 'Patient';
  const pillCls = draft.needsReview
    ? 'qm-lin-pill qm-lin-pill--review'
    : 'qm-lin-pill qm-lin-pill--ready';
  const pillLabel = draft.needsReview ? 'Needs review' : 'Drafted';

  return (
    <Link
      href={`/visits/${draft.id}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 110px 1fr 140px 24px',
        alignItems: 'center',
        gap: 12,
        padding: '0 6px',
        height: 36,
        borderBottom: '1px solid var(--color-linear-hairline)',
        color: 'inherit',
        textDecoration: 'none',
        fontSize: 13,
        transition: 'background-color 100ms ease',
      }}
      className="qm-lin-row"
    >
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 13,
          fontWeight: 600,
          letterSpacing: '-0.005em',
          color: 'var(--color-linear-text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {displayName}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 12,
          color: 'var(--color-linear-text-2)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {draft.specialty ?? '—'}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 12.5,
          color: 'var(--color-linear-text-2)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {draft.previewLine ?? (
          <span style={{ color: 'var(--color-linear-text-3)' }}>
            Draft is empty — open to dictate.
          </span>
        )}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 8,
        }}
      >
        <span className={pillCls}>{pillLabel}</span>
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          color: 'var(--color-linear-text-3)',
        }}
      >
        <Ic.chevRight width={12} height={12} />
      </div>
      {/* Hidden: drafted time available via tooltip-on-hover; not in main grid */}
      <div className="sr-only">
        Drafted <LocalTime iso={draft.draftedAt} variant="relative" />
      </div>
    </Link>
  );
}
