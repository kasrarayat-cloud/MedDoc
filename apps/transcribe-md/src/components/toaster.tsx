'use client';

import { Toaster as SonnerToaster } from 'sonner';

/**
 * App-wide toast host. Mounted once in the root layout so any client
 * component can call `toast(...)` from `sonner` and land here. The
 * styling hooks into our design tokens via `className` + `unstyled` so
 * toasts match the rest of the app rather than sonner's default look.
 */
export function Toaster() {
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
