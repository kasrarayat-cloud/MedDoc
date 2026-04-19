'use client';

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';

interface CopySectionButtonProps {
  /** The plaintext payload to write to the clipboard. */
  text: string;
  /** Short label shown when the button is idle, e.g. "Copy SOAP". */
  label?: string;
  /** Human-readable section name used in toasts. */
  section: string;
  className?: string;
}

/**
 * Small top-right button that copies a section's plaintext into the
 * clipboard. Used on SOAP/Codes/Rx/Extras tabs for piecemeal workflows
 * where the doctor doesn't want the full Sign & Send modal. No
 * VisitDelivery row — too granular to be useful in the audit trail.
 */
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
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1 text-[11px] text-text-tertiary',
        'transition-colors hover:border-border-default hover:text-text-secondary',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
        className
      )}
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
