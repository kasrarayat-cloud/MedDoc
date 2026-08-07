// ============================================================================
// /patients — all-patients list (Gate 16).
// ----------------------------------------------------------------------------
// AppFrame shell + the Rounds patients roster. The dashboard shows a
// truncated first-page view of the same data; this route is the exhaustive
// list, sorted by updatedAt so doctors see their most-recently-touched
// charts first.
//
// The roster is served by a READ-ONLY server search + cursor pagination
// (searchPatientsAction), so it scales past a fixed client-side row cap.
// The page-level data fetches (prisma queries, redirects) are unchanged per
// PROTECTED_CONTRACTS.md. The auth read moved to `getSession()` in F-TYPE —
// see the note above the component; the roster's own paging actions were
// already on it.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { patientScope, visitScope } from '@/lib/practice-scope';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { AppFrame } from '@/components/ui/app-frame';
import { RoundsPatientsRoster } from '@/components/rounds/patients-roster';
import {
  C3_PATIENTS_PAGE_SIZE,
  type C3PatientsCursor,
  type C3PatientRow,
} from '@/lib/c3-list-pagination';

export const metadata: Metadata = { title: 'Patients' };

// ⚠️ F-TYPE 2026-08-07 — THE PRACTICE ID COMES FROM `getSession()`, NOT FROM A
// HAND-ROLLED USER LOOKUP.
//
// This page used to call `auth()` and then re-read `prisma.user.findUnique(...,
// { select: { practiceId: true } })` itself, handing that plain `string` to
// `patientScope()`/`visitScope()`. With the shared Prisma client typed, that is
// three TS2345s: `PracticeId` is a brand, and a brand is minted at exactly one
// place — the session boundary in `lib/auth.ts`.
//
// The value WAS correct at runtime (a practice id read off the signed-in user's
// own row), so the honest fix is to source it from the mint point rather than
// cast a string into the brand — a cast here would restore precisely the silence
// the brand exists to break, and `gate-practice-scope` bans it by name.
//
// `getSession()` performs the SAME single `prisma.user.findUnique` on the
// session user, so this is not an extra round trip; it selects `isActive` and
// `role` alongside `practiceId` and fails closed on a revoked account. It is
// also what `searchPatientsAction`/`loadMorePatientsAction` — the actions that
// page THIS roster forward — already use, and what the sibling
// `/patients/[id]` page uses. This page was the outlier.
export default async function PatientsPage() {
  const session = await getSession();
  if (!session) redirect('/login');
  const practiceId = session.user.practiceId;

  // ── The scaling roster ────────────────────────────────────────────────────
  // One practice-scoped read serves the page: the same VIEWED_PATIENT_LIST
  // audit row, and a cursor the roster pages forward from.
  type C3PatientRaw = {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    updatedAt: Date;
    transcribeVisits: Array<{
      createdAt: Date;
      specialty: string;
      status: import('@prisma/client').TranscribeVisitStatus;
      needsReview: boolean;
      signedAt: Date | null;
    }>;
  };
  const [firstRaw, total] = (await Promise.all([
    prisma.transcribeMdPatient.findMany({
      where: { ...patientScope(practiceId), deletedAt: null },
      orderBy: [{ updatedAt: 'desc' }, { id: 'desc' }],
      take: C3_PATIENTS_PAGE_SIZE + 1,
      select: {
        id: true,
        name: true,
        dateOfBirth: true,
        updatedAt: true,
        transcribeVisits: {
          where: { deletedAt: null, archivedAt: null },
          orderBy: { createdAt: 'desc' },
          take: 1,
          select: {
            createdAt: true,
            specialty: true,
            status: true,
            needsReview: true,
            signedAt: true,
          },
        },
      },
    }),
    prisma.transcribeMdPatient.count({
      where: { ...patientScope(practiceId), deletedAt: null },
    }),
  ])) as [C3PatientRaw[], number];

  void logAudit({
    action: 'VIEWED_PATIENT_LIST',
    targetType: 'TranscribeMdPatient',
    metadata: {
      source: 'rsc:/patients:rounds',
      count: Math.min(firstRaw.length, C3_PATIENTS_PAGE_SIZE),
    },
  });

  const hasMore = firstRaw.length > C3_PATIENTS_PAGE_SIZE;
  const firstPage = hasMore ? firstRaw.slice(0, C3_PATIENTS_PAGE_SIZE) : firstRaw;
  const ids = firstPage.map((p) => p.id);
  const counts = ids.length
    ? await prisma.transcribeVisit.groupBy({
        by: ['patientId'],
        // The ids come from a practice-scoped patient page, but the count
        // gets its OWN predicate: inheriting scope from an upstream query is
        // exactly the assumption T5 exists to stop relying on.
        where: {
          patientId: { in: ids },
          ...visitScope(practiceId),
          deletedAt: null,
          archivedAt: null,
        },
        _count: { _all: true },
      })
    : [];
  const countBy = new Map<string, number>(
    counts.map((c: { patientId: string; _count: { _all: number } }) => [
      c.patientId,
      c._count._all,
    ])
  );
  const firstRows: C3PatientRow[] = firstPage.map((p) => {
    const lv = p.transcribeVisits[0];
    return {
      id: p.id,
      name: p.name,
      dateOfBirth: p.dateOfBirth ? p.dateOfBirth.toISOString().slice(0, 10) : null,
      visitCount: countBy.get(p.id) ?? 0,
      lastVisitAt: lv?.createdAt.toISOString() ?? null,
      lastVisitSpecialty: lv?.specialty ?? null,
      lastVisitStatus: lv?.status ?? null,
      lastVisitNeedsReview: lv?.needsReview ?? false,
      lastVisitSignedAt: lv?.signedAt ? lv.signedAt.toISOString() : null,
    };
  });
  const last = firstPage[firstPage.length - 1];
  const firstCursor: C3PatientsCursor | null =
    hasMore && last ? { updatedAt: last.updatedAt.toISOString(), id: last.id } : null;

  // The roster draws its own header (title, count, New visit) and its own
  // empty state, so nothing else is rendered above it here.
  return (
    <AppFrame>
      <RoundsPatientsRoster
        initialRows={firstRows}
        initialCursor={firstCursor}
        total={total}
      />
    </AppFrame>
  );
}
