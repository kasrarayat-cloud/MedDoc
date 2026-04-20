// ============================================================================
// /api/patients — list + create (T-M17.2 Phase 2 Commit 4)
// ----------------------------------------------------------------------------
// GET  returns every non-soft-deleted TranscribeMdPatient for the caller's
//      practice, decorated with visit count + last-visit-at. Optional
//      `search` query hits the pg_trgm index on LOWER(name) and an ILIKE
//      on externalId. Sorted last-visit-desc (NULLS LAST, id DESC).
//
// POST creates a new patient. DOB is required at the API layer — the
//      match-or-create path used by the new-visit server action
//      (Commit 6) skips this route and writes via Prisma directly, so
//      legacy visits without DOB still work without loosening the API
//      contract.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { apiError, withApiHandler } from '@/lib/api-error';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Trigram similarity threshold — matches the fuzzy-match endpoint's
// default. Only used for the list-search path; exact externalId
// matches still surface via the ILIKE fallback below.
const SEARCH_SIMILARITY_THRESHOLD = 0.3;

// Hard cap — the dashboard is paginated separately (Phase 3 Commit 7).
// For the API surface, 500 is enough headroom that a legitimate UI
// listing never hits it, and it bounds the response size for a
// pathological caller.
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

export const GET = withApiHandler('api:patients:list', async (req) => {
  const session = await getSession();
  if (!session) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
  if (blocked) return blocked;

  const url = new URL(req.url);
  const rawSearch = url.searchParams.get('search');
  const search =
    rawSearch && rawSearch.trim().length > 0 ? rawSearch.trim() : null;

  // Raw SQL so the per-patient visit count + last-visit timestamp
  // aggregate lands in one query and the server-side sort on the
  // aggregate column is correct. Prisma's groupBy can't express
  // "LEFT JOIN, aggregate, ORDER BY aggregated column" in one shot.
  const rows = search
    ? await prisma.$queryRaw<PatientListRow[]>`
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
      `
    : await prisma.$queryRaw<PatientListRow[]>`
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
        GROUP BY p.id
        ORDER BY MAX(v."createdAt") DESC NULLS LAST, p.id DESC
        LIMIT ${LIST_LIMIT}
      `;

  return NextResponse.json({ patients: rows });
});

const CreateBodySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(200),
  /** Accept an ISO-8601 date (YYYY-MM-DD) or a full datetime. Either
   *  way we coerce through `new Date()` and store at midnight — the DB
   *  column is DATE, so any time portion is truncated server-side. */
  dateOfBirth: z
    .string()
    .min(1, 'Date of birth is required')
    .refine((s) => !Number.isNaN(Date.parse(s)), {
      message: 'Invalid date',
    }),
  externalId: z
    .string()
    .trim()
    .max(100)
    .optional()
    .transform((v) => (v && v.length > 0 ? v : null))
    .nullable(),
});

export const POST = withApiHandler('api:patients:create', async (req) => {
  const session = await getSession();
  if (!session) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
  if (blocked) return blocked;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return apiError('invalid JSON body', 400);
  }
  const parsed = CreateBodySchema.safeParse(body);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    const field = first?.path.join('.') || '_form';
    return NextResponse.json(
      { error: first?.message || 'invalid payload', field },
      { status: 400 }
    );
  }

  const patient = await prisma.transcribeMdPatient.create({
    data: {
      practiceId: session.user.practiceId,
      name: parsed.data.name,
      dateOfBirth: new Date(parsed.data.dateOfBirth),
      externalId: parsed.data.externalId,
    },
    select: {
      id: true,
      name: true,
      dateOfBirth: true,
      externalId: true,
      createdAt: true,
    },
  });

  return NextResponse.json({ patient }, { status: 201 });
});
