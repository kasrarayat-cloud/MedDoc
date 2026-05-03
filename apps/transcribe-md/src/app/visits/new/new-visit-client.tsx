'use client';

// ============================================================================
// New-visit wrapper — Phase 5 Linear V1.
// ----------------------------------------------------------------------------
// Renders the stepper chrome + Visit Summary rail around the existing
// PatientPicker / VisitFormStep2 content. Two-step internal state
// (patient absent vs present); "Change patient" resets to step 1. The
// `theme` prop is preserved as a no-op.
// ============================================================================

import { useState } from 'react';

import { Ic } from '@/components/ui/icon';
import { Avatar } from '@/components/ui/avatar';
import { PatientPicker } from './patient-picker';
import { VisitFormStep2 } from './visit-form-step2';
import type { SelectedPatient } from './patient-types';
import { findSpecialty, type Specialty } from '@meddoc/shared/specialties';
type NewVisitClientTheme = 'legacy' | 'clinician';

interface Props {
  initialPatient: SelectedPatient | null;
  specialties: readonly Specialty[];
  defaultSpecialty: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: NewVisitClientTheme;
}

const STEP_LABELS = ['Patient', 'Visit details', 'Capture'] as const;

const SECTION_LABEL: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10.5,
  fontWeight: 500,
  letterSpacing: '0.07em',
  textTransform: 'uppercase',
  color: 'var(--color-linear-text-3)',
};

export function NewVisitClient({
  initialPatient,
  specialties,
  defaultSpecialty,
}: Props) {
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(
    initialPatient
  );

  // The underlying form collapses "visit details" + "capture mode" into
  // one screen, but the stepper shows the three-phase model. Active
  // step = 0 while picking, 1 once a patient is in hand.
  const activeStep = selectedPatient ? 1 : 0;

  return (
    <>
      <Stepper active={activeStep} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gap: 24,
          alignItems: 'flex-start',
        }}
      >
        <div
          style={{
            background: 'var(--color-linear-surface-1)',
            border: '1px solid var(--color-linear-border)',
            borderRadius: 10,
            padding: 24,
          }}
        >
          {selectedPatient === null ? (
            <PatientPicker onSelect={setSelectedPatient} />
          ) : (
            <VisitFormStep2
              patient={selectedPatient}
              onChangePatient={() => setSelectedPatient(null)}
              specialties={specialties}
              defaultSpecialty={defaultSpecialty}
            />
          )}
        </div>

        <VisitSummary patient={selectedPatient} specialty={defaultSpecialty} />
      </div>
    </>
  );
}

function Stepper({ active }: { active: number }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: '0 0 22px',
      }}
    >
      {STEP_LABELS.map((label, i) => {
        const isActive = i === active;
        const isDone = i < active;
        return (
          <span
            key={label}
            style={{ display: 'flex', alignItems: 'center', gap: 10 }}
          >
            <span
              style={{
                width: 26,
                height: 26,
                borderRadius: 999,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: isDone
                  ? 'var(--color-linear-sage)'
                  : isActive
                    ? 'var(--color-linear-sage-tint)'
                    : 'var(--color-linear-surface-2)',
                border: `1px solid ${
                  isActive || isDone
                    ? 'rgba(122,166,140,0.45)'
                    : 'var(--color-linear-border)'
                }`,
                color: isDone
                  ? '#0d1611'
                  : isActive
                    ? 'var(--color-linear-sage-bright)'
                    : 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {isDone ? <Ic.check width={13} height={13} /> : i + 1}
            </span>
            <span
              style={{
                fontSize: 13,
                color: isActive
                  ? 'var(--color-linear-text)'
                  : 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {label}
            </span>
            {i < STEP_LABELS.length - 1 && (
              <span
                style={{
                  width: 40,
                  height: 1,
                  background: isDone
                    ? 'var(--color-linear-sage)'
                    : 'var(--color-linear-border)',
                }}
              />
            )}
          </span>
        );
      })}
    </div>
  );
}

function VisitSummary({
  patient,
  specialty,
}: {
  patient: SelectedPatient | null;
  specialty: string;
}) {
  return (
    <aside
      style={{
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 10,
        padding: 20,
        alignSelf: 'flex-start',
        position: 'sticky',
        top: 12,
      }}
    >
      <div style={{ ...SECTION_LABEL, marginBottom: 12 }}>Visit summary</div>
      <div style={{ display: 'grid', gap: 14 }}>
        <SummaryRow label="Patient">
          {patient ? (
            <span
              style={{ display: 'flex', alignItems: 'center', gap: 10 }}
            >
              <Avatar name={patient.name} size={32} />
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--color-linear-text)',
                }}
              >
                {patient.name}
              </span>
            </span>
          ) : (
            <span
              style={{
                color: 'var(--color-linear-text-3)',
                fontSize: 13,
              }}
            >
              Not picked yet
            </span>
          )}
        </SummaryRow>
        <SummaryRow label="Specialty">
          <span className="qm-lin-pill">{findSpecialty(specialty).label}</span>
        </SummaryRow>
        <SummaryRow label="Capture mode">
          <span style={{ fontSize: 13.5, color: 'var(--color-linear-text-2)' }}>
            Chosen on step 2
          </span>
        </SummaryRow>
        <SummaryRow label="Estimated">
          <span
            style={{
              fontSize: 13.5,
              color: 'var(--color-linear-text-2)',
              lineHeight: 1.55,
            }}
          >
            ~30 sec processing · draft ready immediately after
          </span>
        </SummaryRow>
      </div>
    </aside>
  );
}

function SummaryRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div style={{ ...SECTION_LABEL, marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}
