'use client';

// ============================================================================
// New-visit wrapper — HANDOFF §2.3 visuals (Gate 8).
// ----------------------------------------------------------------------------
// Renders the redesign's stepper chrome + Visit Summary rail around the
// existing PatientPicker / VisitFormStep2 content. Two-step internal
// state (patient absent vs present); "Change patient" resets to step 1.
// ============================================================================

import { useState } from 'react';

import { Ic } from '@/components/ui/icon';
import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { PatientPicker } from './patient-picker';
import { VisitFormStep2 } from './visit-form-step2';
import type { SelectedPatient } from './patient-types';
import type { SPECIALTIES } from '@/lib/specialties';

type Specialty = (typeof SPECIALTIES)[number];

interface Props {
  initialPatient: SelectedPatient | null;
  specialties: Specialty[];
  defaultSpecialty: string;
}

const STEP_LABELS = ['Patient', 'Visit details', 'Capture'] as const;

const KNOWN: readonly SpecialtyKind[] = [
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
];
function toSpecKind(raw: string): SpecialtyKind {
  const lower = raw.toLowerCase() as SpecialtyKind;
  return KNOWN.includes(lower) ? lower : 'primary';
}

export function NewVisitClient({
  initialPatient,
  specialties,
  defaultSpecialty,
}: Props) {
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(
    initialPatient
  );

  // The underlying form collapses "visit details" + "capture mode" into
  // one screen, but the stepper shows the handoff's three-phase model.
  // Active step = 0 while picking, 1 once a patient is in hand (the
  // visit-details + capture UI is a single scrolled panel).
  const activeStep = selectedPatient ? 1 : 0;

  return (
    <>
      <Stepper active={activeStep} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gap: 28,
          alignItems: 'flex-start',
        }}
      >
        <div className="qm-glass" style={{ padding: 28 }}>
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

        <VisitSummary
          patient={selectedPatient}
          specialty={defaultSpecialty}
        />
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
        padding: '4px 0 22px',
      }}
    >
      {STEP_LABELS.map((label, i) => {
        const isActive = i === active;
        const isDone = i < active;
        return (
          <span
            key={label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
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
                  ? 'linear-gradient(135deg, #A87CFF, #6B3FD9)'
                  : isActive
                    ? 'rgba(139,92,255,0.15)'
                    : 'rgba(255,255,255,0.03)',
                border: `1px solid ${
                  isActive || isDone
                    ? 'rgba(139,92,255,0.4)'
                    : 'var(--line)'
                }`,
                color: isDone
                  ? '#fff'
                  : isActive
                    ? 'var(--accent-bright)'
                    : 'var(--fg-3)',
                fontFamily: 'var(--mono)',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {isDone ? <Ic.check width={13} height={13} /> : i + 1}
            </span>
            <span
              style={{
                fontSize: 13,
                color: isActive ? 'var(--fg)' : 'var(--fg-3)',
              }}
            >
              {label}
            </span>
            {i < STEP_LABELS.length - 1 && (
              <span
                style={{
                  width: 40,
                  height: 1,
                  background: isDone ? 'var(--accent-bright)' : 'var(--line)',
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
      className="qm-glass"
      style={{
        padding: 20,
        alignSelf: 'flex-start',
        position: 'sticky',
        top: 12,
      }}
    >
      <div className="qm-sectlabel" style={{ marginBottom: 12 }}>
        Visit summary
      </div>
      <div style={{ display: 'grid', gap: 14 }}>
        <SummaryRow label="Patient">
          {patient ? (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <Avatar name={patient.name} size={32} />
              <span className="qm-serif" style={{ fontSize: 15 }}>
                {patient.name}
              </span>
            </span>
          ) : (
            <span style={{ color: 'var(--fg-4)', fontSize: 13 }}>
              Not picked yet
            </span>
          )}
        </SummaryRow>
        <SummaryRow label="Specialty">
          <SpecChip kind={toSpecKind(specialty)} size="sm" />
        </SummaryRow>
        <SummaryRow label="Capture mode">
          <span style={{ fontSize: 13.5, color: 'var(--fg-2)' }}>
            Chosen on step 2
          </span>
        </SummaryRow>
        <SummaryRow label="Estimated">
          <span style={{ fontSize: 13.5, color: 'var(--fg-2)' }}>
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
      <div
        style={{
          fontSize: 11.5,
          color: 'var(--fg-4)',
          fontFamily: 'var(--mono)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}
