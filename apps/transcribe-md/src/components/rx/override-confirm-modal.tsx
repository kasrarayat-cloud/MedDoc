'use client';

// ============================================================================
// Override confirm modal (DESIGN_SPEC §4.1 critical · override flow).
// ----------------------------------------------------------------------------
// Opened by the O key or the "Override & sign anyway" button on the
// RxWarningCard's critical variant. Collects a 10–500 char reason,
// then calls the `recordOverride` server action. The action returns a
// discriminated union; success closes the modal + fires onSuccess,
// failure keeps the modal open with an inline error.
//
// Focus moves to the textarea on open; returns to the trigger on
// close via Radix's built-in `onCloseAutoFocus`. Escape cancels.
// ============================================================================

import { useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';
import {
  recordOverride,
  type RecordOverrideInput,
} from '@/lib/rx-warning-audit';

const REASON_MIN = 10;
const REASON_MAX = 500;

export interface OverrideConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  warning: {
    id: string;
    rxLineNumber: number;
    sev: string;
    headline: string;
    action?: string;
  };
  visitId: string;
  onSuccess?: (auditId: string) => void;
}

export function OverrideConfirmModal({
  open,
  onOpenChange,
  warning,
  visitId,
  onSuccess,
}: OverrideConfirmModalProps) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const trimmed = reason.trim();
  const canSubmit =
    !submitting && trimmed.length >= REASON_MIN && reason.length <= REASON_MAX;

  function reset() {
    setReason('');
    setError(null);
    setSubmitting(false);
  }

  async function onConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      const input: RecordOverrideInput = {
        visitId,
        warningId: warning.id,
        rxLineNumber: warning.rxLineNumber,
        severity: warning.sev,
        headline: warning.headline,
        reason,
      };
      const result = await recordOverride(input);
      if (result.ok) {
        toast.success('Override recorded', {
          description: 'Audit entry saved. You can sign this visit now.',
        });
        onSuccess?.(result.auditId);
        onOpenChange(false);
        reset();
      } else {
        setError(result.error);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) reset();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 40,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
          }}
        />
        <Dialog.Content
          className="qm-app"
          onOpenAutoFocus={(e) => {
            // Skip Radix's default focus-first-focusable — we want the
            // textarea, not the Cancel button.
            e.preventDefault();
            textareaRef.current?.focus();
          }}
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 50,
            width: 'calc(100% - 40px)',
            maxWidth: 520,
            borderRadius: 14,
            border: '1px solid rgba(251, 113, 133, 0.3)',
            background: 'var(--bg-1)',
            padding: 24,
            outline: 'none',
            boxShadow: 'var(--shadow-2)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 14,
              marginBottom: 16,
            }}
          >
            <div
              aria-hidden
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: '1px solid rgba(251, 113, 133, 0.35)',
                background: 'rgba(251, 113, 133, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FB7185',
                flex: '0 0 36px',
              }}
            >
              <Ic.alert width={18} height={18} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Dialog.Title
                className="qm-serif"
                style={{
                  margin: 0,
                  fontSize: 20,
                  fontWeight: 500,
                  letterSpacing: '-0.015em',
                  color: 'var(--fg)',
                }}
              >
                {warning.headline}
              </Dialog.Title>
              {warning.action && (
                <Dialog.Description
                  style={{
                    marginTop: 6,
                    fontSize: 13,
                    color: 'var(--fg-3)',
                    lineHeight: 1.55,
                  }}
                >
                  {warning.action}
                </Dialog.Description>
              )}
              <p
                style={{
                  margin: '12px 0 0',
                  fontSize: 12.5,
                  color: 'var(--fg-2)',
                  lineHeight: 1.55,
                }}
              >
                You&apos;re about to sign past a critical warning. Record the
                clinical reason below — it will be attached to the visit
                audit log.
              </p>
            </div>
          </div>

          <label
            htmlFor="override-reason"
            style={{
              display: 'block',
              marginBottom: 6,
              fontSize: 11,
              fontFamily: 'var(--mono)',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'var(--fg-3)',
            }}
          >
            Reason for override
          </label>
          <textarea
            id="override-reason"
            ref={textareaRef}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={REASON_MAX}
            rows={4}
            placeholder="Why is it safe to sign past this warning?"
            className="qm-input"
            style={{
              resize: 'vertical',
              fontFamily: 'var(--sans)',
              fontSize: 13.5,
              lineHeight: 1.5,
            }}
            aria-describedby="override-reason-help"
            aria-invalid={error ? 'true' : undefined}
          />
          <div
            id="override-reason-help"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 6,
              fontSize: 11,
              color: 'var(--fg-4)',
              fontFamily: 'var(--mono)',
            }}
          >
            <span>
              {trimmed.length < REASON_MIN
                ? `${REASON_MIN - trimmed.length} more character${
                    REASON_MIN - trimmed.length === 1 ? '' : 's'
                  } required`
                : 'Ready'}
            </span>
            <span>
              {reason.length}/{REASON_MAX}
            </span>
          </div>

          {error && (
            <p
              role="alert"
              style={{
                marginTop: 10,
                fontSize: 12.5,
                color: 'var(--coral)',
              }}
            >
              {error}
            </p>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
              marginTop: 18,
              paddingTop: 14,
              borderTop: '1px solid var(--line-soft)',
            }}
          >
            <Dialog.Close asChild>
              <button
                type="button"
                className="qm-btn qm-btn-ghost"
                disabled={submitting}
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={!canSubmit}
              className="qm-btn"
              style={{
                background:
                  'linear-gradient(180deg, rgba(251, 113, 133, 0.28), rgba(251, 113, 133, 0.14))',
                border: '1px solid rgba(251, 113, 133, 0.55)',
                color: canSubmit ? '#FDA4AF' : '#B79494',
                opacity: canSubmit ? 1 : 0.55,
                cursor: canSubmit ? 'pointer' : 'not-allowed',
              }}
            >
              {submitting ? 'Recording…' : 'Confirm override'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
