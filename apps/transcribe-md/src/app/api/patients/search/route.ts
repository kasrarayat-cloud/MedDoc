// ============================================================================
// POST /api/patients/search — keep patient names out of access logs
// ----------------------------------------------------------------------------
// Security audit P1-C (2026-05-13): GET /api/patients?search=<name>
// puts the patient's name in the URL → Caddy access logs, browser
// history, Referer headers on outbound clicks, Sentry request URLs.
// Even though the endpoint is auth-gated, the URL surface is well
// outside the redactPhi posture, and HIPAA §164.502 minimum-necessary
// applies regardless of who's reading the logs.
//
// The fix moves the search term to a POST body. Auth + practice
// scoping + audit-log emit + rate-limit posture are identical to the
// GET handler at ../route.ts; only the term-transport changes.
//
// The legacy GET endpoint stays in place for backward compatibility
// with any internal tool that uses it; new client code (patient
// picker, dashboard) should use this POST surface.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { apiError, withApiHandler } from '@/lib/api-error';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Mirror the GET endpoint's constants — single SSOT for what
// "match" means here.
const SEARCH_SIMILARITY_THRESHOLD = 0.3;
const LIST_LIMIT = 500;

interface PatientListRow {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  externalId: string | null;
  createdAt: Date;
  visitCount: number;
  lastVisitAt: Date | null;
}

const BodySchema = z.object({
  search: z.string().trim().min(1, 'search is required').max(200),
});

export const POST = withApiHandler('api:patients:search', async (req) => {
  const session = await getSession();
  if (!session) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_READ, session.user.id);
  if (blocked) return blocked;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError('invalid JSON body', 400);
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    return NextResponse.json(
      { error: first?.message || 'invalid payload', field: first?.path.join('.') || 'search' },
      { status: 400 },
    );
  }
  const search = parsed.data.search;

  const rows = await prisma.$queryRaw<PatientListRow[]>`
    SELECT
      p.id,
      p.name,
      p."dateOfBirth",
      p."externalId",
      p."createdAt",
      COUNT(v.id)::int AS "visitCount",
      MAX(v."createdAt") AS "lastVisitAt"
    FROM transcribe_md_patients p
    LEFT JOIN transcribe_visits v ON v."patientId" = p.id
      AND v."deletedAt" IS NULL
      AND v."archivedAt" IS NULL
    WHERE p."practiceId" = ${session.user.practiceId}
      AND p."deletedAt" IS NULL
      AND (
        similarity(LOWER(p.name), LOWER(${search})) > ${SEARCH_SIMILARITY_THRESHOLD}
        OR p."externalId" ILIKE ${'%' + search + '%'}
      )
    GROUP BY p.id
    ORDER BY MAX(v."createdAt") DESC NULLS LAST, p.id DESC
    LIMIT ${LIST_LIMIT}
  `;

  // §164.312(b) PHI-read audit. Mirror the GET handler's metadata:
  // count + hasSearch boolean; never include the search term itself.
  void logAudit({
    action: 'VIEWED_PATIENT_LIST',
    targetType: 'TranscribeMdPatient',
    metadata: {
      source: 'api:POST /api/patients/search',
      count: rows.length,
      hasSearch: true,
    },
  });

  return NextResponse.json({ patients: rows });
});
