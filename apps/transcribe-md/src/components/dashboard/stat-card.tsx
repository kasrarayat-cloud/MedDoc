// HANDOFF §2.2 StatCard — eyebrow + big serif number + unit + optional
// colored delta line. Used by Dashboard (visits/month, avg time saved,
// pending review, signed this week) and later by Patient Detail.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark .qm-glass
// surface + qm-sectlabel + qm-serif treatment unchanged. Pages opt
// in to the Clinician chrome by passing `theme="clinician"`, which
// renders a warm `.qm-cl-card` paper-on-cream surface with the
// `.qm-cl-section-label` eyebrow and `.qm-cl-big-num` numeral.

import type { ReactNode } from 'react';

export type StatDeltaTone = 'mint' | 'amber' | 'coral' | 'accent-bright';
type StatCardTheme = 'legacy' | 'clinician';

interface StatCardProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaTone?: StatDeltaTone;
  theme?: StatCardTheme;
}

export function StatCard({
  label,
  value,
  unit,
  delta,
  deltaTone = 'mint',
  theme = 'legacy',
}: StatCardProps) {
  if (theme === 'clinician') {
    return (
      <ClinicianStatCard
        label={label}
        value={value}
        unit={unit}
        delta={delta}
        deltaTone={deltaTone}
      />
    );
  }
  return (
    <LegacyStatCard
      label={label}
      value={value}
      unit={unit}
      delta={delta}
      deltaTone={deltaTone}
    />
  );
}

function LegacyStatCard({
  label,
  value,
  unit,
  delta,
  deltaTone,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaTone: StatDeltaTone;
}) {
  return (
    <div className="qm-glass" style={{ padding: '18px 20px' }}>
      <div className="qm-sectlabel" style={{ marginBottom: 12 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <div
          className="qm-serif"
          style={{
            fontSize: 40,
            fontWeight: 400,
            letterSpacing: '-0.025em',
            lineHeight: 1,
          }}
        >
          {value}
        </div>
        {unit && (
          <div
            style={{
              color: 'var(--fg-3)',
              fontSize: 13,
              fontFamily: 'var(--mono)',
            }}
          >
            {unit}
          </div>
        )}
      </div>
      {delta && (
        <div
          style={{
            marginTop: 10,
            fontSize: 11.5,
            fontFamily: 'var(--mono)',
            color: `var(--${deltaTone})`,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          {delta}
        </div>
      )}
    </div>
  );
}

/** Map the legacy `StatDeltaTone` (mint/amber/coral/accent-bright) onto
 *  the Clinician palette tokens that exist inside .qm-cl-app:
 *    mint           → sage-deep (positive / on-track)
 *    accent-bright  → sage-deep (positive accent)
 *    amber          → amber-deep (caution)
 *    coral          → coral-deep (warning)
 *  Avoids any new globals.css additions; tokens are scoped under
 *  .qm-cl-app already (see globals.css ~L1395). */
function clinicianDeltaColor(tone: StatDeltaTone): string {
  switch (tone) {
    case 'amber':
      return 'var(--amber-deep)';
    case 'coral':
      return 'var(--coral-deep)';
    case 'mint':
    case 'accent-bright':
    default:
      return 'var(--sage-deep)';
  }
}

function ClinicianStatCard({
  label,
  value,
  unit,
  delta,
  deltaTone,
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaTone: StatDeltaTone;
}) {
  return (
    <div className="qm-cl-card" style={{ padding: '22px 24px' }}>
      <div
        className="qm-cl-section-label"
        style={{ marginBottom: 14 }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <div className="qm-cl-big-num">{value}</div>
        {unit && (
          <div
            style={{
              color: 'var(--ink-3)',
              fontSize: 12.5,
            }}
          >
            {unit}
          </div>
        )}
      </div>
      {delta && (
        <div
          style={{
            marginTop: 14,
            fontSize: 12.5,
            color: clinicianDeltaColor(deltaTone),
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          {delta}
        </div>
      )}
    </div>
  );
}
