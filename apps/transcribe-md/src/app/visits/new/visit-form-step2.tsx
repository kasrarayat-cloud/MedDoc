'use client';

// ============================================================================
// Step 2 of /visits/new — specialty / CC / capture-mode (T-M17.2 Commit 9)
// ----------------------------------------------------------------------------
// Renders the new-visit form fields (SpecialtyDropdown, CC input, the
// three ModeTileWithForm submit buttons) with a patient pill pinned
// to the top. Submits to createVisitAction via the hidden patientId
// field — patientName is NOT submitted, the server action derives the
// canonical name from the FK.
//
// Phase 5 — Linear V1 Faithful. The patient pill renders on a
// hairline-bordered surface-2 backdrop; form labels switch to mono
// uppercase. The `theme` prop is preserved as a no-op.
// ============================================================================

import Link from 'next/link';
import { ArrowLeftRight } from 'lucide-react';

import { SpecialtyDropdown } from '@/components/specialty-dropdown';
import { createVisitAction } from '@/actions/visits';
import { ModeTileWithForm } from './mode-tile-with-form';
import type { SPECIALTIES } from '@/lib/specialties';
import type { SelectedPatient } from './patient-types';

type Specialty = (typeof SPECIALTIES)[number];
type VisitFormStep2Theme = 'legacy' | 'clinician';

interface Props {
  patient: SelectedPatient;
  /** Undefined when the caller opened /visits/new?patientId=… — we
   *  still want the "Change patient" link to work (redirect to the
   *  unlocked flow). Defined when the caller picked via Step 1 — the
   *  link becomes a purely client-side "go back". */
  onChangePatient?: () => void;
  specialties: Specialty[];
  defaultSpecialty: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitFormStep2Theme;
}

const FIELD_LABEL =
  'mb-1.5 block font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3';

const INPUT_CLS =
  'block w-full rounded-md border border-linear-border bg-linear-surface-2 px-3 py-2.5 text-[14px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30';

function formatDob(iso: string | null): string {
  return iso ? `b. ${iso.slice(0, 10)}` : 'No DOB on file';
}

export function VisitFormStep2({
  patient,
  onChangePatient,
  specialties,
  defaultSpecialty,
}: Props) {
  return (
    <>
      <PatientPill patient={patient} onChangePatient={onChangePatient} />

      <form
        id="new-visit-form"
        action={createVisitAction}
        className="grid grid-cols-1 gap-6 sm:grid-cols-2"
      >
        <input type="hidden" name="patientId" value={patient.id} />

        <div>
          <label className={FIELD_LABEL}>Specialty</label>
          <SpecialtyDropdown
            options={specialties}
            name="specialty"
            defaultValue={defaultSpecialty}
          />
        </div>

        <div>
          <label className={FIELD_LABEL}>
            Chief complaint{' '}
            <span
              style={{
                color: 'var(--color-linear-text-3)',
                fontWeight: 400,
                textTransform: 'none',
                letterSpacing: '-0.005em',
              }}
            >
              (optional)
            </span>
          </label>
          <input
            name="chiefComplaint"
            type="text"
            className={INPUT_CLS}
            placeholder="e.g. Headache for 3 days"
          />
        </div>
      </form>

      <div className="mt-10">
        <div className="mb-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3">
          Pick a capture mode
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ModeTileWithForm
            formId="new-visit-form"
            icon="mic"
            title="Upload audio"
            description="Record your visit on your phone, then drop the file here."
            value="audio_upload"
          />
          <ModeTileWithForm
            formId="new-visit-form"
            icon="radio"
            title="Dictate live"
            description="Speak a summary into your mic — we'll clean it up."
            value="voice_dictation"
          />
          <ModeTileWithForm
            formId="new-visit-form"
            icon="pen-line"
            title="Text to SOAP"
            description="Type bullets — AI expands them into a full note."
            value="text_notes"
          />
        </div>
      </div>
    </>
  );
}

function PatientPill({
  patient,
  onChangePatient,
}: {
  patient: SelectedPatient;
  onChangePatient?: () => void;
}) {
  return (
    <div
      className="mb-8 flex flex-wrap items-center gap-3 rounded-md border border-linear-border bg-linear-surface-2 px-3 py-2"
    >
      <div
        aria-hidden
        className="flex h-8 w-8 flex-none items-center justify-center rounded-md text-[12px] font-semibold"
        style={{
          background: 'var(--color-linear-sage-tint)',
          color: 'var(--color-linear-sage-bright)',
        }}
      >
        {patient.name.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[10.5px] uppercase tracking-[0.07em] text-linear-text-3">
            Visit for
          </span>
          <span className="truncate text-[14px] font-medium text-linear-text">
            {patient.name}
          </span>
          <span className="truncate text-[12px] text-linear-text-3">
            {formatDob(patient.dateOfBirth)}
          </span>
        </div>
      </div>
      {onChangePatient ? (
        <button
          type="button"
          onClick={onChangePatient}
          className="qm-lin-btn"
        >
          <ArrowLeftRight className="h-3 w-3" aria-hidden />
          Change patient
        </button>
      ) : (
        <Link
          href="/visits/new"
          className="qm-lin-btn"
          style={{ textDecoration: 'none' }}
        >
          <ArrowLeftRight className="h-3 w-3" aria-hidden />
          Change patient
        </Link>
      )}
    </div>
  );
}
