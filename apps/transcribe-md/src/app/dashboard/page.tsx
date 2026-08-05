// ============================================================================
// /dashboard — a FORWARD, not a page.
// ----------------------------------------------------------------------------
// REDUCED FROM 753 LINES TO THIS 2026-08-05 (F-ret.3). What stood here was the
// Phase 5 "Linear V1" dashboard — greeting, stats row, tab nav, the Patients /
// All-visits tabs and a SKIN_BETA fork between `DashboardC3Body` and the older
// `DashboardBody`. All of it sat BELOW `if (isSkinRounds()) redirect('/board')`,
// so from the 2026-08-02 flip onward not one line of it ran in production. This
// change deletes code that had already stopped executing; it does not remove a
// behaviour.
//
// ⚠️ THE PROOF THAT IT HAD STOPPED, because "unreachable" deserves evidence
// rather than an argument. The old body wrote a §164.312(b) access row —
// `logAudit({ action: 'VIEWED_DASHBOARD' })`, which closed finding F-09. In
// production:
//
//     VIEWED_DASHBOARD    2361 rows   2026-05-06 → 2026-08-03
//     VIEWED_VISIT_LIST    301 rows   2026-08-02 → 2026-08-05 (current)
//
// The row stopped at the flip and `/board`'s own access row took over, with a
// one-day overlap. So the audit obligation MOVED with the home page — it was
// not dropped here, and F-09 stays closed by its successor. That query is the
// reason this deletion is safe to make; without it, removing an audit row would
// be a compliance change wearing a refactor's clothes.
//
// ⚠️ THIS FORWARD IS A BACKSTOP, AND IT CANNOT BE THE PRIMARY ONE.
// `dashboard/loading.tsx` wraps this segment in Suspense, so a `redirect()`
// thrown here AFTER ANY AWAIT — including `await searchParams` — is delivered
// as a streamed 200 + skeleton instead of a 307. That is why this function now
// takes NO parameters: reading them is precisely what suspends. The real
// forward is `next.config.ts`'s `redirects()`, which also owns the
// `?tab=all` → `/board?filter=active` deep-link mapping that has no counterpart
// here. This exists only for the case where that config is ever removed, and
// then it still forwards — just less well.
//
// Orphaned by this deletion and removed with it: `components/dashboard/`'s
// `dashboard-c3.tsx`, `dashboard-inbox-c3.tsx` and `greeting.tsx`, each
// imported by nothing else. KEPT, because live surfaces still import them:
// `visit-list.tsx` (`/visits`, `/patients/[id]`) and `stat-card.tsx`
// (`/patients/[id]`). A hand-kept deletion list would very likely have taken
// those two along with the rest; the import census is what stopped it.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = { title: 'Dashboard' };

export default async function DashboardPage() {
  redirect('/board');
}
