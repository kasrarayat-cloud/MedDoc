// ============================================================================
// POST /api/patients/fuzzy-match (T-M17.2 Phase 2 Commit 5)
// ----------------------------------------------------------------------------
// Inputs:
//   { name: string, dateOfBirth?: ISO date string }
//
// Returns the top 5 candidate TranscribeMdPatient rows for the caller's
// practice with similarity > 0.4, plus a `dobMatches` boolean per row
// when the caller supplied a DOB.
//
// The fuzzy-match score is pg_trgm's `similarity()` — not the rank from
// the GIN index — so the result ordering is exact, not approximate.
// Score range [0.4, 1]; 1 = identical after case-fold.
//
// Powers:
//   - New-visit picker "Create new patient → did you mean…?" modal
//   - Duplicate-guard in the inline create flow (Phase 3 Commit 9)
//
// Scope: excludes soft-deleted patients. Rate limit reused from the
// CRUD endpoints since this is called right next to them in the UI.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { apiError, withApiHandler } from '@/lib/api-error';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Minimum similarity to surface a candidate. Picked by eyeball against
// the backfill data — 0.4 catches "Kasra" / "kAsra" / "Kasratest" as
// candidates for "kasra" while excluding unrelated names like "Bobby".
// Raise if false positives become a problem; lower if near-misses get
// dropped.
const MIN_SIMILARITY = 0.4;

// Top-N shown in the duplicate modal. Small so the UI stays simple;
// anyone scrolling past the 5th candidate probably meant to create a
// new patient anyway.
const MAX_RESULTS = 5;

const BodySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(200),
  dateOfBirth: z
    .string()
    .min(1)
    .refine((s) => !Number.isNaN(Date.parse(s)), { message: 'Invalid date' })
    .optional(),
});

interface MatchRow {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  externalId: string | null;
  score: number;
}

export const POST = withApiHandler('api:patients:fuzzy-match', async (req) => {
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
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    const first = parsed.error.issues[0];
    const field = first?.path.join('.') || '_form';
    return NextResponse.json(
      { error: first?.message || 'invalid payload', field },
      { status: 400 }
    );
  }

  const rows = await prisma.$queryRaw<MatchRow[]>`
    SELECT
      id,
      name,
      "dateOfBirth",
      "externalId",
      similarity(LOWER(name), LOWER(${parsed.data.name})) AS score
    FROM transcribe_md_patients
    WHERE "practiceId" = ${session.user.practiceId}
      AND "deletedAt" IS NULL
      AND similarity(LOWER(name), LOWER(${parsed.data.name})) > ${MIN_SIMILARITY}
    ORDER BY score DESC, name ASC
    LIMIT ${MAX_RESULTS}
  `;

  const dobInput = parsed.data.dateOfBirth
    ? new Date(parsed.data.dateOfBirth)
    : null;

  const matches = rows.map((r: MatchRow) => {
    // DOB matches iff both the row's DOB and the input DOB are non-null
    // and fall on the same calendar day (UTC). We don't boost the
    // score here — the client surfaces `dobMatches` as a separate
    // "same DOB" chip and the doctor confirms visually, which is
    // clearer than a mystery-boosted similarity number.
    let dobMatches: boolean | null = null;
    if (dobInput !== null) {
      dobMatches =
        r.dateOfBirth !== null &&
        r.dateOfBirth.toISOString().slice(0, 10) ===
          dobInput.toISOString().slice(0, 10);
    }
    return {
      patient: {
        id: r.id,
        name: r.name,
        dateOfBirth: r.dateOfBirth,
        externalId: r.externalId,
      },
      score: Number(r.score.toFixed(3)),
      dobMatches,
    };
  });

  return NextResponse.json({ matches });
});
