'use client';

// ============================================================================
// Duplicate-patient confirmation modal (T-M17.2 Phase 3 Commit 9)
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders inside `.qm-lin-spotlight`
// chrome with hairline-bordered match rows on a surface-2 backdrop.
// The `theme` prop is preserved as a no-op.
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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
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
}: Props) {
  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'qm-lin-spotlight',
            'data-[state=open]:animate-in data-[state=open]:fade-in'
          )}
        />
        <Dialog.Content
          className={cn(
            'qm-lin-spotlight-panel qm-lin-blur-in',
            'fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 outline-none'
          )}
          style={{ padding: 0 }}
        >
          <div
            className="flex items-start gap-3"
            style={{ padding: '20px 24px 4px' }}
          >
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-md"
              style={{
                background: 'rgba(212,164,55,0.15)',
                border: '1px solid rgba(212,164,55,0.32)',
                color: 'var(--color-linear-warning)',
              }}
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 16,
                  fontWeight: 500,
                  letterSpacing: '-0.01em',
                  color: 'var(--color-linear-text)',
                }}
              >
                Found similar patient{matches.length === 1 ? '' : 's'}
              </Dialog.Title>
              <Dialog.Description
                style={{
                  marginTop: 6,
                  marginBottom: 0,
                  fontSize: 13,
                  lineHeight: 1.55,
                  color: 'var(--color-linear-text-2)',
                }}
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
              className="flex-none rounded-md p-1 text-linear-text-3 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <ul className="space-y-2" style={{ padding: '12px 24px 4px' }}>
            {matches.map((m) => (
              <li
                key={m.patient.id}
                className="flex items-center gap-3 rounded-md border border-linear-border bg-linear-surface-2 px-3 py-2.5"
              >
                <div
                  aria-hidden
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-md text-[12px] font-semibold"
                  style={{
                    background: 'var(--color-linear-sage-tint)',
                    color: 'var(--color-linear-sage-bright)',
                  }}
                >
                  {m.patient.name.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14px] font-medium text-linear-text">
                    {m.patient.name}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-linear-text-3">
                    <span>{formatDob(m.patient.dateOfBirth)}</span>
                    <span aria-hidden>·</span>
                    <span className="text-linear-text-2">
                      {formatScore(m.score)}
                    </span>
                    {m.dobMatches === true && (
                      <span className="qm-lin-pill qm-lin-pill--sage">
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
                  className="qm-lin-btn flex-none"
                >
                  Use this
                </button>
              </li>
            ))}
          </ul>

          <div
            className="flex items-center justify-end gap-2"
            style={{
              marginTop: 12,
              borderTop: '1px solid var(--color-linear-hairline)',
              background: 'var(--color-linear-surface-2)',
              padding: '12px 24px',
            }}
          >
            <button type="button" onClick={onClose} className="qm-lin-btn">
              Back
            </button>
            <button
              type="button"
              onClick={onCreateAnyway}
              className="qm-lin-btn"
            >
              Create new anyway
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
