// ============================================================================
// GET /api/admin/threats — Phase 6H active-threats list
// ----------------------------------------------------------------------------
// Thin wrapper around `getThreats()` from the dashboard data layer so
// the /admin/threats client page can refresh after a Resolve/Dismiss
// action without a full SSR round-trip. Same detector logic; same
// resolution+silencePattern filtering.
// ============================================================================

import { NextResponse } from 'next/server';

import { adminApi } from '@/lib/admin-api-gate';
import { getThreats } from '@/app/admin/_lib/dashboard-data';

export const dynamic = 'force-dynamic';

export const GET = adminApi('threats:list', async () => {
  const threats = await getThreats();
  return NextResponse.json({ threats });
});
