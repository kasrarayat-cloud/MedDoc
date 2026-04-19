'use client';

import { ErrorFallback } from '@/components/error-fallback';

export default function SettingsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorFallback error={error} reset={reset} scope="settings" />;
}
