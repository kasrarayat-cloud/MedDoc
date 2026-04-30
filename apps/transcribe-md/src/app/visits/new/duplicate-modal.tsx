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
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark-glass overlay/content
// chrome verbatim. `theme="clinician"` swaps to a warm-charcoal scrim,
// `.qm-cl-card`-style content surface, sage focus rings. The Radix
// Portal mounts at <body>, OUTSIDE any `.qm-cl-app` wrapper, so the
// Content node carries `qm-cl-app` itself when in Clinician mode (same
// pattern as the Batch D sign-and-send-modal).
// ============================================================================

import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, X, Check } from 'lucide-react';

import { cn } from '@/lib/cn';
import type { FuzzyMatch, SelectedPatient } from './patient-types';

type DuplicateModalTheme = 'legacy' | 'clinician';

interface Props {
  matches: FuzzyMatch[];
  onClose: () => void;
  onUseExisting: (p: SelectedPatient) => void;
  onCreateAnyway: () => void;
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: DuplicateModalTheme;
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
  theme = 'legacy',
}: Props) {
  const isClinician = theme === 'clinician';

  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-40 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in',
            isClinician ? 'bg-[rgba(43,38,32,0.32)]' : 'bg-black/70'
          )}
        />
        <Dialog.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 p-6 shadow-2xl outline-none',
            isClinician
              ? // Wrap in .qm-cl-app so .qm-cl-* utilities resolve in the Portal.
                'qm-cl-app rounded-2xl border border-clinician-line bg-clinician-cream-card shadow-[0_32px_96px_-24px_rgba(43,38,32,0.18)]'
              : 'rounded-2xl border border-border-default bg-bg-surface-1'
          )}
        >
          <div className="mb-5 flex items-start gap-3">
            <div
              aria-hidden
              className={cn(
                'flex h-9 w-9 flex-none items-center justify-center rounded-full',
                isClinician
                  ? 'bg-clinician-amber-tint text-clinician-amber-deep'
                  : 'bg-warning/15 text-warning'
              )}
              style={
                isClinician
                  ? {
                      background: 'var(--amber-tint)',
                      color: 'var(--amber-deep)',
                    }
                  : undefined
              }
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title
                className={cn(
                  'text-[15px] tracking-tight',
                  isClinician
                    ? 'qm-cl-serif text-clinician-ink'
                    : 'font-semibold text-text-primary'
                )}
                style={
                  isClinician
                    ? { fontWeight: 500, letterSpacing: '-0.01em', fontSize: 18 }
                    : undefined
                }
              >
                Found similar patient{matches.length === 1 ? '' : 's'}
              </Dialog.Title>
              <Dialog.Description
                className={cn(
                  'mt-1 text-[13px]',
                  isClinician
                    ? 'text-clinician-ink-2'
                    : 'text-text-tertiary'
                )}
              >
                One of these might be the same person. Pick an existing
                record, or create a new patient if they&apos;re genuinely
                distinct.
              </Dialog.Description>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className={cn(
                'flex-none rounded-md p-1 focus-visible:outline-none focus-visible:ring-2',
                isClinician
                  ? 'text-clinician-ink-3 hover:text-clinician-ink-2 focus-visible:ring-clinician-sage'
                  : 'text-text-muted hover:text-text-secondary focus-visible:ring-violet-500'
              )}
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <ul className="space-y-2">
            {matches.map((m) => (
              <li
                key={m.patient.id}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5',
                  isClinician
                    ? 'border border-clinician-line bg-clinician-cream'
                    : 'border border-border-subtle bg-bg-surface-1/60'
                )}
              >
                {isClinician ? (
                  <div
                    aria-hidden
                    className="qm-cl-avatar qm-cl-avatar-sage flex-none"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 10,
                      fontSize: 13,
                    }}
                  >
                    {m.patient.name.charAt(0).toUpperCase()}
                  </div>
                ) : (
                  <div
                    aria-hidden
                    className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[12px] font-semibold text-white"
                  >
                    {m.patient.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div
                    className={cn(
                      'truncate text-[13px]',
                      isClinician
                        ? 'qm-cl-serif font-medium text-clinician-ink'
                        : 'font-medium text-text-primary'
                    )}
                    style={isClinician ? { fontSize: 15 } : undefined}
                  >
                    {m.patient.name}
                  </div>
                  <div
                    className={cn(
                      'flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]',
                      isClinician
                        ? 'text-clinician-ink-3'
                        : 'text-text-muted'
                    )}
                  >
                    <span>{formatDob(m.patient.dateOfBirth)}</span>
                    <span aria-hidden>·</span>
                    <span
                      className={
                        isClinician
                          ? 'text-clinician-ink-2'
                          : 'text-text-tertiary'
                      }
                    >
                      {formatScore(m.score)}
                    </span>
                    {m.dobMatches === true && (
                      <span
                        className={
                          isClinician
                            ? 'qm-cl-pill qm-cl-pill-sage'
                            : 'inline-flex items-center gap-0.5 rounded-full bg-success/15 px-1.5 py-0.5 text-success'
                        }
                        style={
                          isClinician
                            ? { fontSize: 10.5, padding: '2px 8px' }
                            : undefined
                        }
                      >
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
                  className={
                    isClinician
                      ? 'qm-cl-btn qm-cl-btn-soft flex-none'
                      : 'flex-none rounded-full border border-border-subtle bg-bg-surface-2 px-3 py-1 text-[12px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary'
                  }
                  style={
                    isClinician
                      ? { padding: '6px 14px', fontSize: 12.5 }
                      : undefined
                  }
                >
                  Use this
                </button>
              </li>
            ))}
          </ul>

          <div
            className={cn(
              'mt-6 flex items-center justify-end gap-2 pt-4',
              isClinician
                ? 'border-t border-clinician-line'
                : 'border-t border-border-subtle'
            )}
          >
            <button
              type="button"
              onClick={onClose}
              className={
                isClinician
                  ? 'qm-cl-btn qm-cl-btn-ghost'
                  : 'rounded-full px-3 py-2 text-[13px] text-text-tertiary hover:text-text-secondary'
              }
              style={
                isClinician ? { padding: '8px 16px', fontSize: 13 } : undefined
              }
            >
              Back
            </button>
            <button
              type="button"
              onClick={onCreateAnyway}
              className={
                isClinician
                  ? 'qm-cl-btn qm-cl-btn-soft'
                  : 'rounded-full border border-border-default bg-bg-surface-2 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary'
              }
              style={
                isClinician ? { padding: '8px 18px', fontSize: 13 } : undefined
              }
            >
              Create new anyway
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
