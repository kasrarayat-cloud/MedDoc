// ============================================================================
// Dashboard — app-redesign-v1 (HANDOFF §2.2).
// ----------------------------------------------------------------------------
// /dashboard                → Patients tab (default)
// /dashboard?tab=all        → All visits tab (grouped by day)
//
// This is the first screen that mounts the new shell chrome — wraps
// in <AppFrame> which owns TopNav + IconRail + the scrollable main
// per §8.2. Stats + tab content run in parallel inside the same
// server component; the page is re-rendered on tab change via Link.
//
// The previous T-M18.2 "Trash" tab + archived toggle are not ported
// yet — the new dashboard is deliberately two-tab per the redesign
// brief. Global trash stays recoverable via /patients/[id] pages.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
import { StatCard } from '@/components/dashboard/stat-card';
import {
  PatientCard,
  type DashboardPatient,
} from '@/components/dashboard/patient-card';
import {
  VisitList,
  type DashboardVisit,
} from '@/components/dashboard/visit-list';

export const metadata: Metadata = { title: 'Dashboard' };

type SearchParams = Record<string, string | string[] | undefined>;
type ActiveTab = 'patients' | 'all';

const PATIENTS_PAGE_SIZE = 20;
const VISITS_PAGE_SIZE = 20;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { practiceId: true },
  });
  if (!user) redirect('/login');

  const params = await searchParams;
  const tabRaw = Array.isArray(params.tab) ? params.tab[0] : params.tab;
  const activeTab: ActiveTab = tabRaw === 'all' ? 'all' : 'patients';

  return (
    <AppFrame>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardBody
          userId={session.user.id}
          practiceId={user.practiceId}
          activeTab={activeTab}
        />
      </Suspense>
    </AppFrame>
  );
}

async function DashboardBody({
  userId,
  practiceId,
  activeTab,
}: {
  userId: string;
  practiceId: string;
  activeTab: ActiveTab;
}) {
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const startOfWeek = (() => {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    const dow = d.getDay();
    const diff = dow === 0 ? -6 : 1 - dow;
    d.setDate(d.getDate() + diff);
    return d;
  })();

  // Parallel stats queries. All scoped to the authed user — no cross-
  // tenant leakage possible because userId is from the session.
  const [
    visitsThisMonth,
    avgDraftedAgg,
    pendingReview,
    signedThisWeek,
    patientCount,
    activeVisitCount,
  ] = await Promise.all([
    prisma.transcribeVisit.count({
      where: {
        userId,
        deletedAt: null,
        createdAt: { gte: startOfMonth },
      },
    }),
    prisma.transcribeVisit.aggregate({
      where: {
        userId,
        deletedAt: null,
        draftedInSeconds: { not: null },
      },
      _avg: { draftedInSeconds: true },
    }),
    prisma.transcribeVisit.count({
      where: {
        userId,
        deletedAt: null,
        archivedAt: null,
        status: TranscribeVisitStatus.READY,
        needsReview: true,
      },
    }),
    prisma.transcribeVisit.count({
      where: {
        userId,
        status: TranscribeVisitStatus.SIGNED,
        signedAt: { gte: startOfWeek },
      },
    }),
    prisma.transcribeMdPatient.count({
      where: { practiceId, deletedAt: null },
    }),
    prisma.transcribeVisit.count({
      where: { userId, deletedAt: null, archivedAt: null },
    }),
  ]);

  const avgDraftedSec = avgDraftedAgg._avg.draftedInSeconds;
  const avgDraftedMin = avgDraftedSec != null ? Math.round(avgDraftedSec / 60) : null;

  // Brand-new account (no data yet) — first-session orb was the old
  // empty state; here we fall through to the patients empty-state
  // below. Stats row stays at zero so the doctor can see the scaffold
  // before it fills in.

  return (
    <>
      <PageHeader
        eyebrow="§ Home / Today"
        title={
          <>
            Your <em style={{ color: 'var(--accent-bright)' }}>workspace</em>.
          </>
        }
        subtitle={
          <>
            {patientCount} patient{patientCount === 1 ? '' : 's'} ·{' '}
            {activeVisitCount} total visit
            {activeVisitCount === 1 ? '' : 's'}
            {pendingReview > 0 && (
              <>
                {' · '}
                <span style={{ color: 'var(--amber)' }}>
                  {pendingReview} awaiting your review
                </span>
              </>
            )}
          </>
        }
        actions={
          <Link
            href="/visits/new"
            className="qm-btn qm-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        }
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          padding: '0 32px 18px',
        }}
      >
        <StatCard
          label={`§ Visits / ${now.toLocaleString('en-US', { month: 'short' })}`}
          value={visitsThisMonth}
          unit="this month"
        />
        <StatCard
          label="§ Avg drafted in"
          value={avgDraftedMin != null ? avgDraftedMin : '—'}
          unit={avgDraftedMin != null ? 'min / visit' : 'no data yet'}
        />
        <StatCard
          label="§ Pending review"
          value={pendingReview}
          unit={pendingReview === 1 ? 'visit' : 'visits'}
          deltaTone={pendingReview > 0 ? 'amber' : 'mint'}
        />
        <StatCard
          label="§ Signed this week"
          value={signedThisWeek}
          unit={signedThisWeek === 1 ? 'note' : 'notes'}
        />
      </div>

      <TabBar activeTab={activeTab} patientCount={patientCount} visitCount={activeVisitCount} />

      {activeTab === 'patients' ? (
        <PatientsTab practiceId={practiceId} patientCount={patientCount} />
      ) : (
        <AllVisitsTab userId={userId} visitCount={activeVisitCount} />
      )}
    </>
  );
}

function TabBar({
  activeTab,
  patientCount,
  visitCount,
}: {
  activeTab: ActiveTab;
  patientCount: number;
  visitCount: number;
}) {
  const tabs: { id: ActiveTab; label: string; count: number; href: string }[] = [
    { id: 'patients', label: 'Patients', count: patientCount, href: '/dashboard' },
    { id: 'all', label: 'All visits', count: visitCount, href: '/dashboard?tab=all' },
  ];
  return (
    <div
      style={{
        padding: '0 32px',
        display: 'flex',
        gap: 4,
        borderBottom: '1px solid var(--line)',
        marginTop: 6,
      }}
    >
      {tabs.map((t) => {
        const active = t.id === activeTab;
        return (
          <Link
            key={t.id}
            href={t.href}
            scroll={false}
            style={{
              padding: '12px 16px',
              background: 'none',
              cursor: 'pointer',
              color: active ? 'var(--fg)' : 'var(--fg-3)',
              borderBottom: `2px solid ${active ? 'var(--accent-bright)' : 'transparent'}`,
              fontFamily: 'var(--sans)',
              fontSize: 13,
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: -1,
              textDecoration: 'none',
            }}
            aria-current={active ? 'page' : undefined}
          >
            {t.label}
            <span
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 10,
                color: 'var(--fg-4)',
              }}
            >
              {t.count}
            </span>
          </Link>
        );
      })}
    </div>
  );
}

async function PatientsTab({
  practiceId,
  patientCount,
}: {
  practiceId: string;
  patientCount: number;
}) {
  if (patientCount === 0) return <EmptyPatients />;

  // Two-query form: patient row + latest visit (take:1), then a
  // separate groupBy for active-visit counts. Explicit local types
  // because the shared `@meddoc/db` export is typed `any` (adapter-
  // pg require-wrap, see packages/db/src/index.ts) and loses Prisma's
  // generated row types at the boundary.
  type LatestVisit = {
    createdAt: Date;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    needsReview: boolean;
  };
  type PatientRow = {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    transcribeVisits: LatestVisit[];
  };
  type CountRow = { patientId: string; _count: { _all: number } };

  const rows: PatientRow[] = await prisma.transcribeMdPatient.findMany({
    where: { practiceId, deletedAt: null },
    orderBy: { updatedAt: 'desc' },
    take: PATIENTS_PAGE_SIZE,
    select: {
      id: true,
      name: true,
      dateOfBirth: true,
      transcribeVisits: {
        where: { deletedAt: null, archivedAt: null },
        orderBy: { createdAt: 'desc' },
        take: 1,
        select: {
          createdAt: true,
          specialty: true,
          status: true,
          needsReview: true,
        },
      },
    },
  });

  const patientIds = rows.map((r: PatientRow) => r.id);
  const counts: CountRow[] = patientIds.length
    ? await prisma.transcribeVisit.groupBy({
        by: ['patientId'],
        where: {
          patientId: { in: patientIds },
          deletedAt: null,
          archivedAt: null,
        },
        _count: { _all: true },
      })
    : [];
  const countByPatient = new Map<string, number>(
    counts.map((c: CountRow) => [c.patientId, c._count._all])
  );

  const patients: DashboardPatient[] = rows.map(
    (r: PatientRow): DashboardPatient => {
      const latest = r.transcribeVisits[0];
      return {
        id: r.id,
        name: r.name,
        dateOfBirth: r.dateOfBirth,
        visitCount: countByPatient.get(r.id) ?? 0,
        lastVisitAt: latest?.createdAt ?? null,
        lastVisitSpecialty: latest?.specialty ?? null,
        lastVisitStatus: latest?.status ?? null,
        lastVisitNeedsReview: latest?.needsReview ?? false,
      };
    }
  );

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
        gap: 14,
        padding: '22px 32px 32px',
      }}
    >
      {patients.map((p) => (
        <PatientCard key={p.id} patient={p} />
      ))}
    </div>
  );
}

async function AllVisitsTab({
  userId,
  visitCount,
}: {
  userId: string;
  visitCount: number;
}) {
  if (visitCount === 0) return <EmptyVisits />;

  type VisitRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    needsReview: boolean;
    createdAt: Date;
    audioDurationSec: number | null;
    patient: { name: string } | null;
  };
  const rows: VisitRow[] = await prisma.transcribeVisit.findMany({
    where: { userId, deletedAt: null, archivedAt: null },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: VISITS_PAGE_SIZE,
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
  });

  const visits: DashboardVisit[] = rows.map(
    (v: VisitRow): DashboardVisit => ({
      id: v.id,
      patientName: v.patient?.name ?? null,
      patientFallback: v.patientName ?? null,
      specialty: v.specialty,
      status: v.status,
      needsReview: v.needsReview,
      createdAt: v.createdAt,
      audioDurationSec: v.audioDurationSec,
    })
  );

  return <VisitList visits={visits} />;
}

function EmptyPatients() {
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 420,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      {/* Minimal violet quill illustration — final version ported in
         Gate 13 (EmptyState + IlloQuill). Placeholder keeps the
         composition right without the asset work. */}
      <div
        aria-hidden
        style={{
          width: 96,
          height: 96,
          borderRadius: 24,
          background:
            'radial-gradient(circle at 30% 30%, rgba(209,181,255,0.35), rgba(107,63,217,0.08))',
          border: '1px solid rgba(139,92,255,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 22,
        }}
      >
        <Ic.sparkle
          width={36}
          height={36}
          style={{ color: 'var(--accent-bright)' }}
        />
      </div>
      <h2
        className="qm-serif"
        style={{
          margin: 0,
          fontSize: 24,
          fontWeight: 400,
          letterSpacing: '-0.015em',
        }}
      >
        No patients <em style={{ color: 'var(--accent-bright)' }}>yet</em>
      </h2>
      <p
        style={{
          marginTop: 10,
          fontSize: 13.5,
          color: 'var(--fg-3)',
          lineHeight: 1.55,
          maxWidth: 340,
        }}
      >
        Start your first visit — we&apos;ll create a patient record for you
        along the way.
      </p>
      <Link
        href="/visits/new"
        className="qm-btn qm-btn-primary"
        style={{
          marginTop: 20,
          padding: '10px 18px',
          textDecoration: 'none',
        }}
      >
        <Ic.plus width={14} height={14} />
        Start your first visit
      </Link>
    </div>
  );
}

function EmptyVisits() {
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 420,
        textAlign: 'center',
        color: 'var(--fg-3)',
        fontSize: 13.5,
      }}
    >
      No visits yet for any patient.{' '}
      <Link
        href="/visits/new"
        style={{ color: 'var(--accent-bright)', fontWeight: 500 }}
      >
        Start one →
      </Link>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ padding: '28px 32px' }}>
      <div
        className="qm-shimmer"
        style={{ height: 36, width: 300, borderRadius: 6, marginBottom: 10 }}
      />
      <div
        className="qm-shimmer"
        style={{ height: 14, width: 220, borderRadius: 4, marginBottom: 24 }}
      />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 20,
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="qm-shimmer"
            style={{ height: 110, borderRadius: 12 }}
          />
        ))}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 14,
        }}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="qm-shimmer"
            style={{ height: 120, borderRadius: 12 }}
          />
        ))}
      </div>
    </div>
  );
}
