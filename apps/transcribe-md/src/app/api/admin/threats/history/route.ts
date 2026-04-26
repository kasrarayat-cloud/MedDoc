// ============================================================================
// GET /api/admin/threats/history?window=7d|30d — Phase 6H resolved threats
// ----------------------------------------------------------------------------
// Surfaces ThreatResolution rows joined with the live detector output
// so the UI can render Active / Resolved / False-positive tabs from a
// single data source.
// ============================================================================

import { NextResponse } from 'next/server';

import { adminApi } from '@/lib/admin-api-gate';
import { getResolvedThreats } from '@/app/admin/_lib/dashboard-data';

export const dynamic = 'force-dynamic';

export const GET = adminApi('threats:history', async (req) => {
  const url = new URL(req.url);
  const w = url.searchParams.get('window');
  const window: '7d' | '30d' = w === '30d' ? '30d' : '7d';
  const threats = await getResolvedThreats(window);
  return NextResponse.json({ window, threats });
});
