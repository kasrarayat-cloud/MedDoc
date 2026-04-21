'use client';

// ============================================================================
// Step 2 of /visits/new — specialty / CC / capture-mode (T-M17.2 Commit 9)
// ----------------------------------------------------------------------------
// Renders the existing new-visit form fields (SpecialtyDropdown, CC input,
// the three ModeTileWithForm submit buttons) with a patient pill pinned
// to the top. Submits to createVisitAction via the hidden patientId
// field — patientName is NOT submitted, the server action derives the
// canonical name from the FK.
// ============================================================================

import Link from 'next/link';
import { ArrowLeftRight } from 'lucide-react';

import { SpecialtyDropdown } from '@/components/specialty-dropdown';
import {
  TemplateDropdown,
  type TemplateOption,
} from '@/components/template-dropdown';
import { createVisitAction } from '@/actions/visits';
import { ModeTileWithForm } from './mode-tile-with-form';
import type { SPECIALTIES } from '@/lib/specialties';
import type { SelectedPatient } from './patient-types';

type Specialty = (typeof SPECIALTIES)[number];

interface Props {
  patient: SelectedPatient;
  /** Undefined when the caller opened /visits/new?patientId=… — we
   *  still want the "Change patient" link to work (redirect to the
   *  unlocked flow). Defined when the caller picked via Step 1 — the
   *  link becomes a purely client-side "go back". */
  onChangePatient?: () => void;
  specialties: Specialty[];
  defaultSpecialty: string;
  /** Doctor's non-deleted templates. Empty array hides the picker
   *  entirely — no point showing "Standard only" as a single choice. */
  templates: TemplateOption[];
}

function formatDob(iso: string | null): string {
  return iso ? `b. ${iso.slice(0, 10)}` : 'No DOB on file';
}

export function VisitFormStep2({
  patient,
  onChangePatient,
  specialties,
  defaultSpecialty,
  templates,
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
          <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
            Specialty
          </label>
          <SpecialtyDropdown
            options={specialties}
            name="specialty"
            defaultValue={defaultSpecialty}
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
            Chief complaint{' '}
            <span className="font-normal text-text-muted">(optional)</span>
          </label>
          <input
            name="chiefComplaint"
            type="text"
            className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
            placeholder="e.g. Headache for 3 days"
          />
        </div>

        {templates.length > 0 && (
          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
              Output template{' '}
              <span className="font-normal text-text-muted">(optional)</span>
            </label>
            <TemplateDropdown options={templates} name="templateId" />
            <p className="mt-1.5 text-[11px] text-text-muted">
              “Standard only” delivers the usual SOAP, ICD, Rx outputs.
              Picking a template also produces a .docx filled with your
              template&apos;s layout.{' '}
              <Link
                href="/settings/templates"
                className="text-text-tertiary underline-offset-2 hover:text-text-primary hover:underline"
              >
                Manage templates
              </Link>
            </p>
          </div>
        )}
      </form>

      <div className="mt-10">
        <div className="mb-4 text-[13px] font-medium tracking-tight text-text-tertiary">
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
    <div className="mb-8 flex flex-wrap items-center gap-3 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2">
      <div
        aria-hidden
        className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[11px] font-semibold text-white"
      >
        {patient.name.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-[11px] uppercase tracking-[0.08em] text-text-muted">
            Visit for
          </span>
          <span className="truncate text-[14px] font-medium text-text-primary">
            {patient.name}
          </span>
          <span className="truncate text-[12px] text-text-tertiary">
            {formatDob(patient.dateOfBirth)}
          </span>
        </div>
      </div>
      {onChangePatient ? (
        <button
          type="button"
          onClick={onChangePatient}
          className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] text-text-tertiary transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <ArrowLeftRight className="h-3 w-3" aria-hidden />
          Change patient
        </button>
      ) : (
        // When the patient was locked in by ?patientId=, "change
        // patient" is a navigation away from the pre-selected flow
        // rather than a state reset.
        <Link
          href="/visits/new"
          className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] text-text-tertiary transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <ArrowLeftRight className="h-3 w-3" aria-hidden />
          Change patient
        </Link>
      )}
    </div>
  );
}
