'use client';

// ============================================================================
// /visits/new client wrapper (T-M17.2 Phase 3 Commit 9)
// ----------------------------------------------------------------------------
// Holds the "selected patient" state for the two-step flow:
//   selectedPatient === null  → PatientPicker (Step 1)
//   selectedPatient !== null  → VisitFormStep2 (Step 2)
//
// `initialPatient` is set when the server validated a ?patientId=
// query param. The user can still hit "Change patient" on the pill
// to go back to Step 1 — resetting the state unlocks the picker.
// ============================================================================

import { useState } from 'react';

import { PatientPicker } from './patient-picker';
import { VisitFormStep2 } from './visit-form-step2';
import type { SelectedPatient } from './patient-types';
import type { SPECIALTIES } from '@/lib/specialties';
import type { TemplateOption } from '@/components/template-dropdown';

type Specialty = (typeof SPECIALTIES)[number];

interface Props {
  initialPatient: SelectedPatient | null;
  specialties: Specialty[];
  defaultSpecialty: string;
  templates: TemplateOption[];
}

export function NewVisitClient({
  initialPatient,
  specialties,
  defaultSpecialty,
  templates,
}: Props) {
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(
    initialPatient
  );

  if (selectedPatient === null) {
    return <PatientPicker onSelect={setSelectedPatient} />;
  }

  return (
    <VisitFormStep2
      patient={selectedPatient}
      onChangePatient={() => setSelectedPatient(null)}
      specialties={specialties}
      defaultSpecialty={defaultSpecialty}
      templates={templates}
    />
  );
}
