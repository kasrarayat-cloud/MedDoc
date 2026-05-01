'use client';

// ============================================================================
// AllergiesCard — list of substance allergies with severity tints.
// ----------------------------------------------------------------------------
// Severity:
//   severe   → coral / danger
//   moderate → amber / warning
//   mild     → sky / info
// ============================================================================

import { ExtrasCard } from './ExtrasCard';

export type AllergySeverity = 'severe' | 'moderate' | 'mild';

export interface Allergy {
  substance: string;
  severity: AllergySeverity;
  reaction?: string | null;
  verifiedAt?: string | null;
  source?: string | null;
}

interface Props {
  allergies: Allergy[];
  readonly: boolean;
}

const SEV_LABEL: Record<AllergySeverity, string> = {
  severe: 'Severe',
  moderate: 'Moderate',
  mild: 'Mild',
};

const SEV_CLS: Record<AllergySeverity, string> = {
  severe: 'qm-lin-extras-allergy',
  moderate: 'qm-lin-extras-allergy qm-lin-extras-allergy--moderate',
  mild: 'qm-lin-extras-allergy qm-lin-extras-allergy--mild',
};

export function AllergiesCard({ allergies, readonly }: Props) {
  const total = allergies.length;
  const severeCount = allergies.filter((a) => a.severity === 'severe').length;

  let count: string | null = null;
  let countTone: 'sage' | 'warn' | 'danger' | 'default' = 'default';
  if (total === 0) {
    count = 'None known';
    countTone = 'sage';
  } else if (severeCount > 0) {
    count = `${severeCount} severe`;
    countTone = 'danger';
  } else {
    count = `${total} active`;
    countTone = 'warn';
  }

  return (
    <ExtrasCard
      icon="⚠"
      title="Allergies"
      sub={
        total === 0
          ? 'No known allergies'
          : `${total} active · confirmed at intake`
      }
      count={count}
      countTone={countTone}
      hideEdit={readonly}
    >
      {total === 0 ? (
        <div className="qm-lin-extras-empty">No known allergies.</div>
      ) : (
        <div>
          {allergies.map((a, i) => (
            <div key={`${a.substance}-${i}`} className={SEV_CLS[a.severity]}>
              <span className="qm-lin-extras-allergy-sev">
                {SEV_LABEL[a.severity]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="qm-lin-extras-allergy-name">{a.substance}</div>
                {a.reaction && (
                  <div className="qm-lin-extras-allergy-detail">
                    Reaction: {a.reaction}
                  </div>
                )}
                {(a.verifiedAt || a.source) && (
                  <div className="qm-lin-extras-allergy-meta">
                    {[
                      a.verifiedAt ? `VERIFIED ${a.verifiedAt}` : null,
                      a.source ? a.source.toUpperCase() : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </ExtrasCard>
  );
}
