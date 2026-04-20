// ============================================================================
// Patient detail page (T-M17.2 Phase 3 Commit 8)
// ----------------------------------------------------------------------------
// Server component. Auth-guarded, practiceId-scoped with a 404 on
// mismatch (anti-enumeration — matches the /api/patients/[id] pattern).
//
// Soft-deleted patients render with a top banner; the page doesn't
// redirect so the doctor can still see the visit history for an
// archived patient. New visits for a deleted patient are prevented
// by the server action + by hiding the CTA here.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import { Download, Plus } from 'lucide-react';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SpecularButton } from '@/components/specular-button';
import { VisitCard, type VisitCardData } from '@/components/visit-card';
import { BackToDashboardLink } from '@/app/visits/[id]/back-link';
import { EditPatientDialog } from './edit-patient-dialog';
import { DeletePatientDialog } from './delete-patient-dialog';

export const metadata: Metadata = { title: 'Patient' };

function formatDob(d: Date | null): string | null {
  if (!d) return null;
  return d.toISOString().slice(0, 10);
}

function formatCreated(d: Date): string {
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default async function PatientPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { id: true, name: true, email: true, practiceId: true },
  });
  if (!user) redirect('/login');

  // Load the patient + all visits for them in one round-trip. No
  // deleted-filter on the patient itself — we still render archived
  // patients so the doctor can see their history. Visits order by
  // createdAt DESC so the timeline is newest-first.
  const patient = await prisma.transcribeMdPatient.findUnique({
    where: { id },
    select: {
      id: true,
      practiceId: true,
      name: true,
      dateOfBirth: true,
      externalId: true,
      deletedAt: true,
      createdAt: true,
      updatedAt: true,
      transcribeVisits: {
        where: {
          userId: user.id,
          // T-M17.3: default view hides trashed + archived visits. The
          // Phase 4 Commit 7 Trash tab fetches deletedAt IS NOT NULL
          // separately; this include is the Active tab's content.
          deletedAt: null,
          archivedAt: null,
        },
        orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
        select: {
          id: true,
          patientName: true,
          specialty: true,
          status: true,
          createdAt: true,
        },
      },
    },
  });
  // 404 on both "doesn't exist" and "wrong practice" — identical
  // response prevents ID enumeration.
  if (!patient || patient.practiceId !== user.practiceId) {
    notFound();
  }

  const dob = formatDob(patient.dateOfBirth);
  const isDeleted = patient.deletedAt !== null;
  const visitCount = patient.transcribeVisits.length;

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-4">
          <BackToDashboardLink />
        </div>

        {isDeleted && <DeletedBanner />}

        <PatientHeader
          id={patient.id}
          name={patient.name}
          dob={dob}
          externalId={patient.externalId}
          createdAt={patient.createdAt}
          deleted={isDeleted}
          visitCount={visitCount}
        >
          <EditPatientDialog
            patientId={patient.id}
            initialName={patient.name}
            initialDob={dob}
            initialExternalId={patient.externalId}
          />
          <DeletePatientDialog
            patientId={patient.id}
            patientName={patient.name}
            visitCount={visitCount}
          />
        </PatientHeader>

        <section className="mt-10">
          <h2 className="mb-4 type-h2 text-text-primary">Visit history</h2>
          {visitCount === 0 ? (
            <VisitsEmpty deleted={isDeleted} patientId={patient.id} />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {patient.transcribeVisits.map((v: VisitCardData) => (
                <VisitCard key={v.id} visit={v} />
              ))}
            </div>
          )}
        </section>
      </main>
    </PageWrapper>
  );
}

function DeletedBanner() {
  return (
    <div
      role="status"
      className="mb-6 rounded-lg border border-border-subtle bg-bg-surface-1/50 px-4 py-3 text-[13px] text-text-tertiary"
    >
      This patient has been deleted. Visits below remain accessible,
      but new visits can&apos;t be added.
    </div>
  );
}

function PatientHeader({
  id,
  name,
  dob,
  externalId,
  createdAt,
  deleted,
  visitCount,
  children,
}: {
  id: string;
  name: string;
  dob: string | null;
  externalId: string | null;
  createdAt: Date;
  deleted: boolean;
  visitCount: number;
  /** Edit + Delete dialog buttons are client components passed in by
   *  the server parent. Kept as children so the header stays a pure
   *  server component (no 'use client' contagion). */
  children: React.ReactNode;
}) {
  const initial = name.charAt(0).toUpperCase() || '?';
  return (
    <div className="rounded-2xl border border-border-default bg-bg-surface-1/60 p-6">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4 min-w-0">
          <div
            aria-hidden
            className="flex h-14 w-14 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_50%,#A855F7_100%)] text-[22px] font-semibold text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
          >
            {initial}
          </div>
          <div className="min-w-0">
            <h1 className="type-h1 text-text-primary">{name}</h1>
            <dl className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px] text-text-tertiary">
              <div className="flex items-center gap-1.5">
                <dt className="text-text-muted">DOB</dt>
                <dd className={dob ? 'text-text-secondary' : 'text-text-muted italic'}>
                  {dob ?? 'No DOB on file'}
                </dd>
              </div>
              {externalId && (
                <div className="flex items-center gap-1.5">
                  <dt className="text-text-muted">ID</dt>
                  <dd className="text-text-secondary">{externalId}</dd>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <dt className="text-text-muted">Created</dt>
                <dd className="text-text-secondary">
                  {formatCreated(createdAt)}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!deleted && (
            <SpecularButton
              href={`/visits/new?patientId=${id}`}
              variant="primary"
              size="sm"
            >
              <Plus className="h-3.5 w-3.5" />
              New visit
            </SpecularButton>
          )}
          {visitCount > 0 && (
            <a
              href={`/api/patients/${id}/export`}
              className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-2/70 hover:border-border-emphasis focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
            >
              <Download className="h-3.5 w-3.5" aria-hidden />
              Export visits
            </a>
          )}
          {children}
        </div>
      </div>
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
    <div className="rounded-xl border border-border-subtle bg-bg-surface-1/40 px-6 py-10 text-center">
      <p className="text-[14px] text-text-tertiary">
        No visits for this patient yet.
      </p>
      {!deleted && (
        <p className="mt-3 text-[13px] text-text-muted">
          <Link
            href={`/visits/new?patientId=${patientId}`}
            className="font-medium text-violet-300 hover:text-violet-200"
          >
            Start a new visit
          </Link>
          .
        </p>
      )}
    </div>
  );
}
