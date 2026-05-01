'use client';

import { Toaster as SonnerToaster } from 'sonner';

type ToasterTheme = 'legacy' | 'clinician';

/**
 * Phase 5 — Linear V1 Faithful toast host.
 *
 * Reference: docs/design-directions-v8-linear/dashboard-v1.html (chrome
 * tokens). Mounted once in the root layout so any client component can
 * call `toast(...)` from `sonner` and land here.
 *
 * Linear V1 toasts: dark surface (linear-surface-1), hairline border,
 * Inter sans, 8px radius. Status meanings:
 *   success → sage border (linear-sage)
 *   error   → coral/danger border (linear-coral)
 *   warning → amber border (linear-amber)
 *   info    → sky border (linear-info)
 *
 * The legacy `theme` prop remains in the type signature for back-compat
 * with unmigrated callers; both values render the single Linear V1 dark
 * variant. Stage 5 cleanup will drop the prop in one sweep.
 */
export function Toaster({ theme: _theme = 'legacy' }: { theme?: ToasterTheme } = {}) {
  return (
    <SonnerToaster
      position="bottom-right"
      theme="dark"
      richColors={false}
      closeButton={false}
      duration={4000}
      visibleToasts={4}
      gap={8}
      toastOptions={{
        classNames: {
          toast: [
            'group',
            '!bg-linear-surface-1',
            '!border !border-linear-border',
            '!shadow-[0_16px_48px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.03)]',
            '!rounded-lg !p-4',
            '!text-[13px] !text-linear-text',
            '!font-[var(--font-sans)]',
          ].join(' '),
          title: '!font-medium !text-linear-text',
          description: '!text-[12px] !text-linear-text-2',
          success: '!border-linear-sage/40',
          error: '!border-linear-coral/50',
          info: '!border-linear-info/40',
          warning: '!border-linear-amber/40',
        },
      }}
    />
  );
}
