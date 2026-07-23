'use client';

// ============================================================================
// NewVisitClientC3 — the calm "just start" create flow (flag-gated).
// ----------------------------------------------------------------------------
// Replaces the 3-step stepper ("Patient → Visit details → Capture") + the
// side Visit-Summary rail with one centered card and one obvious path: pick
// the patient, then a sensible-default capture mode, then Start. No misleading
// stepper for what is really a short form.
//
// SKIN-ONLY: reuses the SAME wired pieces verbatim — <PatientPicker> (search /
// select / quick-create) and <VisitFormStep2> (the real createVisitAction
// <form>, specialty + capture-mode + chief-complaint). No create logic, no
// action, no validation is touched; only the surrounding chrome is calmer.
// ============================================================================

import { useState } from 'react';

import { PatientPicker } from './patient-picker';
import { VisitFormStep2 } from './visit-form-step2';
import type { SelectedPatient } from './patient-types';
import type { Specialty } from '@meddoc/shared/specialties';

interface Props {
  initialPatient: SelectedPatient | null;
  specialties: readonly Specialty[];
  defaultSpecialty: string;
  templates?: ReadonlyArray<{ id: string; name: string; isActive: boolean }>;
}

export function NewVisitClientC3({
  initialPatient,
  specialties,
  defaultSpecialty,
  templates,
}: Props) {
  const [patient, setPatient] = useState<SelectedPatient | null>(initialPatient);

  return (
    <div className="qm-c3-nv">
      <div className="qm-c3-nv-card">
        {patient === null ? (
          <>
            <span className="qm-c3-nv-kicker">New visit</span>
            <h1 className="qm-c3-nv-h">Start a visit</h1>
            <p className="qm-c3-nv-p">
              Pick the patient — then you&apos;re one tap from recording. We
              capture the visit and write the note after you stop.
            </p>
            <div className="qm-c3-nv-picker">
              <PatientPicker onSelect={setPatient} />
            </div>
          </>
        ) : (
          <VisitFormStep2
            patient={patient}
            onChangePatient={() => setPatient(null)}
            specialties={specialties}
            defaultSpecialty={defaultSpecialty}
            templates={templates}
          />
        )}
      </div>
    </div>
  );
}
