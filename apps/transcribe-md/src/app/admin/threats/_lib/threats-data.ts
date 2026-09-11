// ============================================================================
// /admin/threats — SSR seed
// ----------------------------------------------------------------------------
// Shells out to the dashboard data layer so detector logic + resolution
// filtering stay defined in one place. We fetch active + last-7d
// resolved in parallel; the client orchestrator can switch the
// resolved window later via the /api/admin/threats/history endpoint.
// ============================================================================

import 'server-only';

import { assertSuperAdminCaller } from '@/app/admin/_lib/admin-gate';

import { getThreats, getResolvedThreats } from '../../_lib/dashboard-data';
import type { AdminThreatsInitialData } from '../_types';

export async function getThreatsPageData(): Promise<AdminThreatsInitialData> {
  await assertSuperAdminCaller();
  const [active, resolved] = await Promise.all([
    getThreats(),
    getResolvedThreats('7d'),
  ]);
  return { active, resolved };
}
