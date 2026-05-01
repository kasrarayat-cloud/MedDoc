'use client';

// ============================================================================
// CopySectionButton — small "Copy section" pill on each visit-detail tab
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. A `.qm-lin-btn`-shaped chip with a
// copy icon; flips to a check + "Copied" for 1.5s after a successful
// clipboard write. No VisitDelivery row — too granular for the audit
// trail. The `theme` prop is preserved as a no-op for back-compat.
// ============================================================================

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';

type CopySectionButtonTheme = 'legacy' | 'clinician';

interface CopySectionButtonProps {
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
  }, [text, section]);

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
