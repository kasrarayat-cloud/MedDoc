'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

export function BackToDashboardLink() {
  const router = useRouter();
  return (
    <a
      href="/dashboard"
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        router.push('/dashboard');
      }}
      className="relative z-10 inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Back to dashboard
    </a>
  );
}
