import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SpecularButton } from '@/components/specular-button';
import { VisitOrb } from '@/components/visit-orb';

export const metadata: Metadata = { title: 'Visit' };

// -- Copy that depends on the selected input mode. Centralised so T-M4/T-M5
// can swap strings (or render real components) in one place. --
const MODE_COPY: Record<string, string> = {
  audio_upload: 'Coming in T-M4: upload the visit audio here and we will start transcribing immediately.',
  voice_dictation: 'Coming in T-M5: dictate your summary into the mic and we will clean it up.',
  text_notes: 'Coming in T-M5: paste your notes and watch AI expand them into a full SOAP note.',
};

export default async function VisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, visit] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true },
    }),
    prisma.transcribeVisit.findUnique({
      where: { id },
      select: {
        id: true,
        userId: true,
        patientName: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        status: true,
      },
    }),
  ]);

  if (!user) redirect('/login');
  // 404 on both "no such visit" AND "visit belongs to another user" so
  // an attacker can't enumerate IDs to probe for existence.
  if (!visit || visit.userId !== session.user.id) notFound();

  const modeCopy = MODE_COPY[visit.inputMode] ?? 'This visit mode is not yet supported.';

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to dashboard
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          {visit.patientName && (
            <Chip>Patient: {visit.patientName}</Chip>
          )}
          <Chip>{visit.specialty}</Chip>
          {visit.chiefComplaint && <Chip>CC: {visit.chiefComplaint}</Chip>}
          <Chip>Mode: {visit.inputMode.replace(/_/g, ' ')}</Chip>
        </div>

        <div className="mt-16 flex flex-col items-center">
          <VisitOrb />

          <p className="max-w-xl text-center text-[15px] leading-relaxed text-text-secondary">
            {modeCopy}
          </p>

          <div className="mt-8">
            <SpecularButton href="/dashboard" variant="secondary" size="md">
              Back to dashboard
            </SpecularButton>
          </div>
        </div>
      </main>
    </PageWrapper>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-subtle bg-bg-surface-2 px-2.5 py-1 text-[12px] font-medium tracking-tight text-text-tertiary">
      {children}
    </span>
  );
}
