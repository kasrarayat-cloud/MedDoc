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
    /* ⚠️ R3.7 — HOSTED, AND THE POSTED CONTRACT IS UNTOUCHED BY CONSTRUCTION.
       The census counted 10 `qm-c3-nv-*` islands on this route. `.qm-rounds-host`
       retints all of them plus the `qm-lin-btn` controls at once.

       THE REASON IT IS A WRAPPER AND NOT A REWRITE is the brief's own
       constraint: "Function and posted field names unchanged — the specialty
       hidden-input contract from the smoke walks stays." Both prod smoke walks
       assert `input[name="specialty"]` carries the SLUG (`primary-care`, not the
       "Primary Care" label), and the whole flow posts through a server action
       keyed on those names. A wrapper cannot rename a field; a rewrite of the
       form markup is precisely the change that could, silently.

       What is NOT hosted, because hosting cannot fix it: the capture tiles'
       hover and focus, which hard-code the legacy sage as a literal rgba. Those
       are `.qm-rounds-modetile`. */
    <div className="qm-rounds-host qm-c3-nv">
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
