// ============================================================================
// Patient detail.
// ----------------------------------------------------------------------------
// /patients/[id]               → Visits tab (default)
// /patients/[id]?tab=notes     → Notes stub (Gate 13 or later)
// /patients/[id]?tab=files     → Files stub
// /patients/[id]?tab=trash     → Trash tab (only shown when trashCount > 0)
//
// Full shell (TopNav + IconRail + scrollable main) via AppFrame. Visit
// history uses the Gate-6 <VisitList> component. Problem list chips
// sit on the header with a [Manage] drawer; MRN + insurance are
// editable through the existing Edit dialog.
//
// Phase 5 (Linear V1 Faithful) — chrome rendered against the dark
// canvas. AppFrame + StatCard + Avatar + VisitList already migrated in
// Stage 2.5 and we still pass `theme="clinician"` for caller-site
// compatibility on the components Subagent 2/3 own. Server-side data
// fetches (auth, prisma queries, redirects, RBAC scope) are unchanged.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { isSkinBeta } from '@/config/skin-beta';
import { isSkinRounds } from '@/config/skin-rounds';
import { RoundsNewVisitCta } from '@/components/rounds/new-visit-cta';
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

/** Map the canonical problem-list status onto Linear V1 chip tones. */
function problemTone(status: ProblemStatus): {
  bg: string;
  fg: string;
  dot: string;
} {
  switch (status) {
    case 'active':
      return {
        bg: 'rgba(212, 164, 55, 0.15)',
        fg: 'var(--color-linear-warning)',
        dot: 'var(--color-linear-warning)',
      };
    case 'resolved':
      return {
        bg: 'var(--color-linear-sage-tint)',
        fg: 'var(--color-linear-sage-bright)',
        dot: 'var(--color-linear-sage)',
      };
    case 'chronic':
      return {
        bg: 'var(--color-linear-surface-2)',
        fg: 'var(--color-linear-text-2)',
        dot: 'var(--color-linear-text-3)',
      };
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

  // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Single
  // patient detail RSC. Audited at the page-level fetch boundary.
  void logAudit({
    action: 'VIEWED_PATIENT_FILE',
    targetId: patient.id,
    targetType: 'TranscribeMdPatient',
    metadata: { source: 'rsc:/patients/[id]' },
  });

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
        select: { id: true, createdAt: true, specialty: true },
      }),
    ]);

  const activeTab = resolveTab(tabParam, trashCount);
  const dob = patient.dateOfBirth;
  const dobIso = formatDob(dob);
  const isDeleted = patient.deletedAt !== null;
  const problems = parseProblemList(patient.problemList);

  // ── C3 calm-skin patient detail (Stage 2, flag-gated) ─────────────────────
  // SKIN-ONLY: identical auth + Prisma reads + audit row above; this is a
  // re-layout. The 4 vanity stat tiles collapse to one quiet line, the dead
  // "Coming soon" Notes/Files tabs are dropped, and the page resolves to a
  // calm header (ONE "New visit" primary + "Open last note") over the SAME
  // <VisitsTab>/<TrashTab>/dialogs the legacy view renders. Flag OFF → the
  // existing tabbed layout below runs, byte-identical.
  if (isSkinBeta()) {
    // R3.2 — the Rounds fork of this layout. Beta and Rounds are different
    // flags; only the latter guarantees the tokens these controls resolve.
    const roundsSkin = isSkinRounds();
    const age = dob ? yearsFrom(dob) : null;
    const metaBits = [
      dobIso ? `DOB ${dobIso}${age != null ? ` (${age})` : ''}` : null,
      patient.mrn ? `MRN ${patient.mrn}` : null,
      patient.externalId ? `ID ${patient.externalId}` : null,
      patient.insurance ?? null,
    ].filter(Boolean) as string[];

    return (
      <AppFrame>
        <div className="flex items-center gap-2 px-6 pt-5 text-[13px] text-linear-text-3 sm:px-10">
          <Link
            href="/patients"
            className="text-linear-text-3 no-underline hover:text-linear-text-2"
          >
            Patients
          </Link>
          <Ic.chevRight width={12} height={12} />
          <span className="font-medium text-linear-text">{patient.name}</span>
        </div>

        {isDeleted && <DeletedBanner />}

        {/* Calm header — identity + the few facts at a glance + ONE primary. */}
        <div className="flex flex-col gap-5 border-b border-linear-border px-6 pb-7 pt-5 sm:px-10 lg:flex-row lg:items-start">
          <div className="flex min-w-0 flex-1 items-start gap-5">
            <Avatar name={patient.name} size={64} theme="clinician" />
            <div className="min-w-0 flex-1">
              <h1 className="m-0 text-[26px] font-semibold leading-tight tracking-tight text-linear-text">
                {patient.name}
              </h1>
              {metaBits.length > 0 ? (
                <p className="mt-2 font-mono text-[12.5px] text-linear-text-3">
                  {metaBits.join('  ·  ')}
                </p>
              ) : (
                <p className="mt-2 font-mono text-[12.5px] italic text-linear-text-3">
                  No MRN / DOB / insurance on file — edit to add
                </p>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {problems.map((p, i) => {
                  const tone = problemTone(p.status);
                  return (
                    <span
                      key={`${p.condition}-${i}`}
                      className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.05em]"
                      style={{ background: tone.bg, color: tone.fg }}
                      title={`${statusLabel(p.status)}${p.icd10 ? ` · ${p.icd10}` : ''}`}
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: tone.dot }}
                      />
                      {p.condition}
                    </span>
                  );
                })}
                {problems.length === 0 && (
                  <span className="font-mono text-[12px] text-linear-text-3">
                    No problem list yet.
                  </span>
                )}
                {/* R3.2 — the problem-list affordance. Item 2 names it as part
                    of the identity header, and the census found its trigger
                    still on `qm-lin-btn`: the LAST legacy class on this route.
                    Hosted rather than restyled, for the same reason as the
                    action row — the dialog inside it is Radix + `linear-*`
                    utilities, so the bridge retints the trigger and the panel
                    together, and a hand-restyle of the trigger alone would
                    leave the panel behind. */}
                <span className="qm-rounds-host">
                  <ProblemListDialog
                    patientId={patient.id}
                    initialProblemList={patient.problemList}
                  />
                </span>
              </div>
            </div>
          </div>

          {/* ── R3.2 — THE ACTION ROW, REBUILT IN ROUNDS CONTROLS ─────────────
              Three things changed and each was a finding, not a preference:

              1. The primary was `qm-lin-btn-primary` — the LEGACY SAGE the
                 census flagged on this route. It is the shared Rounds CTA now,
                 the same component the board and the roster mount, so the label
                 and the destination cannot drift between three surfaces.
              2. DELETE WAS A PEER OF EXPORT. A control that destroys a
                 patient's record sat in a flat row beside "Export" and "Edit",
                 one mis-click from a surface whose job is careful review — the
                 same reasoning that moved "Visit actions" off the stage foot in
                 R2. It is in a quiet `<details>` overflow now, closed by
                 default, keyboard-operable and screen-reader-announced with no
                 JavaScript.
              3. The remaining actions take `.qm-rounds-btn-secondary` rather
                 than `qm-lin-btn`.

              ⚠️ FORKED ON `isSkinRounds()`, NOT ON `isSkinBeta()`. This whole
              branch is the skin-beta layout, and in production skin-beta is on
              wherever Rounds is — but they are different flags, and a build with
              beta and without Rounds would otherwise get Rounds controls with no
              Rounds tokens behind them. */}
          {/* ⚠️ `qm-rounds-host` ON THIS ROW IS LOAD-BEARING, not decoration.
              The Edit and Delete triggers are Radix dialogs styled with Tailwind
              `linear-*` utilities — including a `ring-linear-sage/40` focus
              ring, i.e. the legacy sage, on controls this round is meant to
              de-legacy. Those resolve custom properties, so the bridge retints
              all of them at once; restyling two dialog triggers by hand would
              leave the next one to be found later.
              It is also an island the CENSUS CANNOT SEE — its colour arm samples
              color/background/border, not ring. Named in the report rather than
              left implicit. */}
          {roundsSkin ? (
            <div className="qm-rounds-host qm-rounds-pdetail-actions">
              {!isDeleted && <RoundsNewVisitCta variant="bar" />}
              {latestVisit && (
                <Link
                  href={`/visits/${latestVisit.id}`}
                  className="qm-rounds-btn-secondary"
                  style={{ textDecoration: 'none' }}
                >
                  Open last note
                </Link>
              )}
              <EditPatientDialog
                patientId={patient.id}
                initialName={patient.name}
                initialDob={dobIso}
                initialExternalId={patient.externalId}
                initialMrn={patient.mrn}
                initialInsurance={patient.insurance}
              />
              {activeCount > 0 && (
                <a
                  href={`/api/patients/${patient.id}/export`}
                  className="qm-rounds-btn-secondary"
                  style={{ textDecoration: 'none' }}
                >
                  <Ic.download width={13} height={13} />
                  Export
                </a>
              )}
              <details
                className="qm-rounds-overflow"
                data-testid="rounds-patient-overflow"
              >
                <summary className="qm-rounds-overflow-summary">
                  Patient actions
                </summary>
                <div className="qm-rounds-overflow-body">
                  <DeletePatientDialog
                    patientId={patient.id}
                    patientName={patient.name}
                    visitCount={activeCount}
                  />
                </div>
              </details>
            </div>
          ) : (
          <div className="flex flex-wrap items-center gap-2">
            {!isDeleted && (
              <Link
                href={`/visits/new?patientId=${patient.id}`}
                className="qm-lin-btn-primary"
                style={{ textDecoration: 'none' }}
              >
                <Ic.plus width={14} height={14} />
                New visit
              </Link>
            )}
            {latestVisit && (
              <Link
                href={`/visits/${latestVisit.id}`}
                className="qm-lin-btn"
                style={{ textDecoration: 'none' }}
              >
                Open last note
              </Link>
            )}
            <EditPatientDialog
              patientId={patient.id}
              initialName={patient.name}
              initialDob={dobIso}
              initialExternalId={patient.externalId}
              initialMrn={patient.mrn}
              initialInsurance={patient.insurance}
            />
            {activeCount > 0 && (
              <a
                href={`/api/patients/${patient.id}/export`}
                className="qm-lin-btn"
                style={{ textDecoration: 'none' }}
              >
                <Ic.download width={13} height={13} />
                Export
              </a>
            )}
            <DeletePatientDialog
              patientId={patient.id}
              patientName={patient.name}
              visitCount={activeCount}
            />
          </div>
          )}
        </div>

        {/* Quiet one-line summary — replaces the 4 vanity stat cards. */}
        <div className="px-6 pt-4 font-mono text-[12px] text-linear-text-3 sm:px-10">
          {activeCount} visit{activeCount === 1 ? '' : 's'}
          {' · '}
          {signedCount} signed
          {latestVisit && (
            <>
              {' · '}last {relTime(latestVisit.createdAt)}
            </>
          )}
          {' · '}
          {visitsThisMonth} this {now.toLocaleString('en-US', { month: 'short' })}
        </div>

        {/* Visits — the calm primary list. */}
        <section aria-labelledby="c3-pt-visits" className="pt-3">
          <div className="flex items-center gap-2 px-6 pb-1 sm:px-10">
            <h2
              id="c3-pt-visits"
              className="m-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
            >
              Visits
            </h2>
            <span className="font-mono text-[11px] tabular-nums text-linear-text-3">
              {activeCount}
            </span>
          </div>
          {activeCount === 0 ? (
            <VisitsEmpty deleted={isDeleted} patientId={patient.id} />
          ) : (
            <VisitsTab patientId={patient.id} userId={user.id} />
          )}
        </section>

        {/* Deleted visits — shown only when present; no dead tab. */}
        {trashCount > 0 && (
          <section aria-labelledby="c3-pt-trash" className="pt-4">
            <div className="flex items-center gap-2 px-6 pb-1 sm:px-10">
              <h2
                id="c3-pt-trash"
                className="m-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                Deleted
              </h2>
              <span className="font-mono text-[11px] tabular-nums text-linear-text-3">
                {trashCount}
              </span>
            </div>
            <TrashTab patientId={patient.id} userId={user.id} />
          </section>
        )}
      </AppFrame>
    );
  }

  return (
    <AppFrame>
      <div className="flex items-center gap-2 px-10 pt-5 text-[13px] text-linear-text-3">
        <Link href="/patients" className="text-linear-text-3 no-underline hover:text-linear-text-2">
          Patients
        </Link>
        <Ic.chevRight width={12} height={12} />
        <span className="font-medium text-linear-text">{patient.name}</span>
      </div>

      {isDeleted && <DeletedBanner />}

      <PatientHeaderCard
        patient={patient}
        problems={problems}
        dobIso={dobIso}
        age={dob ? yearsFrom(dob) : null}
        visitCount={activeCount}
      />

      <div className="grid grid-cols-1 gap-4 px-10 py-6 sm:grid-cols-2 lg:grid-cols-4">
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
              <span className="capitalize">{latestVisit.specialty}</span>
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
      className="mx-10 mt-5 rounded-lg border border-linear-border bg-linear-surface-1 px-4 py-3 text-[13px] text-linear-text-3"
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
  const isDeleted = patient.deletedAt !== null;
  const canNewVisit = !isDeleted;

  return (
    <div className="flex items-start gap-6 border-b border-linear-border px-10 pb-7 pt-5">
      <Avatar name={patient.name} size={76} theme="clinician" />
      <div className="min-w-0 flex-1">
        <h1 className="m-0 text-[28px] font-semibold leading-tight tracking-tight text-linear-text">
          {patient.name}
        </h1>
        <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[12.5px] text-linear-text-3">
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
            <span className="italic text-linear-text-3">
              No MRN / DOB / insurance on file — edit to add
            </span>
          )}
        </div>

        <div className="mt-3.5 flex flex-wrap items-center gap-2">
          {problems.map((p, i) => {
            const tone = problemTone(p.status);
            return (
              <span
                key={`${p.condition}-${i}`}
                className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.05em]"
                style={{ background: tone.bg, color: tone.fg }}
                title={`${statusLabel(p.status)}${p.icd10 ? ` · ${p.icd10}` : ''}`}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: tone.dot }}
                />
                {p.condition}
              </span>
            );
          })}
          {problems.length === 0 && (
            <span className="font-mono text-[12px] text-linear-text-3">
              No problem list yet.
            </span>
          )}
          <ProblemListDialog
            patientId={patient.id}
            initialProblemList={patient.problemList}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {canNewVisit && (
          <Link
            href={`/visits/new?patientId=${patient.id}`}
            className="qm-lin-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Ic.plus width={14} height={14} />
            New visit
          </Link>
        )}
        {visitCount > 0 && (
          <a
            href={`/api/patients/${patient.id}/export`}
            className="qm-lin-btn"
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
    <nav className="flex items-center gap-1 border-b border-linear-border px-10">
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
              className={
                '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-[13px] font-medium no-underline transition-colors ' +
                (active
                  ? 'border-linear-sage text-linear-text'
                  : 'border-transparent text-linear-text-3 hover:text-linear-text-2')
              }
            >
              {t.label}
              {t.count != null && (
                <span
                  className={
                    'font-mono text-[11px] tabular-nums ' +
                    (active ? 'text-linear-sage-bright' : 'text-linear-text-3')
                  }
                >
                  {t.count}
                </span>
              )}
            </Link>
          );
        })}
    </nav>
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
      <div className="mx-auto my-16 max-w-[420px] text-center text-[13.5px] text-linear-text-3">
        No deleted visits.
      </div>
    );
  }
  return (
    <div
      className="grid gap-3.5 px-10 pb-10 pt-6"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}
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
    <div className="mx-auto my-16 max-w-[440px] text-center text-[14px] leading-relaxed text-linear-text-3">
      <p className="m-0">No visits for this patient yet.</p>
      {!deleted && (
        <p className="mt-3">
          <Link
            href={`/visits/new?patientId=${patientId}`}
            className="font-medium text-linear-sage-bright no-underline hover:underline"
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
    <div className="mx-auto my-16 max-w-[480px] px-6 text-center">
      <div className="mb-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-linear-text-3">
        {title}
      </div>
      <h2 className="m-0 text-[24px] font-semibold tracking-tight text-linear-text">
        Coming soon
      </h2>
      <p className="mx-auto mt-3 max-w-[380px] text-[14px] leading-relaxed text-linear-text-2">
        {body}
      </p>
    </div>
  );
}
