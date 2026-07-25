'use client';

// ============================================================================
// CopySectionButton — small "Copy section" pill on each visit-detail tab
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. A `.qm-lin-btn`-shaped chip with a
// copy icon; flips to a check + "Copied" for 1.5s after a successful
// clipboard write. No VisitDelivery row — too granular for a DELIVERY
// row. The `theme` prop is preserved as a no-op for back-compat.
//
// S4b (2026-07-25): it does now emit an AUDIT row. The two are different
// things — a VisitDelivery models "the note was sent somewhere we track", an
// audit row models "PHI left the application". Copying a whole SOAP section to
// the OS clipboard is the second, and it used to leave no trace at all.
// ============================================================================

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { reportClipboardCopy } from '@/lib/clipboard-audit';

type CopySectionButtonTheme = 'legacy' | 'clinician';

interface CopySectionButtonProps {
  /** Visit this text belongs to — required so the copy can be audited. */
  visitId: string;
  /** The plaintext payload to write to the clipboard. */
  text: string;
  /** Short label shown when the button is idle, e.g. "Copy SOAP". */
  label?: string;
  /** Human-readable section name used in toasts. */
  section: string;
  className?: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: CopySectionButtonTheme;
}

export function CopySectionButton({
  visitId,
  text,
  label = 'Copy section',
  section,
  className,
}: CopySectionButtonProps) {
  const [copied, setCopied] = useState(false);

  const onClick = useCallback(async () => {
    if (!text) {
      toast.info('Nothing to copy in this section.');
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      // Only after the write RESOLVES — a blocked clipboard throws, and
      // auditing a disclosure that never happened would be a false record.
      reportClipboardCopy(visitId, 'section', section, text);
      setCopied(true);
      toast.success(`${section} copied`);
      // Plain timeout — not a setState inside an effect, so the
      // react-hooks/set-state-in-effect lint stays happy.
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Copy blocked by browser', {
        description: 'Grant clipboard access in your browser settings.',
      });
    }
  }, [visitId, text, section]);

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn('qm-lin-btn', className)}
    >
      {copied ? (
        <>
          <Check className="h-3 w-3" aria-hidden />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" aria-hidden />
          {label}
        </>
      )}
    </button>
  );
}
