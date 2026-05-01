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
//
// Phase 2 (Clinician remodel — Batch C): opts in to the new chrome
// by passing `theme="clinician"` to <AppFrame> and threading the
// same `theme` through every restyled child (PageHeader, StatCard,
// PatientCard, VisitList). Inline JSX (TabBar, EmptyPatients,
// EmptyVisits, DashboardSkeleton) is restyled in-place using the
// `.qm-cl-*` class catalog — they aren't reused elsewhere so a
// theme prop on each would just duplicate code paths nobody else
// calls. Server-side data fetching (auth, prisma queries, redirect)
// is unchanged per PROTECTED_CONTRACTS.md.
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
import { StatCard } from '@/components/dashboard/stat-card';
import {
  VisitList,
  type DashboardVisit,
} from '@/components/dashboard/visit-list';
// Phase 3 Wave 2 (dashboard density). Brings the patients tab to mockup
// fidelity — the 11-row PatientList projecting the same data the legacy
// <PatientCard> grid used to consume, and a "Three drafts, ready when
// you are." section of preview cards under the patient list. The
// legacy <PatientCard> grid is no longer rendered from this page (the
// component itself stays in /components/dashboard/ for /patients/[id]
// consumers).
//
// Phase 4 (cinematic). The greeting line that lived inside the body
// (Greeting component) is replaced by a full-width photo hero band
// (CinematicDashboardHero) that swaps the photo + greeting word based
// on the doctor's local Pacific-time bucket. The Greeting component
// itself stays in components/dashboard/ in case a non-cinematic
// surface wants it; this page simply doesn't render it anymore.
import { CinematicDashboardHero, type DashboardTimeBucket } from '@/components/dashboard/CinematicDashboardHero';
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

// PATIENTS_PAGE_SIZE is gone — the patient panel is capped by
// DASHBOARD_PATIENT_LIMIT (11) downstream to match the mockup.
const VISITS_PAGE_SIZE = 20;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  // Phase 3 Wave 2 — also pull `name` so the greeting can read
  // "Good morning, Dr. {firstName}." downstream. The existing
  // practiceId hand-off is unchanged.
  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { practiceId: true, name: true },
  });
  if (!user) redirect('/login');

  const params = await searchParams;
  const tabRaw = Array.isArray(params.tab) ? params.tab[0] : params.tab;
  const activeTab: ActiveTab = tabRaw === 'all' ? 'all' : 'patients';

  // Phase 4 — compute the initial time-of-day bucket on the SERVER so
  // the cinematic hero band's first paint matches the active photo
  // exactly (no FOUC, no hydration mismatch). The client component
  // re-checks every 60 s and crossfades when the bucket flips.
  // US/Pacific is the launch market and the source of truth here.
  const initialBucket = computeInitialPtBucket();

  return (
    <AppFrame theme="clinician">
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardBody
          userId={session.user.id}
          practiceId={user.practiceId}
          userName={user.name}
          activeTab={activeTab}
          initialBucket={initialBucket}
        />
      </Suspense>
    </AppFrame>
  );
}

/** Server-side PT-hour → bucket mapping. Mirrored on the client side
 *  inside <CinematicDashboardHero>; keeping the formula in both places
 *  is intentional — the server pass renders the SSR-safe initial photo
 *  and the client pass picks up any boundary crossings the SSR cache
 *  missed. */
function computeInitialPtBucket(): DashboardTimeBucket {
  const ptNow = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles',
    hour: 'numeric',
    hour12: false,
  }).format(new Date());
  const ptHour = parseInt(ptNow, 10) % 24;
  if (ptHour >= 5 && ptHour < 12) return 'morning';
  if (ptHour >= 12 && ptHour < 18) return 'afternoon';
  return 'evening';
}

async function DashboardBody({
  userId,
  practiceId,
  userName,
  activeTab,
  initialBucket,
}: {
  userId: string;
  practiceId: string;
  userName: string | null;
  activeTab: ActiveTab;
  initialBucket: DashboardTimeBucket;
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

  // Phase 3 Wave 2 — derive the doctor's first name for the greeting.
  // Splits on whitespace so "Mei-Ling Chen" reads as "Mei-Ling".
  const firstName = userName ? userName.trim().split(/\s+/)[0] ?? null : null;

  return (
    <>
      {/* Phase 4 — cinematic time-based hero band. Replaces the
         in-page <Greeting> + "+ New visit" row. The greeting word
         (morning / afternoon / evening) and matching photo are
         driven by the doctor's Pacific-time bucket; the band silently
         crossfades when the bucket flips during a long session.
         The "+ New visit" CTA stays accessible from the top-nav
         (rendered by <AppFrame>), so the button doesn't disappear
         from the dashboard chrome — it's just hosted upstream. */}
      <CinematicDashboardHero
        initialBucket={initialBucket}
        firstName={firstName}
        subtitle={
          <>
            {patientCount} patient{patientCount === 1 ? '' : 's'} ·{' '}
            {activeVisitCount} total visit
            {activeVisitCount === 1 ? '' : 's'}
            {pendingReview > 0 && (
              <>
                {' · '}
                <span style={{ color: 'var(--color-clinician-sage-bright)' }}>
                  {pendingReview} awaiting your review
                </span>
              </>
            )}
          </>
        }
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          padding: '40px 40px 24px',
        }}
      >
        {/* Existing 4 metric cards stay unchanged. */}
        <StatCard
          theme="clinician"
          label={`Visits / ${now.toLocaleString('en-US', { month: 'short' })}`}
          value={visitsThisMonth}
          unit="this month"
        />
        <StatCard
          theme="clinician"
          label="Avg drafted in"
          value={avgDraftedMin != null ? avgDraftedMin : '—'}
          unit={avgDraftedMin != null ? 'min / visit' : 'no data yet'}
        />
        <StatCard
          theme="clinician"
          label="Pending review"
          value={pendingReview}
          unit={pendingReview === 1 ? 'visit' : 'visits'}
          deltaTone={pendingReview > 0 ? 'amber' : 'mint'}
        />
        <StatCard
          theme="clinician"
          label="Signed this week"
          value={signedThisWeek}
          unit={signedThisWeek === 1 ? 'note' : 'notes'}
        />
      </div>

      <TabBar activeTab={activeTab} patientCount={patientCount} visitCount={activeVisitCount} />

      {activeTab === 'patients' ? (
        <PatientsTab
          practiceId={practiceId}
          userId={userId}
          patientCount={patientCount}
        />
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
  // Mockup ref: docs/design-directions-v3/clinician/dashboard.html L571–576.
  // Soft tab pills (`.qm-cl-tab-row` / `.qm-cl-tab` + `.qm-cl-active`)
  // sit on the page, not on a bottom-border underline like the legacy
  // tabs. Counts ride alongside the label in muted ink-4.
  return (
    <div
      style={{
        padding: '4px 40px 18px',
        display: 'flex',
        justifyContent: 'flex-start',
      }}
    >
      <div className="qm-cl-tab-row">
        {tabs.map((t) => {
          const active = t.id === activeTab;
          return (
            <Link
              key={t.id}
              href={t.href}
              scroll={false}
              className={`qm-cl-tab${active ? ' qm-cl-active' : ''}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                textDecoration: 'none',
              }}
              aria-current={active ? 'page' : undefined}
            >
              {t.label}
              <span
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  color: active ? 'var(--sage-deep)' : 'var(--ink-4)',
                  opacity: active ? 0.85 : 1,
                }}
              >
                {t.count}
              </span>
            </Link>
          );
        })}
      </div>
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

  // Phase 3 Wave 2 (dashboard density). Same two-query form as before,
  // extended with two extra columns (`signedAt`, `chiefComplaint`)
  // pulled from the latest visit so the new <PatientList> rows can
  // render the Batch H "Signed · {date}" pill and the italic
  // chief-complaint snippet from the mockup. A third parallel query
  // grabs the most-recent READY-but-unsigned visits for the
  // "Three drafts, ready when you are." section.
  //
  // Patient cap drops from 20 to 11 (PATIENTS_PAGE_SIZE → DASHBOARD_PATIENT_LIMIT)
  // to match the mockup's "Eleven faces on the schedule." copy. The
  // legacy 20-row scroll wasn't truly paginated upstream — this
  // tightens the dashboard view without losing any patients (full list
  // is at /patients).
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
    // Drafts query — READY status, not yet signed, ordered by most
    // recently updated. Pull soapFinal AND soapDraft so we can prefer
    // the post-Layer-6 polish but fall back to Layer 4 output if the
    // pipeline stopped short. patient.name lives behind a relation
    // include since the dashboard always wants the canonical name
    // (visit.patientName is a legacy free-text fallback).
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
    counts.map((c: CountRow) => [c.patientId, c._count._all])
  );

  const patients: DashboardListPatient[] = rows.map(
    (r: PatientRow): DashboardListPatient => {
      const latest = r.transcribeVisits[0];
      return {
        id: r.id,
        name: r.name,
        // DOB is a date — slice the ISO to avoid any TZ influence.
        dateOfBirth: r.dateOfBirth
          ? r.dateOfBirth.toISOString().slice(0, 10)
          : null,
        visitCount: countByPatient.get(r.id) ?? 0,
        // Full ISO UTC — client formats in viewer's timezone.
        lastVisitAt: latest?.createdAt.toISOString() ?? null,
        lastVisitSpecialty: latest?.specialty ?? null,
        lastVisitStatus: latest?.status ?? null,
        lastVisitNeedsReview: latest?.needsReview ?? false,
        lastVisitSignedAt: latest?.signedAt
          ? latest.signedAt.toISOString()
          : null,
        // Clip on the server so a long chief complaint doesn't push the
        // serialized payload up. ~80 chars matches the mockup's snippet
        // budget (one-line italic).
        lastVisitChiefComplaint: clipChiefComplaint(
          latest?.chiefComplaint ?? null
        ),
      };
    }
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
    })
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

/** Pick the first non-empty line of the SOAP body for the drafts-ready
 *  preview. Falls back to the visit's chief complaint when soapFinal /
 *  soapDraft are both empty (failed pipeline). Strips markdown headers
 *  ("S:", "Subjective:", "##") so the preview reads as prose, not as a
 *  section label. Server-side, no PHI redaction beyond what's already
 *  in the raw text — the dashboard rendering is in-session for the
 *  authed doctor. */
function firstLineFromSoap(
  body: string | null | undefined,
  chiefComplaint: string | null | undefined
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

/** Clip the patient-list chief-complaint snippet to a single-line
 *  budget. Trims trailing punctuation that would render awkwardly
 *  inside curly quotes. */
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
      // ISO UTC — <VisitList> formats + buckets in viewer's local TZ.
      createdAt: v.createdAt.toISOString(),
      // Batch H: surfaces "Signed · {date}" pill on the visit-list row.
      signedAt: v.signedAt ? v.signedAt.toISOString() : null,
      audioDurationSec: v.audioDurationSec,
    })
  );

  return <VisitList visits={visits} theme="clinician" />;
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
          width: 96,
          height: 96,
          borderRadius: 24,
          background: 'var(--sage-tint)',
          border: '1px solid var(--sage-tint-strong)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 22,
        }}
      >
        <Ic.sparkle
          width={36}
          height={36}
          style={{ color: 'var(--sage-deep)' }}
        />
      </div>
      <h2
        className="qm-cl-serif"
        style={{
          margin: 0,
          fontSize: 28,
          fontWeight: 400,
          letterSpacing: '-0.01em',
          color: 'var(--ink)',
          lineHeight: 1.2,
        }}
      >
        No patients <em style={{ color: 'var(--sage-deep)' }}>yet</em>
      </h2>
      <p
        className="qm-cl-serif"
        style={{
          marginTop: 12,
          fontSize: 15,
          color: 'var(--ink-2)',
          lineHeight: 1.55,
          maxWidth: 360,
        }}
      >
        Start your first visit — we&apos;ll create a patient record for you
        along the way.
      </p>
      <Link
        href="/visits/new"
        className="qm-cl-btn qm-cl-btn-primary"
        style={{
          marginTop: 22,
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
        maxWidth: 460,
        textAlign: 'center',
        color: 'var(--ink-3)',
        fontSize: 14.5,
        fontFamily: 'var(--serif)',
      }}
    >
      No visits yet for any patient.{' '}
      <Link
        href="/visits/new"
        style={{ color: 'var(--sage-deep)', fontWeight: 500 }}
      >
        Start one →
      </Link>
    </div>
  );
}

function DashboardSkeleton() {
  // Cream-tinted skeleton tiles. The legacy `.qm-shimmer` animation
  // is built around a violet-on-dark gradient, which reads off-key
  // on the warm cream canvas. For the Clinician variant we just
  // render quiet placeholder rectangles in cream-2 — restful, no
  // theatrical motion (per direction CL-5).
  const tile: React.CSSProperties = {
    background: 'var(--cream-2)',
    border: '1px solid var(--line)',
    borderRadius: 16,
  };
  return (
    <div style={{ padding: '40px 40px 0' }}>
      <div
        style={{
          height: 38,
          width: 320,
          marginBottom: 12,
          ...tile,
          borderRadius: 8,
        }}
      />
      <div
        style={{
          height: 16,
          width: 240,
          marginBottom: 28,
          ...tile,
          borderRadius: 6,
        }}
      />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          marginBottom: 24,
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ height: 140, ...tile }} />
        ))}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 16,
        }}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ height: 140, ...tile }} />
        ))}
      </div>
    </div>
  );
}
