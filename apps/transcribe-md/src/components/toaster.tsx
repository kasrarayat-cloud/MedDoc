'use client';

import { Toaster as SonnerToaster } from 'sonner';

type ToasterTheme = 'legacy' | 'clinician';

/**
 * App-wide toast host. Mounted once in the root layout so any client
 * component can call `toast(...)` from `sonner` and land here. The
 * styling hooks into our design tokens via `className` + `unstyled` so
 * toasts match the rest of the app rather than sonner's default look.
 *
 * Theme — `'legacy'` (Sonner `theme="dark"`, glassy bg-surface-1/95
 * with subtle violet ring) or `'clinician'` (Sonner `theme="light"`,
 * cream-card surface, warm hairline, paper-on-desk shadow, sage/teal/
 * coral/amber accents on the success/info/error/warning borders).
 */
export function Toaster({ theme = 'legacy' }: { theme?: ToasterTheme } = {}) {
  if (theme === 'clinician') {
    return (
      <SonnerToaster
        position="bottom-right"
        theme="light"
        richColors={false}
        closeButton={false}
        duration={4000}
        visibleToasts={4}
        gap={8}
        toastOptions={{
          classNames: {
            toast: [
              'group',
              '!bg-clinician-cream-card',
              '!border !border-clinician-line',
              '!shadow-[0_8px_24px_rgba(43,38,32,0.06)]',
              '!rounded-xl !p-4',
              '!text-[14px] !text-clinician-ink',
              '!font-[var(--font-sans)]',
            ].join(' '),
            title: '!font-medium !text-clinician-ink',
            description: '!text-[13px] !text-clinician-ink-2',
            success: '!border-clinician-sage/40',
            error: '!border-clinician-coral/40',
            info: '!border-clinician-sky/40',
            warning: '!border-clinician-amber/40',
          },
        }}
      />
    );
  }

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
            '!bg-bg-surface-1/95 !backdrop-blur-xl',
            '!border !border-border-default',
            '!shadow-[0_16px_48px_-16px_rgba(0,0,0,0.8),0_0_0_1px_rgba(139,92,246,0.08)]',
            '!rounded-xl !p-4',
            '!text-[13px] !text-text-primary',
          ].join(' '),
          title: '!font-medium !text-text-primary',
          description: '!text-[12px] !text-text-tertiary',
          success: '!border-success/40',
          error: '!border-danger/40',
          info: '!border-violet-500/40',
          warning: '!border-warning/40',
        },
      }}
    />
  );
}
