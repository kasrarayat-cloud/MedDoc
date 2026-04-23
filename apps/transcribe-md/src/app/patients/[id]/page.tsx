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
  statusTone,
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
    <AppFrame>
      <div
        style={{
          padding: '18px 32px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 12.5,
          color: 'var(--fg-3)',
        }}
      >
        <Link
          href="/dashboard"
          style={{ color: 'var(--fg-3)', textDecoration: 'none' }}
        >
          Patients
        </Link>
        <Ic.chevRight width={12} height={12} />
        <span style={{ color: 'var(--fg)' }}>{patient.name}</span>
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
          gap: 14,
          padding: '22px 32px 6px',
        }}
      >
        <StatCard
          label="§ Total visits"
          value={activeCount}
          unit={activeCount === 1 ? 'visit' : 'visits'}
        />
        <StatCard
          label="§ Last visit"
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
          label={`§ Visits / ${now.toLocaleString('en-US', { month: 'short' })}`}
          value={visitsThisMonth}
          unit="this month"
        />
        <StatCard
          label="§ Signed"
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
        margin: '18px 32px 0',
        padding: '10px 14px',
        borderRadius: 12,
        border: '1px solid var(--line)',
        background: 'rgba(255, 255, 255, 0.02)',
        fontSize: 12.5,
        color: 'var(--fg-3)',
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
  // Italicise the last word of the name to match §1.2 signature move:
  // "Linda K. <em>Ahmed</em>". Single-token names fall back to plain.
  const trimmed = patient.name.trim();
  const idx = trimmed.lastIndexOf(' ');
  const firstPart = idx >= 0 ? trimmed.slice(0, idx) : trimmed;
  const lastPart = idx >= 0 ? trimmed.slice(idx + 1) : '';

  const isDeleted = patient.deletedAt !== null;
  const canNewVisit = !isDeleted;

  return (
    <div
      style={{
        padding: '16px 32px 24px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 20,
        borderBottom: '1px solid var(--line)',
      }}
    >
      <Avatar name={patient.name} size={76} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1
          className="qm-serif"
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 400,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          {firstPart}
          {lastPart && (
            <>
              {' '}
              <em style={{ color: 'var(--accent-bright)' }}>{lastPart}</em>
            </>
          )}
        </h1>
        <div
          style={{
            display: 'flex',
            gap: 18,
            marginTop: 8,
            color: 'var(--fg-3)',
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
            <span style={{ fontStyle: 'italic', color: 'var(--fg-4)' }}>
              No MRN / DOB / insurance on file — edit to add
            </span>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginTop: 12,
            flexWrap: 'wrap',
          }}
        >
          {problems.map((p, i) => (
            <span
              key={`${p.condition}-${i}`}
              className={`qm-chip qm-chip-${statusTone(p.status)}`}
              title={`${statusLabel(p.status)}${p.icd10 ? ` · ${p.icd10}` : ''}`}
            >
              {p.condition}
            </span>
          ))}
          {problems.length === 0 && (
            <span
              style={{
                fontSize: 11.5,
                color: 'var(--fg-4)',
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
            className="qm-btn qm-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        )}
        {visitCount > 0 && (
          <a
            href={`/api/patients/${patient.id}/export`}
            className="qm-btn qm-btn-ghost"
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
  return (
    <div
      style={{
        padding: '18px 32px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        borderBottom: '1px solid var(--line)',
      }}
    >
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
              style={{
                padding: '10px 14px',
                color: active ? 'var(--fg)' : 'var(--fg-3)',
                borderBottom: `2px solid ${
                  active ? 'var(--accent-bright)' : 'transparent'
                }`,
                fontFamily: 'var(--sans)',
                fontSize: 13,
                fontWeight: 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: -1,
                textDecoration: 'none',
              }}
            >
              {t.label}
              {t.count != null && (
                <span
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    color: 'var(--fg-4)',
                  }}
                >
                  {t.count}
                </span>
              )}
            </Link>
          );
        })}
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
      createdAt: v.createdAt,
      audioDurationSec: v.audioDurationSec,
    })
  );
  return <VisitList visits={visits} />;
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
          color: 'var(--fg-3)',
          fontSize: 13,
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
        padding: '22px 32px 32px',
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
        maxWidth: 420,
        textAlign: 'center',
        color: 'var(--fg-3)',
        fontSize: 13.5,
      }}
    >
      <p style={{ margin: 0 }}>No visits for this patient yet.</p>
      {!deleted && (
        <p style={{ marginTop: 10 }}>
          <Link
            href={`/visits/new?patientId=${patientId}`}
            style={{ color: 'var(--accent-bright)', fontWeight: 500 }}
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
      }}
    >
      <div
        className="qm-sectlabel"
        style={{ marginBottom: 12 }}
      >{`§ ${title}`}</div>
      <h2
        className="qm-serif"
        style={{
          margin: 0,
          fontSize: 22,
          fontWeight: 400,
          letterSpacing: '-0.015em',
          color: 'var(--fg-2)',
        }}
      >
        Coming soon
      </h2>
      <p
        style={{
          marginTop: 10,
          fontSize: 13,
          color: 'var(--fg-3)',
          lineHeight: 1.55,
        }}
      >
        {body}
      </p>
    </div>
  );
}
