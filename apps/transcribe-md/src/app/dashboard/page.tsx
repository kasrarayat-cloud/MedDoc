// ============================================================================
// Phase 5 — Linear V1 Faithful dashboard.
// ----------------------------------------------------------------------------
// /dashboard                → Patients tab (default)
// /dashboard?tab=all        → All visits tab (grouped by day)
//
// The Phase 4 cinematic photo-band hero is gone. Linear V1 dashboard
// opens with a single-line typographic greeting (Greeting component),
// followed by an inline stats row, followed by the tab nav and the
// active tab content. The 240 px sidebar lives upstream in
// <AppFrame>; this page only renders the main column.
//
// Reference: docs/design-directions-v8-linear/dashboard-v1.html.
//
// Server-side data fetching (auth, prisma queries, redirects) is
// unchanged per PROTECTED_CONTRACTS.md.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { StatCard } from '@/components/dashboard/stat-card';
import { Greeting } from '@/components/dashboard/greeting';
import {
  VisitList,
  type DashboardVisit,
} from '@/components/dashboard/visit-list';
import {
  PatientList,
  type DashboardListPatient,
} from '@/components/dashboard/patient-list';
import {
  DraftsReady,
  type DraftReadyVisit,
} from '@/components/dashboard/drafts-ready';

export const metadata: Metadata = { title: 'Dashboard' };

type SearchParams = Record<string, string | string[] | undefined>;
type ActiveTab = 'patients' | 'all';

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
    select: { practiceId: true, name: true },
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
          userName={user.name}
          activeTab={activeTab}
        />
      </Suspense>
    </AppFrame>
  );
}

async function DashboardBody({
  userId,
  practiceId,
  userName,
  activeTab,
}: {
  userId: string;
  practiceId: string;
  userName: string | null;
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

  const firstName = userName ? userName.trim().split(/\s+/)[0] ?? null : null;

  // Greeting subtitle — sage-bright callout when there are pending
  // reviews so the doctor sees the action signal at a glance.
  const subtitleNode = (
    <>
      {patientCount} patient{patientCount === 1 ? '' : 's'} ·{' '}
      {activeVisitCount} visit{activeVisitCount === 1 ? '' : 's'}
      {pendingReview > 0 && (
        <>
          {' · '}
          <span style={{ color: 'var(--color-linear-sage-bright)' }}>
            {pendingReview} awaiting review
          </span>
        </>
      )}
    </>
  );

  return (
    <div style={{ padding: '18px 24px 80px' }}>
      <Greeting firstName={firstName} subtitle={subtitleNode} />

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 0,
          padding: '6px 0 14px',
          marginBottom: 8,
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        <StatCard
          label={`Visits / ${now.toLocaleString('en-US', { month: 'short' })}`}
          value={visitsThisMonth}
          unit="this month"
        />
        <StatCard
          label="Avg drafted in"
          value={avgDraftedMin != null ? avgDraftedMin : '—'}
          unit={avgDraftedMin != null ? 'min / visit' : 'no data yet'}
        />
        <StatCard
          label="Pending review"
          value={pendingReview}
          unit={pendingReview === 1 ? 'visit' : 'visits'}
          deltaTone={pendingReview > 0 ? 'amber' : 'mint'}
        />
        <StatCard
          label="Signed this week"
          value={signedThisWeek}
          unit={signedThisWeek === 1 ? 'note' : 'notes'}
        />
      </div>

      <TabBar
        activeTab={activeTab}
        patientCount={patientCount}
        visitCount={activeVisitCount}
      />

      {activeTab === 'patients' ? (
        <PatientsTab
          practiceId={practiceId}
          userId={userId}
          patientCount={patientCount}
        />
      ) : (
        <AllVisitsTab userId={userId} visitCount={activeVisitCount} />
      )}
    </div>
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
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        marginTop: 16,
        marginBottom: 4,
      }}
    >
      {tabs.map((t) => {
        const active = t.id === activeTab;
        return (
          <Link
            key={t.id}
            href={t.href}
            scroll={false}
            aria-current={active ? 'page' : undefined}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              borderRadius: 6,
              fontFamily: 'var(--font-sans)',
              fontSize: 12.5,
              color: active
                ? 'var(--color-linear-text)'
                : 'var(--color-linear-text-2)',
              background: active
                ? 'var(--color-linear-sage-tint)'
                : 'transparent',
              textDecoration: 'none',
              transition:
                'background-color 100ms ease, color 100ms ease',
              fontWeight: active ? 500 : 400,
              letterSpacing: '-0.005em',
            }}
          >
            {t.label}
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: active
                  ? 'var(--color-linear-sage-bright)'
                  : 'var(--color-linear-text-3)',
                fontVariantNumeric: 'tabular-nums',
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
  userId,
  patientCount,
}: {
  practiceId: string;
  userId: string;
  patientCount: number;
}) {
  if (patientCount === 0) return <EmptyPatients />;

  type LatestVisit = {
    id: string;
    createdAt: Date;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    needsReview: boolean;
    signedAt: Date | null;
    chiefComplaint: string | null;
  };
  type PatientRow = {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    transcribeVisits: LatestVisit[];
  };
  type CountRow = { patientId: string; _count: { _all: number } };
  type DraftRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    needsReview: boolean;
    updatedAt: Date;
    soapFinal: string | null;
    soapDraft: string | null;
    chiefComplaint: string | null;
    patient: { name: string } | null;
  };

  const [rows, draftRows] = await Promise.all([
    prisma.transcribeMdPatient.findMany({
      where: { practiceId, deletedAt: null },
      orderBy: { updatedAt: 'desc' },
      take: DASHBOARD_PATIENT_LIMIT,
      select: {
        id: true,
        name: true,
        dateOfBirth: true,
        transcribeVisits: {
          where: { deletedAt: null, archivedAt: null },
          orderBy: { createdAt: 'desc' },
          take: 1,
          select: {
            id: true,
            createdAt: true,
            specialty: true,
            status: true,
            needsReview: true,
            signedAt: true,
            chiefComplaint: true,
          },
        },
      },
    }) as Promise<PatientRow[]>,
    prisma.transcribeVisit.findMany({
      where: {
        userId,
        deletedAt: null,
        archivedAt: null,
        status: TranscribeVisitStatus.READY,
        signedAt: null,
      },
      orderBy: { updatedAt: 'desc' },
      take: DASHBOARD_DRAFT_LIMIT,
      select: {
        id: true,
        patientName: true,
        specialty: true,
        needsReview: true,
        updatedAt: true,
        soapFinal: true,
        soapDraft: true,
        chiefComplaint: true,
        patient: { select: { name: true } },
      },
    }) as Promise<DraftRow[]>,
  ]);

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
    counts.map((c: CountRow) => [c.patientId, c._count._all]),
  );

  const patients: DashboardListPatient[] = rows.map(
    (r: PatientRow): DashboardListPatient => {
      const latest = r.transcribeVisits[0];
      return {
        id: r.id,
        name: r.name,
        dateOfBirth: r.dateOfBirth
          ? r.dateOfBirth.toISOString().slice(0, 10)
          : null,
        visitCount: countByPatient.get(r.id) ?? 0,
        lastVisitAt: latest?.createdAt.toISOString() ?? null,
        lastVisitSpecialty: latest?.specialty ?? null,
        lastVisitStatus: latest?.status ?? null,
        lastVisitNeedsReview: latest?.needsReview ?? false,
        lastVisitSignedAt: latest?.signedAt
          ? latest.signedAt.toISOString()
          : null,
        lastVisitChiefComplaint: clipChiefComplaint(
          latest?.chiefComplaint ?? null,
        ),
      };
    },
  );

  const drafts: DraftReadyVisit[] = draftRows.map(
    (v: DraftRow): DraftReadyVisit => ({
      id: v.id,
      patientName: v.patient?.name ?? null,
      patientFallback: v.patientName ?? null,
      specialty: v.specialty ?? null,
      draftedAt: v.updatedAt.toISOString(),
      previewLine: firstLineFromSoap(v.soapFinal ?? v.soapDraft, v.chiefComplaint),
      needsReview: v.needsReview,
    }),
  );

  return (
    <>
      <PatientList patients={patients} />
      <DraftsReady drafts={drafts} />
    </>
  );
}

const DASHBOARD_PATIENT_LIMIT = 11;
const DASHBOARD_DRAFT_LIMIT = 3;
const SOAP_PREVIEW_MAX_CHARS = 160;
const CHIEF_PREVIEW_MAX_CHARS = 80;

function firstLineFromSoap(
  body: string | null | undefined,
  chiefComplaint: string | null | undefined,
): string | null {
  const source = body && body.trim().length > 0 ? body : chiefComplaint ?? '';
  if (!source) return null;
  const lines = source.split(/\r?\n/);
  for (const raw of lines) {
    const line = raw
      .replace(/^#+\s*/g, '')
      .replace(/^\s*\*\*\s*/, '')
      .replace(/\s*\*\*\s*$/, '')
      .replace(/^(S|O|A|P|Subjective|Objective|Assessment|Plan)\s*[:—–-]\s*/i, '')
      .trim();
    if (line.length === 0) continue;
    return line.length > SOAP_PREVIEW_MAX_CHARS
      ? line.slice(0, SOAP_PREVIEW_MAX_CHARS - 1).trimEnd() + '…'
      : line;
  }
  return null;
}

function clipChiefComplaint(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.replace(/\s+/g, ' ').trim();
  if (!trimmed) return null;
  return trimmed.length > CHIEF_PREVIEW_MAX_CHARS
    ? trimmed.slice(0, CHIEF_PREVIEW_MAX_CHARS - 1).trimEnd() + '…'
    : trimmed;
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
    signedAt: Date | null;
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
      signedAt: true,
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
      createdAt: v.createdAt.toISOString(),
      signedAt: v.signedAt ? v.signedAt.toISOString() : null,
      audioDurationSec: v.audioDurationSec,
    }),
  );

  return <VisitList visits={visits} />;
}

function EmptyPatients() {
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 460,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 56,
          height: 56,
          borderRadius: 14,
          background: 'var(--color-linear-sage-tint)',
          border: '1px solid rgba(122, 166, 140, 0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 18,
          color: 'var(--color-linear-sage-bright)',
          fontSize: 22,
        }}
      >
        +
      </div>
      <h2
        style={{
          margin: 0,
          fontFamily: 'var(--font-sans)',
          fontSize: 22,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          color: 'var(--color-linear-text)',
          lineHeight: 1.2,
        }}
      >
        No patients yet
      </h2>
      <p
        style={{
          marginTop: 10,
          fontFamily: 'var(--font-sans)',
          fontSize: 13.5,
          color: 'var(--color-linear-text-2)',
          lineHeight: 1.55,
          maxWidth: 360,
        }}
      >
        Start your first visit — we&apos;ll create a patient record for you
        along the way.
      </p>
      <Link
        href="/visits/new"
        className="qm-lin-btn-primary"
        style={{
          marginTop: 18,
          textDecoration: 'none',
          height: 32,
          padding: '0 14px',
          fontSize: 13,
        }}
      >
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
        maxWidth: 460,
        textAlign: 'center',
        color: 'var(--color-linear-text-3)',
        fontFamily: 'var(--font-sans)',
        fontSize: 13,
      }}
    >
      No visits yet for any patient.{' '}
      <Link
        href="/visits/new"
        style={{
          color: 'var(--color-linear-sage-bright)',
          fontWeight: 500,
          textDecoration: 'none',
        }}
      >
        Start one →
      </Link>
    </div>
  );
}

function DashboardSkeleton() {
  // Linear V1 skeleton — quiet linear-surface-2 placeholders, no shimmer.
  const tile: React.CSSProperties = {
    background: 'var(--color-linear-surface-2)',
    border: '1px solid var(--color-linear-border)',
    borderRadius: 8,
  };
  return (
    <div style={{ padding: '18px 24px 0' }}>
      <div
        style={{
          height: 18,
          width: 320,
          marginBottom: 18,
          ...tile,
          borderRadius: 6,
        }}
      />
      <div
        style={{
          display: 'flex',
          gap: 0,
          padding: '6px 0 14px',
          marginBottom: 8,
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              padding: '0 18px',
              borderRight:
                i < 3
                  ? '1px solid var(--color-linear-hairline)'
                  : 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <div style={{ height: 22, width: 60, ...tile, borderRadius: 4 }} />
            <div style={{ height: 10, width: 80, ...tile, borderRadius: 3 }} />
          </div>
        ))}
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
          marginTop: 18,
        }}
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            style={{
              height: 36,
              borderBottom: '1px solid var(--color-linear-hairline)',
              opacity: 0.6,
            }}
          />
        ))}
      </div>
    </div>
  );
}
