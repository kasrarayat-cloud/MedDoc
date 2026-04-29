'use client';

// ============================================================================
// New-visit wrapper — HANDOFF §2.3 visuals (Gate 8).
// ----------------------------------------------------------------------------
// Renders the redesign's stepper chrome + Visit Summary rail around the
// existing PatientPicker / VisitFormStep2 content. Two-step internal
// state (patient absent vs present); "Change patient" resets to step 1.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark glass + violet
// gradient stepper byte-for-byte. `theme="clinician"` swaps the
// stepper to soft sage indicator dots, the visit summary rail to
// `.qm-cl-card`, and threads theme to PatientPicker + VisitFormStep2.
// ============================================================================

import { useState } from 'react';

import { cn } from '@/lib/cn';
import { Ic } from '@/components/ui/icon';
import { Avatar } from '@/components/ui/avatar';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { PatientPicker } from './patient-picker';
import { VisitFormStep2 } from './visit-form-step2';
import type { SelectedPatient } from './patient-types';
import type { SPECIALTIES } from '@/lib/specialties';

type Specialty = (typeof SPECIALTIES)[number];
type NewVisitClientTheme = 'legacy' | 'clinician';

interface Props {
  initialPatient: SelectedPatient | null;
  specialties: Specialty[];
  defaultSpecialty: string;
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: NewVisitClientTheme;
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
  theme = 'legacy',
}: Props) {
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(
    initialPatient
  );

  // The underlying form collapses "visit details" + "capture mode" into
  // one screen, but the stepper shows the handoff's three-phase model.
  // Active step = 0 while picking, 1 once a patient is in hand (the
  // visit-details + capture UI is a single scrolled panel).
  const activeStep = selectedPatient ? 1 : 0;
  const isClinician = theme === 'clinician';

  return (
    <>
      <Stepper active={activeStep} theme={theme} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gap: 28,
          alignItems: 'flex-start',
        }}
      >
        <div
          className={isClinician ? 'qm-cl-card' : 'qm-glass'}
          style={{ padding: 28 }}
        >
          {selectedPatient === null ? (
            <PatientPicker onSelect={setSelectedPatient} theme={theme} />
          ) : (
            <VisitFormStep2
              patient={selectedPatient}
              onChangePatient={() => setSelectedPatient(null)}
              specialties={specialties}
              defaultSpecialty={defaultSpecialty}
              theme={theme}
            />
          )}
        </div>

        <VisitSummary
          patient={selectedPatient}
          specialty={defaultSpecialty}
          theme={theme}
        />
      </div>
    </>
  );
}

function Stepper({
  active,
  theme,
}: {
  active: number;
  theme: NewVisitClientTheme;
}) {
  const isClinician = theme === 'clinician';

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
              style={
                isClinician
                  ? {
                      width: 26,
                      height: 26,
                      borderRadius: 999,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: isDone
                        ? 'var(--sage)'
                        : isActive
                          ? 'var(--sage-tint-strong)'
                          : 'var(--cream-2)',
                      border: `1px solid ${
                        isActive || isDone
                          ? 'var(--sage)'
                          : 'var(--line)'
                      }`,
                      color: isDone
                        ? '#FFFCF5'
                        : isActive
                          ? 'var(--sage-deep)'
                          : 'var(--ink-3)',
                      fontFamily: 'var(--sans)',
                      fontSize: 12,
                      fontWeight: 500,
                    }
                  : {
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
                    }
              }
            >
              {isDone ? <Ic.check width={13} height={13} /> : i + 1}
            </span>
            <span
              style={
                isClinician
                  ? {
                      fontSize: 13,
                      color: isActive ? 'var(--ink)' : 'var(--ink-3)',
                      fontFamily: 'var(--sans)',
                    }
                  : {
                      fontSize: 13,
                      color: isActive ? 'var(--fg)' : 'var(--fg-3)',
                    }
              }
            >
              {label}
            </span>
            {i < STEP_LABELS.length - 1 && (
              <span
                style={
                  isClinician
                    ? {
                        width: 40,
                        height: 1,
                        background: isDone ? 'var(--sage)' : 'var(--line)',
                      }
                    : {
                        width: 40,
                        height: 1,
                        background: isDone
                          ? 'var(--accent-bright)'
                          : 'var(--line)',
                      }
                }
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
  theme,
}: {
  patient: SelectedPatient | null;
  specialty: string;
  theme: NewVisitClientTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <aside
      className={isClinician ? 'qm-cl-card' : 'qm-glass'}
      style={{
        padding: 20,
        alignSelf: 'flex-start',
        position: 'sticky',
        top: 12,
      }}
    >
      <div
        className={isClinician ? 'qm-cl-section-label' : 'qm-sectlabel'}
        style={{ marginBottom: 12 }}
      >
        Visit summary
      </div>
      <div style={{ display: 'grid', gap: 14 }}>
        <SummaryRow label="Patient" theme={theme}>
          {patient ? (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <Avatar name={patient.name} size={32} theme={theme} />
              <span
                className={isClinician ? 'qm-cl-serif' : 'qm-serif'}
                style={
                  isClinician
                    ? { fontSize: 16, color: 'var(--ink)' }
                    : { fontSize: 15 }
                }
              >
                {patient.name}
              </span>
            </span>
          ) : (
            <span
              style={{
                color: isClinician ? 'var(--ink-3)' : 'var(--fg-4)',
                fontSize: 13,
                fontStyle: isClinician ? 'italic' : undefined,
                fontFamily: isClinician ? 'var(--serif)' : undefined,
              }}
            >
              Not picked yet
            </span>
          )}
        </SummaryRow>
        <SummaryRow label="Specialty" theme={theme}>
          {isClinician ? (
            // Per visit-detail mockup: specialty rendered as a small
            // soft pill rather than a chip. Use the existing SpecChip
            // for legacy parity, but wrap with sage tint if Clinician.
            <span
              className="qm-cl-pill qm-cl-pill-soft"
              style={{ fontSize: 11.5, padding: '4px 10px' }}
            >
              {specialty}
            </span>
          ) : (
            <SpecChip kind={toSpecKind(specialty)} size="sm" />
          )}
        </SummaryRow>
        <SummaryRow label="Capture mode" theme={theme}>
          <span
            style={{
              fontSize: 13.5,
              color: isClinician ? 'var(--ink-2)' : 'var(--fg-2)',
              fontStyle: isClinician ? 'italic' : undefined,
              fontFamily: isClinician ? 'var(--serif)' : undefined,
            }}
          >
            Chosen on step 2
          </span>
        </SummaryRow>
        <SummaryRow label="Estimated" theme={theme}>
          <span
            style={{
              fontSize: 13.5,
              color: isClinician ? 'var(--ink-2)' : 'var(--fg-2)',
              fontFamily: isClinician ? 'var(--serif)' : undefined,
              lineHeight: isClinician ? 1.55 : undefined,
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
  theme,
}: {
  label: string;
  children: React.ReactNode;
  theme: NewVisitClientTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <div>
      <div
        className={cn(isClinician && 'qm-cl-section-label')}
        style={
          isClinician
            ? { marginBottom: 6 }
            : {
                fontSize: 11.5,
                color: 'var(--fg-4)',
                fontFamily: 'var(--mono)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                marginBottom: 6,
              }
        }
      >
        {label}
      </div>
      {children}
    </div>
  );
}
