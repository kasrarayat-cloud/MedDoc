// ============================================================================
// /visits — all-visits list (Gate 16).
// ----------------------------------------------------------------------------
// AppFrame shell + filter chips + grouped VisitList. Filter state is
// URL-driven via ?filter=all|ready|review|signed|processing so a
// bookmark or middle-click preserves the selection. Matches the
// pattern used elsewhere in the redesign (Dashboard ?tab=, Patient
// ?tab=, Visit ?tab=).
//
// Phase 2 (Clinician remodel) — this route opts in to the Clinician
// chrome via `<AppFrame theme="clinician">` and threads
// `theme="clinician"` to PageHeader, EmptyState, and VisitList. The
// inline FilterBar + empty-message JSX is restyled in place rather
// than extracted (it's route-only, no other call sites).
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
      audioDurationSec: v.audioDurationSec,
    })
  );

  const hasAny = totalCount > 0;

  return (
    <AppFrame theme="clinician">
      <PageHeader
        theme="clinician"
        eyebrow="Visits"
        title={
          <>
            All{' '}
            <em
              style={{
                color: 'var(--sage-deep, #2F5040)',
                fontStyle: 'italic',
              }}
            >
              visits
            </em>
          </>
        }
        subtitle={
          hasAny
            ? `${totalCount} active visit${totalCount === 1 ? '' : 's'} · most recent first`
            : 'No visits yet — start one below.'
        }
        actions={
          <Link
            href="/visits/new"
            className="qm-cl-btn qm-cl-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        }
      />

      {!hasAny ? (
        <EmptyState
          theme="clinician"
          kind="stethoscope"
          eyebrow="No visits"
          title={
            <>
              No visits{' '}
              <em
                style={{
                  color: 'var(--sage-deep, #2F5040)',
                  fontStyle: 'italic',
                }}
              >
                yet
              </em>
            </>
          }
          body="Capture your first encounter — live recording, audio upload, or text."
          cta={
            <Link
              href="/visits/new"
              className="qm-cl-btn qm-cl-btn-primary"
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
                color: 'var(--ink-3, #8A8278)',
              }}
            >
              No visits match{' '}
              <strong style={{ color: 'var(--ink, #2B2620)' }}>
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
  // Filter chips render as `.qm-cl-tab-row` + `.qm-cl-tab` chips so the
  // active filter mirrors the visit-detail tab idiom (cream-card on
  // cream-2, sage-deep ink, paper button shadow).
  return (
    <div
      style={{
        padding: '4px 32px 0',
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
        alignItems: 'center',
      }}
    >
      <span className="qm-cl-eyebrow" style={{ marginRight: 8 }}>
        Filter
      </span>
      <div className="qm-cl-tab-row">
        {chips.map((c) => {
          const isActive = c.id === active;
          return (
            <Link
              key={c.id}
              href={c.href}
              scroll={false}
              className={`qm-cl-tab${isActive ? ' qm-cl-active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
              style={{
                textDecoration: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              {c.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
