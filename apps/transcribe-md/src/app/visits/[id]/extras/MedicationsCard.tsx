'use client';

// ============================================================================
// MedicationsCard — chronic / outpatient medications.
// ----------------------------------------------------------------------------
// Distinct from the Rx tab (which is the today's-Rx draft). This card
// is the "what does the patient take chronically" surface; today's
// freshly-drafted prescriptions live in the Rx tab.
// ============================================================================

import { ExtrasCard } from './ExtrasCard';

export interface ChronicMedication {
  name: string;
  /** "10 mg PO daily" — single-line dose / route / frequency. */
  schedule?: string | null;
  /** Free-text indication (e.g. "for hypertension (I10)"). */
  indication?: string | null;
  /** "Active" / "Held" / etc. */
  status?: string | null;
  /** "Started Jan 2024 · adherence excellent". */
  history?: string | null;
}

interface Props {
  medications: ChronicMedication[];
  readonly: boolean;
  /** Optional foot byline ("Reviewed today by Dr. Sarah Chen"). */
  reviewedBy?: string | null;
}

export function MedicationsCard({
  medications,
  readonly,
  reviewedBy,
}: Props) {
  const total = medications.length;

  return (
    <ExtrasCard
      icon="💊"
      title="Current medications"
      sub="Chronic only · today's Rx is in the Rx tab"
      count={total === 0 ? null : `${total} chronic`}
      countTone="default"
      hideEdit={readonly}
      foot={
        readonly ? null : (
          <>
            <span className="opacity-60">+ Add medication (coming soon)</span>
            {reviewedBy && <span>Reviewed by {reviewedBy}</span>}
          </>
        )
      }
    >
      {total === 0 ? (
        <div className="qm-lin-extras-empty">
          No chronic medications recorded.
        </div>
      ) : (
        <div>
          {medications.map((m, i) => (
            <div key={`${m.name}-${i}`} className="qm-lin-extras-med-row">
              <span className="qm-lin-extras-med-icon">Rx</span>
              <div className="min-w-0 flex-1">
                <div className="qm-lin-extras-med-name">
                  {m.name}
                  {m.status && (
                    <span className="qm-lin-extras-med-pill">{m.status}</span>
                  )}
                </div>
                <div className="qm-lin-extras-med-detail">
                  {[m.schedule, m.indication, m.history]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </ExtrasCard>
  );
}
