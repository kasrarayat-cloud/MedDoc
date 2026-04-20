'use client';

// ============================================================================
// Duplicate-patient confirmation modal (T-M17.2 Phase 3 Commit 9)
// ----------------------------------------------------------------------------
// Opened by PatientPicker when POST /api/patients/fuzzy-match returns
// candidates with score > 0.6 for a just-entered name. Caller passes
// three callbacks:
//   onClose           dismiss without picking (back to the inline form,
//                     pending values preserved)
//   onUseExisting(p)  doctor clicked "Use this" on one of the matches
//   onCreateAnyway()  doctor rejected the matches and wants to create
//                     the new patient using the pending form values
// ============================================================================

import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, X, Check } from 'lucide-react';

import type { FuzzyMatch, SelectedPatient } from './patient-types';

interface Props {
  matches: FuzzyMatch[];
  onClose: () => void;
  onUseExisting: (p: SelectedPatient) => void;
  onCreateAnyway: () => void;
}

function formatScore(s: number): string {
  return `${Math.round(s * 100)}% match`;
}

function formatDob(iso: string | null): string {
  return iso ? `b. ${iso.slice(0, 10)}` : 'no DOB on file';
}

export function DuplicateModal({
  matches,
  onClose,
  onUseExisting,
  onCreateAnyway,
}: Props) {
  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl outline-none">
          <div className="mb-5 flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-warning/15 text-warning"
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title className="text-[15px] font-semibold tracking-tight text-text-primary">
                Found similar patient{matches.length === 1 ? '' : 's'}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] text-text-tertiary">
                One of these might be the same person. Pick an existing
                record, or create a new patient if they&apos;re genuinely
                distinct.
              </Dialog.Description>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="flex-none rounded-md p-1 text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <ul className="space-y-2">
            {matches.map((m) => (
              <li
                key={m.patient.id}
                className="flex items-center gap-3 rounded-lg border border-border-subtle bg-bg-surface-1/60 px-3 py-2.5"
              >
                <div
                  aria-hidden
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[12px] font-semibold text-white"
                >
                  {m.patient.name.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-medium text-text-primary">
                    {m.patient.name}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-text-muted">
                    <span>{formatDob(m.patient.dateOfBirth)}</span>
                    <span aria-hidden>·</span>
                    <span className="text-text-tertiary">
                      {formatScore(m.score)}
                    </span>
                    {m.dobMatches === true && (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-success/15 px-1.5 py-0.5 text-success">
                        <Check className="h-2.5 w-2.5" />
                        DOB matches
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    onUseExisting({
                      id: m.patient.id,
                      name: m.patient.name,
                      dateOfBirth: m.patient.dateOfBirth,
                      externalId: m.patient.externalId,
                    })
                  }
                  className="flex-none rounded-full border border-border-subtle bg-bg-surface-2 px-3 py-1 text-[12px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary"
                >
                  Use this
                </button>
              </li>
            ))}
          </ul>

          <div className="mt-6 flex items-center justify-end gap-2 border-t border-border-subtle pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full px-3 py-2 text-[13px] text-text-tertiary hover:text-text-secondary"
            >
              Back
            </button>
            <button
              type="button"
              onClick={onCreateAnyway}
              className="rounded-full border border-border-default bg-bg-surface-2 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary"
            >
              Create new anyway
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
