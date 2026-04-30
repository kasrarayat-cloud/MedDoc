// ============================================================================
// Phase 3 Wave 2 (dashboard density) — "Three drafts, ready when you are."
// ----------------------------------------------------------------------------
// The mockup (docs/design-directions-v3/clinician/dashboard.html
// L833–907) reserves a section under the patient list where exactly
// three of the doctor's most-recent READY-but-unsigned visits appear
// as preview cards. Each card carries:
//
//   ▎ avatar pill (specialty color)
//   ▎ patient name, Source Serif italic
//   ▎ specialty + drafted-time meta line
//   ▎ a one-line preview of the SOAP first line (~80 chars, italic)
//   ▎ a sage "Open" CTA + relative-time footer
//
// Empty state: "No drafts in flight." in italic on the same card grid
// background, matching the mockup voice.
//
// Server component — the page upstream already does the Prisma query
// and passes pre-shaped rows in. Doesn't read or write anywhere; all
// it does is project + render.
// ============================================================================

import Link from 'next/link';

import { Ic } from '@/components/ui/icon';
import { LocalTime } from '@/components/ui/local-time';
import {
  clinicianInitials,
  clinicianToneForSpecialty,
  type ClinicianAvatarTone,
} from '@/lib/clinician-specialty-color';

export type DraftReadyVisit = {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string | null;
  /** ISO 8601 UTC — displayed via <LocalTime variant="relative">. */
  draftedAt: string;
  /** Already clipped to ~80 chars on the server. UI does not re-clip,
   *  it just trusts the upstream. */
  previewLine: string | null;
  /** When true, the visit's `needsReview` flag is set — render the
   *  amber "Needs review" pill instead of the sage default. */
  needsReview: boolean;
};

interface DraftsReadyProps {
  drafts: DraftReadyVisit[];
}

export function DraftsReady({ drafts }: DraftsReadyProps) {
  return (
    <section style={{ padding: '32px 40px 8px' }}>
      <header style={{ marginBottom: 18 }}>
        <div className="qm-cl-eyebrow" style={{ marginBottom: 8 }}>
          Awaiting your eyes
        </div>
        <h2
          className="qm-cl-serif"
          style={{
            margin: 0,
            fontSize: 28,
            fontWeight: 400,
            letterSpacing: '-0.01em',
            lineHeight: 1.2,
            color: 'var(--ink)',
          }}
        >
          {headlineFor(drafts.length)}
        </h2>
      </header>

      {drafts.length === 0 ? (
        <EmptyDrafts />
      ) : (
        <div
          style={{
            display: 'grid',
            // Mockup: 3 equal columns at desktop; collapse to auto-fill
            // below ~960px to keep cards from squishing on tablets.
            gridTemplateColumns:
              'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 18,
          }}
        >
          {drafts.map((d) => (
            <DraftCard key={d.id} draft={d} />
          ))}
        </div>
      )}
    </section>
  );
}

function headlineFor(count: number): string {
  if (count === 0) return 'No drafts in flight.';
  if (count === 1) return 'One draft, ready when you are.';
  if (count === 2) return 'Two drafts, ready when you are.';
  return `${count === 3 ? 'Three' : count} drafts, ready when you are.`;
}

function EmptyDrafts() {
  return (
    <div
      className="qm-cl-card"
      style={{
        padding: '34px 28px',
        textAlign: 'center',
      }}
    >
      <p
        className="qm-cl-serif"
        style={{
          margin: 0,
          fontSize: 16,
          fontStyle: 'italic',
          color: 'var(--ink-3)',
          lineHeight: 1.55,
        }}
      >
        No drafts in flight.
      </p>
    </div>
  );
}

function DraftCard({ draft }: { draft: DraftReadyVisit }) {
  const displayName =
    draft.patientName ?? draft.patientFallback ?? 'Patient';
  const tone: ClinicianAvatarTone = clinicianToneForSpecialty(
    draft.specialty,
    displayName
  );
  const initials = clinicianInitials(displayName);
  const pillTone = draft.needsReview ? 'amber' : 'sage';
  const pillLabel = draft.needsReview ? 'Needs review' : 'Drafted';

  return (
    <Link
      href={`/visits/${draft.id}`}
      className="qm-cl-card-soft"
      style={{
        padding: '20px 22px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        textDecoration: 'none',
        color: 'inherit',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          aria-hidden
          className={`qm-cl-avatar qm-cl-avatar-${tone}`}
          style={{ width: 36, height: 36, fontSize: 13 }}
        >
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            className="qm-cl-serif"
            style={{
              fontSize: 16,
              fontStyle: 'italic',
              letterSpacing: '-0.005em',
              lineHeight: 1.2,
              color: 'var(--ink)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {displayName}
          </div>
          <div
            style={{
              color: 'var(--ink-3)',
              fontSize: 11.5,
              marginTop: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {draft.specialty ? `${draft.specialty} · ` : ''}
            <span>
              <LocalTime iso={draft.draftedAt} variant="relative" />
            </span>
          </div>
        </div>
        <span
          className={`qm-cl-pill qm-cl-pill-${pillTone}`}
          style={{ fontSize: 10.5, padding: '2px 8px' }}
        >
          <span className="qm-cl-pill-dot" />
          {pillLabel}
        </span>
      </div>

      {/* SOAP preview line — italic serif, two-line clamp so a long
          subjective opener doesn't break the card height. */}
      <p
        className="qm-cl-serif"
        style={{
          margin: 0,
          fontSize: 14.5,
          fontStyle: 'italic',
          color: 'var(--ink-2)',
          lineHeight: 1.6,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          minHeight: '2.6em', // reserve two lines so card heights stay even
        }}
      >
        {draft.previewLine ? (
          <>&ldquo;{draft.previewLine}&rdquo;</>
        ) : (
          <span style={{ color: 'var(--ink-3)' }}>
            Draft is empty — open to dictate.
          </span>
        )}
      </p>

      {/* Footer row: relative drafted-time on the left, sage "Open" CTA
          on the right. Matches mockup L856 (Drafted N min ago · readtime). */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 12,
          color: 'var(--ink-3)',
        }}
      >
        <span>
          Drafted <LocalTime iso={draft.draftedAt} variant="relative" />
        </span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color: 'var(--sage-deep)',
            fontWeight: 500,
          }}
        >
          Open
          <Ic.chevRight width={12} height={12} />
        </span>
      </div>
    </Link>
  );
}
