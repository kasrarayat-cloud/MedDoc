// ============================================================================
// /visits — all-visits list (Gate 16).
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Filter pills row + grouped VisitList
// on the dark canvas. Filter state is URL-driven via
// ?filter=all|ready|review|signed|processing so a bookmark or
// middle-click preserves the selection.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { EmptyState } from '@/components/ui/empty-state';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
import {
  VisitList,
  type DashboardVisit,
} from '@/components/dashboard/visit-list';

export const metadata: Metadata = { title: 'Visits' };

type SearchParams = Record<string, string | string[] | undefined>;
type Filter = 'all' | 'ready' | 'review' | 'signed' | 'processing';

const PROCESSING: ReadonlyArray<TranscribeVisitStatus> = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

function resolveFilter(raw: string | undefined): Filter {
  if (raw === 'ready') return 'ready';
  if (raw === 'review') return 'review';
  if (raw === 'signed') return 'signed';
  if (raw === 'processing') return 'processing';
  return 'all';
}

const FILTER_LABEL: Record<Filter, string> = {
  all: 'All',
  ready: 'Ready',
  review: 'Needs review',
  signed: 'Signed',
  processing: 'Processing',
};

const PAGE_SIZE = 80;

export default async function VisitsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const sp = await searchParams;
  const filterParam = Array.isArray(sp.filter) ? sp.filter[0] : sp.filter;
  const filter = resolveFilter(filterParam);

  // Status-predicate for the active filter. All queries share the base
  // `userId + deletedAt:null + archivedAt:null` clause so any filter
  // stays scoped to non-trashed, non-archived visits.
  const statusFilter: import('@prisma/client').Prisma.TranscribeVisitWhereInput = (() => {
    switch (filter) {
      case 'ready':
        return { status: TranscribeVisitStatus.READY, needsReview: false };
      case 'review':
        return { status: TranscribeVisitStatus.READY, needsReview: true };
      case 'signed':
        return { status: TranscribeVisitStatus.SIGNED };
      case 'processing':
        return { status: { in: [...PROCESSING] } };
      case 'all':
      default:
        return {};
    }
  })();

  type VisitRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: TranscribeVisitStatus;
    needsReview: boolean;
    createdAt: Date;
    signedAt: Date | null;
    audioDurationSec: number | null;
    patient: { name: string } | null;
  };

  const [rows, totalCount] = (await Promise.all([
    prisma.transcribeVisit.findMany({
      where: {
        userId: session.user.id,
        deletedAt: null,
        archivedAt: null,
        ...statusFilter,
      },
      orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
      take: PAGE_SIZE,
      select: {
        id: true,
        patientName: true,
        specialty: true,
        status: true,
        needsReview: true,
        createdAt: true,
        signedAt: true,
        audioDurationSec: true,
        patient: { select: { name: true } },
      },
    }),
    prisma.transcribeVisit.count({
      where: {
        userId: session.user.id,
        deletedAt: null,
        archivedAt: null,
      },
    }),
  ])) as [VisitRow[], number];

  const visits: DashboardVisit[] = rows.map(
    (v: VisitRow): DashboardVisit => ({
      id: v.id,
      patientName: v.patient?.name ?? null,
      patientFallback: v.patientName ?? null,
      specialty: v.specialty,
      status: v.status,
      needsReview: v.needsReview,
      createdAt: v.createdAt.toISOString(),
      // Batch H: surfaces "Signed · {date}" pill on the visit-list row.
      signedAt: v.signedAt ? v.signedAt.toISOString() : null,
      audioDurationSec: v.audioDurationSec,
    })
  );

  const hasAny = totalCount > 0;

  return (
    <AppFrame>
      <PageHeader
        eyebrow="Visits"
        title="All visits"
        subtitle={
          hasAny
            ? `${totalCount} active visit${totalCount === 1 ? '' : 's'} · most recent first`
            : 'No visits yet — start one below.'
        }
        actions={
          <Link
            href="/visits/new"
            className="qm-lin-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        }
      />

      {!hasAny ? (
        <EmptyState
          kind="stethoscope"
          eyebrow="No visits"
          title="No visits yet"
          body="Capture your first encounter — live recording, audio upload, or text."
          cta={
            <Link
              href="/visits/new"
              className="qm-lin-btn-primary"
              style={{ textDecoration: 'none' }}
            >
              <Ic.plus width={14} height={14} />
              Start a visit
            </Link>
          }
        />
      ) : (
        <>
          <FilterBar active={filter} />
          {visits.length === 0 ? (
            <div
              style={{
                margin: '40px auto',
                maxWidth: 420,
                textAlign: 'center',
                fontSize: 13,
                color: 'var(--color-linear-text-3)',
              }}
            >
              No visits match{' '}
              <strong style={{ color: 'var(--color-linear-text)' }}>
                {FILTER_LABEL[filter]}
              </strong>
              .
            </div>
          ) : (
            <VisitList visits={visits} theme="clinician" />
          )}
        </>
      )}
    </AppFrame>
  );
}

function FilterBar({ active }: { active: Filter }) {
  const chips: { id: Filter; label: string; href: string }[] = [
    { id: 'all', label: 'All', href: '/visits' },
    { id: 'ready', label: 'Ready', href: '/visits?filter=ready' },
    { id: 'review', label: 'Needs review', href: '/visits?filter=review' },
    { id: 'signed', label: 'Signed', href: '/visits?filter=signed' },
    {
      id: 'processing',
      label: 'Processing',
      href: '/visits?filter=processing',
    },
  ];
  // Linear V1 filter chips: each pill is a standard `.qm-lin-pill` on
  // the surface-2 background, with the active filter swapped to a sage
  // tint via `.qm-lin-pill--sage`.
  return (
    <div
      style={{
        padding: '14px 24px 4px',
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        alignItems: 'center',
        borderBottom: '1px solid var(--color-linear-hairline)',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          fontWeight: 500,
          letterSpacing: '0.07em',
          textTransform: 'uppercase',
          color: 'var(--color-linear-text-3)',
          marginRight: 4,
        }}
      >
        Filter
      </span>
      {chips.map((c) => {
        const isActive = c.id === active;
        return (
          <Link
            key={c.id}
            href={c.href}
            scroll={false}
            className={
              isActive
                ? 'qm-lin-pill qm-lin-pill--sage qm-tap-44'
                : 'qm-lin-pill qm-tap-44'
            }
            aria-current={isActive ? 'page' : undefined}
            style={{
              textDecoration: 'none',
              cursor: 'pointer',
            }}
          >
            {c.label}
          </Link>
        );
      })}
    </div>
  );
}
