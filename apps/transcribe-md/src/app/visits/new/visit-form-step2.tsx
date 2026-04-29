'use client';

// ============================================================================
// Step 2 of /visits/new — specialty / CC / capture-mode (T-M17.2 Commit 9)
// ----------------------------------------------------------------------------
// Renders the existing new-visit form fields (SpecialtyDropdown, CC input,
// the three ModeTileWithForm submit buttons) with a patient pill pinned
// to the top. Submits to createVisitAction via the hidden patientId
// field — patientName is NOT submitted, the server action derives the
// canonical name from the FK.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark glass + violet
// gradient pill chrome verbatim. `theme="clinician"` swaps to a soft
// cream patient pill with `.qm-cl-avatar-sage`, Source Serif 4 names,
// `.qm-cl-input` form fields, and Clinician-themed mode tiles.
// ============================================================================

import Link from 'next/link';
import { ArrowLeftRight } from 'lucide-react';

import { cn } from '@/lib/cn';
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
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: VisitFormStep2Theme;
}

function formatDob(iso: string | null): string {
  return iso ? `b. ${iso.slice(0, 10)}` : 'No DOB on file';
}

export function VisitFormStep2({
  patient,
  onChangePatient,
  specialties,
  defaultSpecialty,
  theme = 'legacy',
}: Props) {
  const isClinician = theme === 'clinician';

  return (
    <>
      <PatientPill
        patient={patient}
        onChangePatient={onChangePatient}
        theme={theme}
      />

      <form
        id="new-visit-form"
        action={createVisitAction}
        className="grid grid-cols-1 gap-6 sm:grid-cols-2"
      >
        <input type="hidden" name="patientId" value={patient.id} />

        <div>
          <label
            className={cn(
              'mb-1.5 block text-[12px] font-medium tracking-tight',
              isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
            )}
          >
            Specialty
          </label>
          <SpecialtyDropdown
            options={specialties}
            name="specialty"
            defaultValue={defaultSpecialty}
            theme={theme}
          />
        </div>

        <div>
          <label
            className={cn(
              'mb-1.5 block text-[12px] font-medium tracking-tight',
              isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
            )}
          >
            Chief complaint{' '}
            <span
              className={cn(
                'font-normal',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              (optional)
            </span>
          </label>
          <input
            name="chiefComplaint"
            type="text"
            className={
              isClinician
                ? 'qm-cl-input block w-full'
                : 'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
            }
            placeholder="e.g. Headache for 3 days"
          />
        </div>
      </form>

      <div className="mt-10">
        <div
          className={cn(
            'mb-4 text-[13px] font-medium tracking-tight',
            isClinician
              ? 'qm-cl-section-label'
              : 'text-text-tertiary'
          )}
        >
          {isClinician ? 'Pick a capture mode' : 'Pick a capture mode'}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ModeTileWithForm
            formId="new-visit-form"
            icon="mic"
            title="Upload audio"
            description="Record your visit on your phone, then drop the file here."
            value="audio_upload"
            theme={theme}
          />
          <ModeTileWithForm
            formId="new-visit-form"
            icon="radio"
            title="Dictate live"
            description="Speak a summary into your mic — we'll clean it up."
            value="voice_dictation"
            theme={theme}
          />
          <ModeTileWithForm
            formId="new-visit-form"
            icon="pen-line"
            title="Text to SOAP"
            description="Type bullets — AI expands them into a full note."
            value="text_notes"
            theme={theme}
          />
        </div>
      </div>
    </>
  );
}

function PatientPill({
  patient,
  onChangePatient,
  theme,
}: {
  patient: SelectedPatient;
  onChangePatient?: () => void;
  theme: VisitFormStep2Theme;
}) {
  const isClinician = theme === 'clinician';

  return (
    <div
      className={cn(
        'mb-8 flex flex-wrap items-center gap-3 rounded-full px-4 py-2',
        isClinician
          ? 'border border-clinician-line bg-clinician-cream-card'
          : 'border border-border-default bg-bg-surface-1/60'
      )}
    >
      {isClinician ? (
        <div
          aria-hidden
          className="qm-cl-avatar qm-cl-avatar-sage flex-none"
          style={{
            width: 30,
            height: 30,
            borderRadius: 10,
            fontSize: 12,
          }}
        >
          {patient.name.charAt(0).toUpperCase()}
        </div>
      ) : (
        <div
          aria-hidden
          className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[11px] font-semibold text-white"
        >
          {patient.name.charAt(0).toUpperCase()}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              'text-[11px] uppercase tracking-[0.08em]',
              isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
            )}
          >
            Visit for
          </span>
          <span
            className={cn(
              'truncate',
              isClinician
                ? 'qm-cl-serif text-clinician-ink'
                : 'text-[14px] font-medium text-text-primary'
            )}
            style={isClinician ? { fontSize: 15 } : undefined}
          >
            {patient.name}
          </span>
          <span
            className={cn(
              'truncate text-[12px]',
              isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
            )}
          >
            {formatDob(patient.dateOfBirth)}
          </span>
        </div>
      </div>
      {onChangePatient ? (
        <button
          type="button"
          onClick={onChangePatient}
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-2',
            isClinician
              ? 'text-clinician-ink-2 hover:text-clinician-ink focus-visible:ring-clinician-sage'
              : 'text-text-tertiary hover:text-text-primary focus-visible:ring-violet-500'
          )}
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
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-2',
            isClinician
              ? 'text-clinician-ink-2 hover:text-clinician-ink focus-visible:ring-clinician-sage'
              : 'text-text-tertiary hover:text-text-primary focus-visible:ring-violet-500'
          )}
        >
          <ArrowLeftRight className="h-3 w-3" aria-hidden />
          Change patient
        </Link>
      )}
    </div>
  );
}
