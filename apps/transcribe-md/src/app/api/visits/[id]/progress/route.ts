// ============================================================================
// GET /api/visits/[id]/progress (Gate 14 alias).
// ----------------------------------------------------------------------------
// HANDOFF §2.3 refers to a "progress" endpoint for the Processing
// screen; the actual endpoint was always /api/visits/[id]/status. This
// thin alias keeps both names valid so anything that grepped the
// handoff copy for the URL still works.
// ============================================================================

import { GET as statusGet } from '../status/route';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = statusGet;
