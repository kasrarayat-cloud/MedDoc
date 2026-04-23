// HANDOFF §2.2 StatCard — eyebrow + big serif number + unit + optional
// colored delta line. Used by Dashboard (visits/month, avg time saved,
// pending review, signed this week) and later by Patient Detail.

import type { ReactNode } from 'react';

export type StatDeltaTone = 'mint' | 'amber' | 'coral' | 'accent-bright';

export function StatCard({
  label,
  value,
  unit,
  delta,
  deltaTone = 'mint',
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaTone?: StatDeltaTone;
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
