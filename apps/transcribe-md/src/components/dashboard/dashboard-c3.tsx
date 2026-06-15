// ============================================================================
// Dashboard — C3 "calm, one-clear-action" skin (Stage 1, flag-gated).
// ----------------------------------------------------------------------------
// Renders ONLY when NEXT_PUBLIC_SKIN_BETA is on (see dashboard/page.tsx). The
// single focus is the "Ready to sign" inbox (the doctor's real do-this-next);
// the 4 vanity stat cards collapse to one quiet line; the duplicate
// Patients/All-visits tabs are gone (Patients lives in the nav). One glance =
// what to do next.
//
// SKIN-ONLY: this is a re-layout. Every query below is READ-ONLY and mirrors
// the reads the existing dashboard already runs (same Prisma selects, same
// user-scoping, same fire-and-forget audit row). No server action, gate, or
// pipeline behavior changes. Visit rows link to the EXISTING /visits/[id].
// ============================================================================
import Link from 'next/link';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { logAudit } from '@/lib/audit';
import { Greeting } from './greeting';
import { c3Status } from '@/lib/visit-status-c3';
import { DashboardInboxC3 } from './dashboard-inbox-c3';
import {
  C3_INBOX_PAGE_SIZE,
  type C3InboxCursor,
  type C3InboxRow,
} from '@/lib/c3-list-pagination';

const INPROGRESS_LIMIT = 10;

const PROCESSING_STATUSES: TranscribeVisitStatus[] = [
  TranscribeVisitStatus.QUEUED,
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

type Row = {
  id: string;
  patientName: string | null;
  specialty: string;
  status: TranscribeVisitStatus;
  needsReview: boolean;
  chiefComplaint: string | null;
  updatedAt: Date;
  patient: { name: string } | null;
};

const ROW_SELECT = {
  id: true,
  patientName: true,
  specialty: true,
  status: true,
  needsReview: true,
  chiefComplaint: true,
  updatedAt: true,
  patient: { select: { name: true } },
};

export async function DashboardC3Body({
  userId,
  userName,
}: {
  userId: string;
  userName: string | null;
}) {
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const startOfWeek = (() => {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    const dow = d.getDay();
    d.setDate(d.getDate() + (dow === 0 ? -6 : 1 - dow));
    return d;
  })();

  const inboxWhere = {
    userId,
    deletedAt: null,
    archivedAt: null,
    status: TranscribeVisitStatus.READY,
    signedAt: null,
  };

  const [inboxRaw, inboxTotal, inProgress, visitsThisMonth, signedThisWeek] =
    await Promise.all([
      // First inbox page (+1 to derive the cursor). The rest streams in via
      // the read-only searchInboxAction — the list never renders all rows.
      prisma.transcribeVisit.findMany({
        where: inboxWhere,
        orderBy: [{ updatedAt: 'desc' }, { id: 'desc' }],
        take: C3_INBOX_PAGE_SIZE + 1,
        select: ROW_SELECT,
      }) as Promise<Row[]>,
      prisma.transcribeVisit.count({ where: inboxWhere }),
      prisma.transcribeVisit.findMany({
        where: { userId, deletedAt: null, archivedAt: null, status: { in: PROCESSING_STATUSES } },
        orderBy: { updatedAt: 'desc' },
        take: INPROGRESS_LIMIT,
        select: ROW_SELECT,
      }) as Promise<Row[]>,
      prisma.transcribeVisit.count({ where: { userId, deletedAt: null, createdAt: { gte: startOfMonth } } }),
      prisma.transcribeVisit.count({ where: { userId, status: TranscribeVisitStatus.SIGNED, signedAt: { gte: startOfWeek } } }),
    ]);

  const inboxHasMore = inboxRaw.length > C3_INBOX_PAGE_SIZE;
  const inboxPage = inboxHasMore ? inboxRaw.slice(0, C3_INBOX_PAGE_SIZE) : inboxRaw;
  const inboxRows: C3InboxRow[] = inboxPage.map((v) => ({
    id: v.id,
    patientName: v.patient?.name ?? v.patientName,
    specialty: v.specialty,
    status: v.status,
    needsReview: v.needsReview,
    chiefComplaint: v.chiefComplaint,
  }));
  const inboxLast = inboxPage[inboxPage.length - 1];
  const inboxCursor: C3InboxCursor | null =
    inboxHasMore && inboxLast
      ? { updatedAt: inboxLast.updatedAt.toISOString(), id: inboxLast.id }
      : null;

  // Same fire-and-forget §164.312(b) audit row as the existing dashboard.
  void logAudit({
    action: 'VIEWED_DASHBOARD',
    targetType: 'User',
    targetId: userId,
    metadata: { source: 'rsc:/dashboard:c3', toSign: inboxTotal, inProgress: inProgress.length },
  });

  const firstName = userName ? (userName.trim().split(/\s+/)[0] ?? null) : null;
  const subtitle = (
    <>
      {visitsThisMonth} visit{visitsThisMonth === 1 ? '' : 's'} this month · {signedThisWeek} signed this week
    </>
  );

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '22px 24px 80px' }}>
      <Greeting firstName={firstName} subtitle={subtitle} />

      <Section title="Ready to sign" count={inboxTotal} style={{ marginTop: 26 }}>
        {inboxTotal === 0 ? (
          <EmptyInbox />
        ) : (
          <DashboardInboxC3
            initialRows={inboxRows}
            initialCursor={inboxCursor}
            total={inboxTotal}
          />
        )}
      </Section>

      {inProgress.length > 0 && (
        <Section title="In progress" count={inProgress.length} style={{ marginTop: 26, opacity: 0.9 }}>
          <div className="qm-c3-list">
            {inProgress.map((v) => (
              <VisitRow key={v.id} v={v} interactive />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  style,
  children,
}: {
  title: string;
  count: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <section style={style} aria-label={title}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            fontWeight: 500,
          }}
        >
          {title}
        </h2>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--color-linear-text-3)',
            background: 'var(--color-linear-surface-2)',
            border: '1px solid var(--color-linear-border)',
            borderRadius: 999,
            padding: '0 7px',
            lineHeight: '17px',
          }}
        >
          {count}
        </span>
      </div>
      {children}
    </section>
  );
}

function VisitRow({ v, interactive }: { v: Row; interactive?: boolean }) {
  const s = c3Status(v.status, v.needsReview);
  const name = v.patient?.name ?? v.patientName ?? 'Unknown patient';
  const meta = [v.specialty, v.chiefComplaint?.replace(/\s+/g, ' ').trim()].filter(Boolean).join(' · ');
  const inner = (
    <>
      <span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <span style={{ fontSize: 13.5, color: 'var(--color-linear-text)', fontWeight: 500 }}>{name}</span>
        {meta && (
          <span style={{ fontSize: 12, color: 'var(--color-linear-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {meta}
          </span>
        )}
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 'none' }}>
        <span className={s.pillClass}>{s.label}</span>
        {interactive && <span aria-hidden style={{ color: 'var(--color-linear-text-3)', fontSize: 13 }}>→</span>}
      </span>
    </>
  );
  return (
    <Link href={`/visits/${v.id}`} className="qm-c3-row qm-tap-44" style={{ textDecoration: 'none' }}>
      {inner}
    </Link>
  );
}

function EmptyInbox() {
  return (
    <div
      style={{
        padding: '26px 18px',
        textAlign: 'center',
        border: '1px solid var(--color-linear-border)',
        borderRadius: 11,
        background: 'var(--color-linear-surface-1)',
      }}
    >
      <span aria-hidden style={{ color: 'var(--color-linear-sage-bright)', fontSize: 15 }}>✓</span>
      <p style={{ margin: '8px 0 0', fontSize: 13.5, color: 'var(--color-linear-text-2)' }}>You’re all caught up.</p>
      <Link
        href="/visits/new"
        className="qm-lin-btn-primary"
        style={{ marginTop: 16, textDecoration: 'none', height: 32, padding: '0 14px', fontSize: 13 }}
      >
        Start a visit
      </Link>
    </div>
  );
}
