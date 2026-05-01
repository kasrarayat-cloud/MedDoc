// ============================================================================
// Patient detail — app-redesign-v1 (HANDOFF §2.2 PatientDetailScreen).
// ----------------------------------------------------------------------------
// /patients/[id]               → Visits tab (default)
// /patients/[id]?tab=notes     → Notes stub (Gate 13 or later)
// /patients/[id]?tab=files     → Files stub
// /patients/[id]?tab=trash     → Trash tab (only shown when trashCount > 0)
//
// Full shell (TopNav + IconRail + scrollable main) via AppFrame. Visit
// history uses the Gate-6 <VisitList> component. Problem list chips
// sit on the header with a [Manage] drawer; MRN + insurance are now
// editable through the existing Edit dialog.
//
// Phase 4 follow-up (Bug 2) — this route was missed in the Phase 2 / 3 / 4
// Clinician migration and was still rendering the legacy dark + violet
// `app-redesign-v1` chrome. We now opt in to the Clinician shell via
// `<AppFrame theme="clinician">`, thread `theme="clinician"` to the
// nested chrome children (StatCard, VisitList, Avatar), and re-style
// the inline header card / breadcrumb / tab bar / empty messages to
// the warm cream + sage + ink token catalog. The DB queries, RBAC
// gates (auth + practiceId scope), notFound() short-circuit, and all
// dialog components remain byte-identical.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { Avatar } from '@/components/ui/avatar';
import { Ic } from '@/components/ui/icon';
import { StatCard } from '@/components/dashboard/stat-card';
import {
  VisitList,
  type DashboardVisit,
} from '@/components/dashboard/visit-list';
import {
  parseProblemList,
  statusLabel,
  type ProblemStatus,
} from '@/lib/problem-list';
import { EditPatientDialog } from './edit-patient-dialog';
import { DeletePatientDialog } from './delete-patient-dialog';
import { ProblemListDialog } from './problem-list-dialog';
import {
  TrashedVisitCard,
  type TrashedVisitCardData,
} from './trashed-visit-card';

export const metadata: Metadata = { title: 'Patient' };

type SearchParams = Record<string, string | string[] | undefined>;
type ActiveTab = 'visits' | 'notes' | 'files' | 'trash';

function resolveTab(raw: string | undefined, trashCount: number): ActiveTab {
  if (raw === 'notes') return 'notes';
  if (raw === 'files') return 'files';
  if (raw === 'trash' && trashCount > 0) return 'trash';
  return 'visits';
}

function formatDob(d: Date | null): string | null {
  if (!d) return null;
  return d.toISOString().slice(0, 10);
}

function yearsFrom(d: Date): number {
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

function relTime(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const diffMin = diffMs / 60000;
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${Math.round(diffMin)}m ago`;
  const diffH = diffMin / 60;
  if (diffH < 24) return `${Math.round(diffH)}h ago`;
  if (diffH < 48) return 'yesterday';
  const diffD = diffH / 24;
  if (diffD < 7) return `${Math.round(diffD)}d ago`;
  if (diffD < 30) return `${Math.round(diffD / 7)}w ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Map the canonical problem-list status (`active | resolved | chronic`)
 *  onto the Clinician pill catalog (`.qm-cl-pill-{tone}`). The legacy
 *  pill mapping in `lib/problem-list.statusTone()` returns the older
 *  `mint | amber | accent` tones used by the dark theme; we keep that
 *  helper unmodified (it's pure logic, may be consumed elsewhere) and
 *  do the Clinician mapping locally:
 *    active   → amber  (caution / open issue)
 *    resolved → sage   (closed / on-track)
 *    chronic  → soft   (long-running / informational) */
function clinicianProblemTone(
  status: ProblemStatus
): 'amber' | 'sage' | 'soft' {
  switch (status) {
    case 'active':
      return 'amber';
    case 'resolved':
      return 'sage';
    case 'chronic':
      return 'soft';
  }
}

export default async function PatientPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { id } = await params;
  const spRaw = await searchParams;
  const tabParam = Array.isArray(spRaw.tab) ? spRaw.tab[0] : spRaw.tab;

  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { id: true, practiceId: true },
  });
  if (!user) redirect('/login');

  type PatientRow = {
    id: string;
    practiceId: string;
    name: string;
    dateOfBirth: Date | null;
    externalId: string | null;
    mrn: string | null;
    insurance: string | null;
    problemList: unknown;
    deletedAt: Date | null;
    createdAt: Date;
    updatedAt: Date;
  };

  const patient: PatientRow | null = await prisma.transcribeMdPatient.findUnique({
    where: { id },
    select: {
      id: true,
      practiceId: true,
      name: true,
      dateOfBirth: true,
      externalId: true,
      mrn: true,
      insurance: true,
      problemList: true,
      deletedAt: true,
      createdAt: true,
      updatedAt: true,
    },
  });
  if (!patient || patient.practiceId !== user.practiceId) notFound();

  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

  const [activeCount, trashCount, signedCount, visitsThisMonth, latestVisit] =
    await Promise.all([
      prisma.transcribeVisit.count({
        where: {
          patientId: id,
          userId: user.id,
          deletedAt: null,
          archivedAt: null,
        },
      }),
      prisma.transcribeVisit.count({
        where: {
          patientId: id,
          userId: user.id,
          deletedAt: { not: null },
        },
      }),
      prisma.transcribeVisit.count({
        where: {
          patientId: id,
          userId: user.id,
          status: 'SIGNED',
        },
      }),
      prisma.transcribeVisit.count({
        where: {
          patientId: id,
          userId: user.id,
          deletedAt: null,
          createdAt: { gte: startOfMonth },
        },
      }),
      prisma.transcribeVisit.findFirst({
        where: {
          patientId: id,
          userId: user.id,
          deletedAt: null,
          archivedAt: null,
        },
        orderBy: { createdAt: 'desc' },
        select: { createdAt: true, specialty: true },
      }),
    ]);

  const activeTab = resolveTab(tabParam, trashCount);
  const dob = patient.dateOfBirth;
  const dobIso = formatDob(dob);
  const isDeleted = patient.deletedAt !== null;
  const problems = parseProblemList(patient.problemList);

  return (
    <AppFrame theme="clinician">
      <div
        style={{
          padding: '18px 40px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 13,
          color: 'var(--ink-3)',
        }}
      >
        <Link
          href="/patients"
          style={{ color: 'var(--ink-3)', textDecoration: 'none' }}
        >
          Patients
        </Link>
        <Ic.chevRight width={12} height={12} />
        <span
          className="qm-cl-serif"
          style={{ color: 'var(--ink)' }}
        >
          {patient.name}
        </span>
      </div>

      {isDeleted && <DeletedBanner />}

      <PatientHeaderCard
        patient={patient}
        problems={problems}
        dobIso={dobIso}
        age={dob ? yearsFrom(dob) : null}
        visitCount={activeCount}
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 16,
          padding: '24px 40px 8px',
        }}
      >
        <StatCard
          theme="clinician"
          label="Total visits"
          value={activeCount}
          unit={activeCount === 1 ? 'visit' : 'visits'}
        />
        <StatCard
          theme="clinician"
          label="Last visit"
          value={latestVisit ? relTime(latestVisit.createdAt) : '—'}
          unit={latestVisit ? '' : 'none yet'}
          delta={
            latestVisit ? (
              <span style={{ textTransform: 'capitalize' }}>
                {latestVisit.specialty}
              </span>
            ) : null
          }
          deltaTone="accent-bright"
        />
        <StatCard
          theme="clinician"
          label={`Visits / ${now.toLocaleString('en-US', { month: 'short' })}`}
          value={visitsThisMonth}
          unit="this month"
        />
        <StatCard
          theme="clinician"
          label="Signed"
          value={signedCount}
          unit={signedCount === 1 ? 'note' : 'notes'}
        />
      </div>

      <TabBar
        patientId={patient.id}
        activeTab={activeTab}
        visitCount={activeCount}
        trashCount={trashCount}
      />

      {activeTab === 'visits' &&
        (activeCount === 0 ? (
          <VisitsEmpty deleted={isDeleted} patientId={patient.id} />
        ) : (
          <VisitsTab patientId={patient.id} userId={user.id} />
        ))}

      {activeTab === 'trash' && (
        <TrashTab patientId={patient.id} userId={user.id} />
      )}

      {activeTab === 'notes' && (
        <StubTab
          title="Notes"
          body="A freeform clinical notepad for this patient lands later. Scoped out of the app-redesign scope."
        />
      )}

      {activeTab === 'files' && (
        <StubTab
          title="Files"
          body="Patient-attached files (imaging, referrals, consent forms). Not ported yet."
        />
      )}
    </AppFrame>
  );
}

// ────────────────────────────────────────────────────────────────

function DeletedBanner() {
  return (
    <div
      role="status"
      style={{
        margin: '18px 40px 0',
        padding: '12px 16px',
        borderRadius: 12,
        border: '1px solid var(--line)',
        background: 'var(--cream-2)',
        fontSize: 13,
        color: 'var(--ink-3)',
        fontFamily: 'var(--serif)',
      }}
    >
      This patient has been deleted. Visits below remain accessible, but new
      visits can&apos;t be added.
    </div>
  );
}

function PatientHeaderCard({
  patient,
  problems,
  dobIso,
  age,
  visitCount,
}: {
  patient: {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    externalId: string | null;
    mrn: string | null;
    insurance: string | null;
    problemList: unknown;
    deletedAt: Date | null;
  };
  problems: ReturnType<typeof parseProblemList>;
  dobIso: string | null;
  age: number | null;
  visitCount: number;
}) {
  // Italicise the last word of the name with sage glow to match §1.2
  // signature move and the dashboard greeting / cinematic-hero pattern
  // ("Linda K. <em>Ahmed</em>"). Single-token names fall back to plain.
  const trimmed = patient.name.trim();
  const idx = trimmed.lastIndexOf(' ');
  const firstPart = idx >= 0 ? trimmed.slice(0, idx) : trimmed;
  const lastPart = idx >= 0 ? trimmed.slice(idx + 1) : '';

  const isDeleted = patient.deletedAt !== null;
  const canNewVisit = !isDeleted;

  return (
    <div
      style={{
        padding: '20px 40px 28px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 22,
        borderBottom: '1px solid var(--line)',
      }}
    >
      <Avatar name={patient.name} size={76} theme="clinician" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1
          className="qm-cl-serif"
          style={{
            margin: 0,
            fontSize: 34,
            fontWeight: 400,
            letterSpacing: '-0.015em',
            lineHeight: 1.1,
            color: 'var(--ink)',
          }}
        >
          {firstPart}
          {lastPart && (
            <>
              {' '}
              <em
                style={{
                  color: 'var(--sage-deep)',
                  fontStyle: 'italic',
                }}
              >
                {lastPart}
              </em>
            </>
          )}
        </h1>
        <div
          style={{
            display: 'flex',
            gap: 18,
            marginTop: 10,
            color: 'var(--ink-3)',
            fontSize: 12.5,
            fontFamily: 'var(--mono)',
            flexWrap: 'wrap',
          }}
        >
          {dobIso && (
            <span>
              DOB {dobIso}
              {age != null ? ` (${age})` : ''}
            </span>
          )}
          {patient.mrn && <span>MRN {patient.mrn}</span>}
          {patient.externalId && <span>ID {patient.externalId}</span>}
          {patient.insurance && <span>{patient.insurance}</span>}
          {!dobIso && !patient.mrn && !patient.externalId && !patient.insurance && (
            <span style={{ fontStyle: 'italic', color: 'var(--ink-4)' }}>
              No MRN / DOB / insurance on file — edit to add
            </span>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 14,
            flexWrap: 'wrap',
          }}
        >
          {problems.map((p, i) => {
            const tone = clinicianProblemTone(p.status);
            return (
              <span
                key={`${p.condition}-${i}`}
                className={`qm-cl-pill qm-cl-pill-${tone}`}
                title={`${statusLabel(p.status)}${p.icd10 ? ` · ${p.icd10}` : ''}`}
              >
                <span className="qm-cl-pill-dot" />
                {p.condition}
              </span>
            );
          })}
          {problems.length === 0 && (
            <span
              style={{
                fontSize: 12,
                color: 'var(--ink-4)',
                fontFamily: 'var(--mono)',
                letterSpacing: '0.02em',
              }}
            >
              No problem list yet.
            </span>
          )}
          <ProblemListDialog
            patientId={patient.id}
            initialProblemList={patient.problemList}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {canNewVisit && (
          <Link
            href={`/visits/new?patientId=${patient.id}`}
            className="qm-cl-btn qm-cl-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        )}
        {visitCount > 0 && (
          <a
            href={`/api/patients/${patient.id}/export`}
            className="qm-cl-btn qm-cl-btn-ghost"
            style={{ textDecoration: 'none' }}
          >
            <Ic.download width={13} height={13} />
            Export
          </a>
        )}
        <EditPatientDialog
          patientId={patient.id}
          initialName={patient.name}
          initialDob={dobIso}
          initialExternalId={patient.externalId}
          initialMrn={patient.mrn}
          initialInsurance={patient.insurance}
        />
        <DeletePatientDialog
          patientId={patient.id}
          patientName={patient.name}
          visitCount={visitCount}
        />
      </div>
    </div>
  );
}

function TabBar({
  patientId,
  activeTab,
  visitCount,
  trashCount,
}: {
  patientId: string;
  activeTab: ActiveTab;
  visitCount: number;
  trashCount: number;
}) {
  const base = `/patients/${patientId}`;
  const tabs: {
    id: ActiveTab;
    label: string;
    count?: number;
    href: string;
    hidden?: boolean;
  }[] = [
    { id: 'visits', label: 'Visits', count: visitCount, href: base },
    { id: 'notes', label: 'Notes', href: `${base}?tab=notes` },
    { id: 'files', label: 'Files', href: `${base}?tab=files` },
    {
      id: 'trash',
      label: 'Trash',
      count: trashCount,
      href: `${base}?tab=trash`,
      hidden: trashCount === 0,
    },
  ];
  // Same `.qm-cl-tab-row` / `.qm-cl-tab` chips as the dashboard tab idiom.
  return (
    <div
      style={{
        padding: '20px 40px 4px',
        display: 'flex',
        justifyContent: 'flex-start',
      }}
    >
      <div className="qm-cl-tab-row">
        {tabs
          .filter((t) => !t.hidden)
          .map((t) => {
            const active = t.id === activeTab;
            return (
              <Link
                key={t.id}
                href={t.href}
                scroll={false}
                aria-current={active ? 'page' : undefined}
                className={`qm-cl-tab${active ? ' qm-cl-active' : ''}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  textDecoration: 'none',
                }}
              >
                {t.label}
                {t.count != null && (
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
                )}
              </Link>
            );
          })}
      </div>
    </div>
  );
}

async function VisitsTab({
  patientId,
  userId,
}: {
  patientId: string;
  userId: string;
}) {
  type Row = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    needsReview: boolean;
    createdAt: Date;
    signedAt: Date | null;
    audioDurationSec: number | null;
  };
  const rows: Row[] = await prisma.transcribeVisit.findMany({
    where: {
      patientId,
      userId,
      deletedAt: null,
      archivedAt: null,
    },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      needsReview: true,
      createdAt: true,
      signedAt: true,
      audioDurationSec: true,
    },
  });
  const visits: DashboardVisit[] = rows.map(
    (v: Row): DashboardVisit => ({
      id: v.id,
      patientName: v.patientName,
      patientFallback: null,
      specialty: v.specialty,
      status: v.status,
      needsReview: v.needsReview,
      createdAt: v.createdAt.toISOString(),
      // Batch H: surfaces "Signed · {date}" pill on the visit-list row.
      signedAt: v.signedAt ? v.signedAt.toISOString() : null,
      audioDurationSec: v.audioDurationSec,
    })
  );
  return <VisitList visits={visits} theme="clinician" />;
}

async function TrashTab({
  patientId,
  userId,
}: {
  patientId: string;
  userId: string;
}) {
  type Row = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    createdAt: Date;
    deletedAt: Date | null;
  };
  const rows: Row[] = await prisma.transcribeVisit.findMany({
    where: {
      patientId,
      userId,
      deletedAt: { not: null },
    },
    orderBy: [{ deletedAt: 'desc' }, { id: 'desc' }],
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
      deletedAt: true,
    },
  });
  if (rows.length === 0) {
    return (
      <div
        style={{
          margin: '60px auto',
          maxWidth: 420,
          textAlign: 'center',
          color: 'var(--ink-3)',
          fontSize: 13.5,
          fontFamily: 'var(--serif)',
        }}
      >
        No deleted visits.
      </div>
    );
  }
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
        gap: 14,
        padding: '24px 40px 40px',
      }}
    >
      {rows.map((v: Row) => (
        <TrashedVisitCard
          key={v.id}
          visit={v as unknown as TrashedVisitCardData}
        />
      ))}
    </div>
  );
}

function VisitsEmpty({
  deleted,
  patientId,
}: {
  deleted: boolean;
  patientId: string;
}) {
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 440,
        textAlign: 'center',
        color: 'var(--ink-3)',
        fontSize: 14,
        fontFamily: 'var(--serif)',
        lineHeight: 1.55,
      }}
    >
      <p style={{ margin: 0 }}>No visits for this patient yet.</p>
      {!deleted && (
        <p style={{ marginTop: 12 }}>
          <Link
            href={`/visits/new?patientId=${patientId}`}
            style={{
              color: 'var(--sage-deep)',
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            Start a new visit →
          </Link>
        </p>
      )}
    </div>
  );
}

function StubTab({ title, body }: { title: string; body: string }) {
  return (
    <div
      style={{
        margin: '60px auto',
        maxWidth: 480,
        textAlign: 'center',
        padding: '0 24px',
      }}
    >
      <div className="qm-cl-eyebrow" style={{ marginBottom: 12 }}>
        {title}
      </div>
      <h2
        className="qm-cl-serif"
        style={{
          margin: 0,
          fontSize: 24,
          fontWeight: 400,
          letterSpacing: '-0.015em',
          color: 'var(--ink)',
        }}
      >
        Coming{' '}
        <em style={{ color: 'var(--sage-deep)', fontStyle: 'italic' }}>
          soon
        </em>
      </h2>
      <p
        className="qm-cl-serif"
        style={{
          marginTop: 12,
          fontSize: 14,
          color: 'var(--ink-2)',
          lineHeight: 1.6,
          maxWidth: 380,
          margin: '12px auto 0',
        }}
      >
        {body}
      </p>
    </div>
  );
}
