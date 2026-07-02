'use client';

// ============================================================================
// PlaceholderAdvisoryDialog (F-7, 2026-07-02) — client-side ADVISORY confirm
// shown when the doctor opens the Sign flow while one or more sections still
// carry the anchored-verifier "[set aside for your review]" placeholder.
// ----------------------------------------------------------------------------
// Advisory ONLY: "Sign anyway" continues to the real Sign & Send modal; the
// server sign route is deliberately untouched (the fail-closed Rx/E-M gates
// remain the authority). Pattern cloned from rx/override-confirm-modal.tsx —
// controlled Radix Dialog (focus trap, Esc-close, aria-modal, focus-return
// for free), amber advisory styling (the review-banner family, not danger).
// ============================================================================

import * as Dialog from '@radix-ui/react-dialog';
import { Ic } from '@/components/ui/icon';

export interface PlaceholderAdvisoryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Section labels still holding the set-aside placeholder (verbatim). */
  sections: string[];
  /** Count of review suggestions in the lane (0 = unknown/none). */
  suggestionCount: number;
  /** Continue to the real Sign & Send modal. */
  onContinue: () => void;
}

export function PlaceholderAdvisoryDialog({
  open,
  onOpenChange,
  sections,
  suggestionCount,
  onContinue,
}: PlaceholderAdvisoryDialogProps) {
  const n = sections.length;
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="qm-lin-spotlight" />
        <Dialog.Content
          className="qm-lin-spotlight-panel qm-lin-blur-in"
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 50,
            width: 'calc(100% - 40px)',
            maxWidth: 480,
            outline: 'none',
            padding: 0,
            border: '1px solid color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 14,
              padding: '20px 24px 8px',
            }}
          >
            <div
              aria-hidden
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: '1px solid color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
                background: 'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--color-linear-amber)',
                flex: '0 0 36px',
              }}
            >
              <Ic.alert width={18} height={18} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Dialog.Title
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 17,
                  fontWeight: 500,
                  letterSpacing: '-0.012em',
                  color: 'var(--color-linear-text)',
                }}
              >
                {n === 1
                  ? '1 section still has content set aside for review'
                  : `${n} sections still have content set aside for review`}
              </Dialog.Title>
              <Dialog.Description
                style={{
                  marginTop: 8,
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                  lineHeight: 1.55,
                }}
              >
                The note will be signed and exported with the placeholder text
                in place of the set-aside content
                {suggestionCount > 0
                  ? ` — ${suggestionCount} review suggestion${suggestionCount === 1 ? '' : 's'} ${suggestionCount === 1 ? 'is' : 'are'} waiting to be adopted or dismissed.`
                  : '.'}
              </Dialog.Description>
              <ul
                style={{
                  margin: '10px 0 0',
                  padding: '10px 12px',
                  listStyle: 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  borderRadius: 8,
                  border: '1px solid var(--color-linear-border)',
                  background: 'var(--color-linear-surface-2)',
                }}
              >
                {sections.map((label) => (
                  <li
                    key={label}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      letterSpacing: '0.04em',
                      color: 'var(--color-linear-text-2)',
                    }}
                  >
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
              padding: '16px 24px 20px',
            }}
          >
            <Dialog.Close asChild>
              <button
                type="button"
                className="qm-lin-btn"
                style={{ padding: '8px 14px', height: 32 }}
              >
                Go back to review
              </button>
            </Dialog.Close>
            <button
              type="button"
              className="qm-lin-btn-primary"
              style={{ padding: '8px 14px', height: 32 }}
              onClick={onContinue}
            >
              Sign anyway
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
