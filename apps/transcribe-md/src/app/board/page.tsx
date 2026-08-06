// ============================================================================
// ROUNDS — Screen 1, the Board route.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md, Screen 1. The component is components/rounds/board.tsx;
// this file is the server half: query the real queue, map through the row
// model, and hand over `BoardLane[]`.
//
// SEARCH AND PAGINATION SURVIVE. The spec is explicit that "the designs' bans
// lose to shipped features", so the search predicate here is the SAME one
// searchInboxAction already ships (patient.name / patientName / chiefComplaint,
// case-insensitive, 100-char cap) and the paging is the same shape /visits
// uses. They are reproduced rather than imported because that action is scoped
// to the READY inbox and the board is whole-queue — copying the predicate keeps
// the two honest about being the same search without pretending the scopes are
// the same.
//
// UNCONDITIONAL since F-ret.3 (2026-08-05). This route used to fail closed —
// `notFound()` before `auth()`, so with the skin flag off it did not exist and
// nothing could link here. The flag and its OFF arm are gone, so the guard has
// nothing left to protect against and was removed with them. `/board` is now
// simply the home surface.
//
// The guard's removal is what allowed `lib/recovery-href.ts` to collapse from a
// fork to a constant: every recovery affordance can point here now without the
// risk of sending a doctor from one 404 to another.
//
// PHI-read audit: an RSC reading visit rows IS a doctor seeing the queue, and
// §164.312(b) wants that recorded — same as /visits does.
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { visitScope } from '@/lib/practice-scope';
import type { Prisma } from '@prisma/client';

import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { emAppliesToSpecialty } from '@meddoc/shared/specialties';
import {
  laneMatchesFilter,
  sortLanes,
  toBoardLane,
  dayProgress,
  type BoardFilter,
  type BoardLane,
} from '@/lib/rounds/board-data';
import { RoundsBoard } from '@/components/rounds/board';
import { RoundsBoardChrome } from '@/components/rounds/board-chrome';

export const metadata: Metadata = { title: 'Board' };

const PAGE_SIZE = 20;
/** Same cap searchInboxAction uses. A longer query is not a better one, and an
 *  unbounded LIKE against a PHI column is not a thing to leave open. */
const QUERY_MAX = 100;

const FILTERS: BoardFilter[] = [
  'active',
  'ready',
  'signed',
  'soap',
  'ultrasound',
  'critical',
  'failed',
];

function resolveFilter(raw: string | undefined): BoardFilter {
  return FILTERS.includes(raw as BoardFilter) ? (raw as BoardFilter) : 'active';
}

type SearchParams = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined): string | undefined =>
  Array.isArray(v) ? v[0] : v;

export default async function BoardPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const sp = await searchParams;
  const filter = resolveFilter(one(sp.filter));
  const q = (one(sp.q) ?? '').trim().slice(0, QUERY_MAX);
  const page = Math.max(1, Number(one(sp.page) ?? '1') || 1);

  const where: Prisma.TranscribeVisitWhereInput = {
    // ⚠️ T5 — THE BOARD IS THE PRACTICE'S DAY NOW (§4.1b). This read was
    // `userId: session.user.id` until 2026-08-06, which made the Ward Board a
    // solo inbox wearing a ward's name. The count below shares this const, so
    // the list and its total can never disagree about scope.
    ...visitScope(session.user.practiceId),
    deletedAt: null,
    archivedAt: null,
    ...(q
      ? {
          OR: [
            { patient: { is: { name: { contains: q, mode: 'insensitive' } } } },
            { patientName: { contains: q, mode: 'insensitive' } },
            { chiefComplaint: { contains: q, mode: 'insensitive' } },
          ],
        }
      : {}),
  };

  const [rows, totalCount] = await Promise.all([
    prisma.transcribeVisit.findMany({
      where,
      orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
      skip: (page - 1) * PAGE_SIZE,
      take: PAGE_SIZE,
      select: {
        id: true,
        patientName: true,
        specialty: true,
        status: true,
        createdAt: true,
        signedAt: true,
        audioDurationSec: true,
        // The board's critical treatment derives from real warnings — see
        // criticalWarningsOf(). Selected here so the lane never has to guess.
        rxDrafts: true,
        patient: { select: { name: true } },
      },
    }),
    prisma.transcribeVisit.count({ where }),
  ]);

  void logAudit({
    action: 'VIEWED_VISIT_LIST',
    targetType: 'TranscribeVisit',
    metadata: {
      source: 'rsc:/board',
      filter,
      // The QUERY ITSELF is not logged — a doctor searching a patient's name
      // would write that name into the audit metadata, which is the one place
      // the contract says never to put raw PHI. Length only.
      queryLength: q.length,
      count: rows.length,
      totalCount,
    },
  });

  // Derived from the ONE switch, never re-typed from its parts. The first cut
  // of this file open-coded the imaging conjunction by hand and the source
  // guard in review-read-only-paper.test.ts caught it — that hand-copying is
  // exactly how the specialtyLabel-vs-specialtyId defect ended up with seven
  // call sites, one of which compared a display label against an id and so was
  // silently, permanently false.
  //
  // (Note this comment does not quote the banned expression: the guard is a
  // source grep, so an explanatory comment containing it trips the guard on
  // itself. Same lesson as the last time.)
  //
  // "Imaging" and "E/M does not apply" are the same predicate. Saying it once
  // means the board's Ultrasound filter cannot drift from the E/M gate.
  const isImaging = (s: string) => !emAppliesToSpecialty(s);

  type BoardRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: string;
    createdAt: Date;
    signedAt: Date | null;
    audioDurationSec: number | null;
    rxDrafts: unknown;
    patient: { name: string } | null;
  };

  const allLanes: BoardLane[] = (rows as BoardRow[]).map((v) =>
    toBoardLane({
      id: v.id,
      patientName: v.patient?.name ?? null,
      patientFallback: v.patientName ?? null,
      specialty: v.specialty,
      status: v.status,
      createdAt: v.createdAt.toISOString(),
      signedAt: v.signedAt?.toISOString() ?? null,
      audioDurationSec: v.audioDurationSec,
      rxDrafts: v.rxDrafts,
    }),
  );

  const lanes = sortLanes(
    allLanes.filter((l) => laneMatchesFilter(l, filter, isImaging)),
  );
  const progress = dayProgress(allLanes);
  const criticalTally = allLanes.filter((l) => l.criticalCount > 0).length;
  const nextReview = lanes.find((l) => l.kind === 'ready') ?? null;

  return (
    <RoundsBoardChrome
      clinicianName={session.user.name ?? session.user.email ?? 'Clinician'}
      progress={progress}
      criticalTally={criticalTally}
      filter={filter}
      query={q}
      page={page}
      pageSize={PAGE_SIZE}
      totalCount={totalCount}
      nextReviewHref={nextReview ? `/visits/${nextReview.id}` : null}
      shownCount={lanes.length}
    >
      <RoundsBoard lanes={lanes} />
    </RoundsBoardChrome>
  );
}
