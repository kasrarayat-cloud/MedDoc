// ============================================================================
// Platform-admin home — Phase 1A placeholder
// ----------------------------------------------------------------------------
// The SUPER_ADMIN gate lives in layout.tsx. This page exists purely to
// prove end-to-end that the gate resolves: kasra → sees this text;
// qa-bundle / logged-out → 404.
// Phase 1B will replace this with the real admin dashboard shell.
// ============================================================================

import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Admin' };

export default function AdminHomePage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24 text-center">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
        § Admin / home
      </p>
      <h1 className="text-3xl font-bold">Admin Dashboard</h1>
      <p className="mt-4 text-[14px] text-slate-400">
        Phase 1B APIs coming soon.
      </p>
    </div>
  );
}
