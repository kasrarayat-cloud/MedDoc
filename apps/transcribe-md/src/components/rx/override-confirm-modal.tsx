'use client';

// ============================================================================
// Override confirm modal (DESIGN_SPEC §4.1 critical · override flow).
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders inside `.qm-lin-spotlight`
// chrome with hairline-bordered surface-1 panels and a danger-tinted
// alert chip. Reason validation, recordOverride wiring, and onSuccess
// fire are unchanged.
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
        <Dialog.Overlay className="qm-lin-spotlight" />
        <Dialog.Content
          className="qm-lin-spotlight-panel qm-lin-blur-in"
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
            outline: 'none',
            padding: 0,
            border: '1px solid rgba(212, 87, 74, 0.32)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 14,
              padding: '20px 24px 4px',
            }}
          >
            <div
              aria-hidden
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: '1px solid rgba(212, 87, 74, 0.32)',
                background: 'rgba(212, 87, 74, 0.10)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--color-linear-danger)',
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
                  fontSize: 18,
                  fontWeight: 500,
                  letterSpacing: '-0.012em',
                  color: 'var(--color-linear-text)',
                }}
              >
                {warning.headline}
              </Dialog.Title>
              {warning.action && (
                <Dialog.Description
                  style={{
                    marginTop: 6,
                    fontSize: 13,
                    color: 'var(--color-linear-text-2)',
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
                  color: 'var(--color-linear-text-2)',
                  lineHeight: 1.55,
                }}
              >
                You&apos;re about to sign past a critical warning. Record the
                clinical reason below — it will be attached to the visit
                audit log.
              </p>
            </div>
          </div>

          <div style={{ padding: '12px 24px 4px' }}>
            <label
              htmlFor="override-reason"
              style={{
                display: 'block',
                marginBottom: 6,
                fontSize: 10.5,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.07em',
                textTransform: 'uppercase',
                fontWeight: 500,
                color: 'var(--color-linear-text-3)',
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
              className="block w-full rounded-md border border-linear-border bg-linear-surface-2 px-3 py-2 text-[13.5px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30"
              style={{
                resize: 'vertical',
                fontFamily: 'var(--font-sans)',
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
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-mono)',
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
                  color: 'var(--color-linear-danger)',
                }}
              >
                {error}
              </p>
            )}
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
              marginTop: 14,
              padding: '12px 24px',
              borderTop: '1px solid var(--color-linear-hairline)',
              background: 'var(--color-linear-surface-2)',
            }}
          >
            <Dialog.Close asChild>
              <button
                type="button"
                className="qm-lin-btn"
                disabled={submitting}
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={!canSubmit}
              className="qm-lin-btn"
              style={{
                background: 'rgba(212, 87, 74, 0.16)',
                borderColor: 'rgba(212, 87, 74, 0.45)',
                color: 'var(--color-linear-danger)',
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
