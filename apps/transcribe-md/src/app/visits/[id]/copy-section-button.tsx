'use client';

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
  /** Phase 2 (Clinician remodel) — additive theme prop, default
   *  `'legacy'` so non-migrated callers keep the violet-ring chip. */
  theme?: CopySectionButtonTheme;
}

/**
 * Small top-right button that copies a section's plaintext into the
 * clipboard. Used on SOAP/Codes/Rx/Extras tabs for piecemeal workflows
 * where the doctor doesn't want the full Sign & Send modal. No
 * VisitDelivery row — too granular to be useful in the audit trail.
 *
 * Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
 * `theme` prop. Default `'legacy'` keeps the existing dark chip
 * verbatim. Clinician branch renders the same affordance with the
 * `.qm-cl-btn-ghost`-style cream chrome (cream-2 hover, sage focus
 * ring). Click handler + clipboard semantics unchanged.
 */
export function CopySectionButton({
  text,
  label = 'Copy section',
  section,
  className,
  theme = 'legacy',
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

  const isClinician = theme === 'clinician';

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] transition-colors',
        isClinician
          ? // Clinician — quiet ghost chip on cream. Soft hover lift,
            // sage focus ring on cream offset. ink-3 → ink-2 on hover.
            'border border-clinician-line bg-clinician-cream-card text-clinician-ink-3 hover:border-clinician-line-strong hover:bg-clinician-cream-2 hover:text-clinician-ink-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
          : // Legacy — original dark chrome.
            'border border-border-subtle bg-bg-surface-2/60 text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
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
