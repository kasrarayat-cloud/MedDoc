import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SpecialtyDropdown } from '@/components/specialty-dropdown';
import { createVisitAction } from '@/actions/visits';
import { SPECIALTIES } from '@/lib/specialties';
import { ModeTileWithForm } from './mode-tile-with-form';

export const metadata: Metadata = { title: 'New visit' };

export default async function NewVisitPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, mostRecentVisit] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true },
    }),
    prisma.transcribeVisit.findFirst({
      where: { userId: session.user.id },
      orderBy: { createdAt: 'desc' },
      select: { specialty: true },
    }),
  ]);
  if (!user) redirect('/login');

  const specialties = SPECIALTIES;

  // Fresh signups have no prior visit — fall back to the first specialty
  // in the catalog so the hidden-input value is never empty. A blank
  // specialty made it to the server, failed Zod's min(1), and surfaced
  // as a 500 ("Invalid visit input") when the user clicked a mode tile
  // without opening the dropdown.
  const defaultSpecialty =
    mostRecentVisit?.specialty ?? SPECIALTIES[0]?.displayName ?? '';

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-8">
          <h1 className="type-h1 text-text-primary">Start a new visit</h1>
          <p className="mt-2 text-[14px] text-text-tertiary">
            Add optional context, then pick how you want to capture the encounter.
          </p>
        </div>

        <form
          id="new-visit-form"
          action={createVisitAction}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2"
        >
          <div>
            <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
              Patient name{' '}
              <span className="font-normal text-text-muted">(optional)</span>
            </label>
            <input
              name="patientName"
              type="text"
              className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              placeholder="e.g. Jane Doe"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
              Specialty
            </label>
            <SpecialtyDropdown
              options={specialties}
              name="specialty"
              defaultValue={defaultSpecialty}
            />
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
              Chief complaint{' '}
              <span className="font-normal text-text-muted">(optional)</span>
            </label>
            <input
              name="chiefComplaint"
              type="text"
              className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              placeholder="e.g. Headache for 3 days"
            />
          </div>
        </form>

        <div className="mt-10">
          <div className="mb-4 text-[13px] font-medium tracking-tight text-text-tertiary">
            Pick a capture mode
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* Each ModeTile is its own submit button INSIDE the form above,
                targeting it via the `form` attribute. Clicking sends the
                form data + the chosen inputMode=<value> and the server
                action creates the visit then redirects to /visits/[id]. */}
            <ModeTileWithForm
              formId="new-visit-form"
              icon="mic"
              title="Upload audio"
              description="Record your visit on your phone, then drop the file here."
              value="audio_upload"
            />
            <ModeTileWithForm
              formId="new-visit-form"
              icon="radio"
              title="Dictate live"
              description="Speak a summary into your mic — we'll clean it up."
              value="voice_dictation"
            />
            <ModeTileWithForm
              formId="new-visit-form"
              icon="pen-line"
              title="Text to SOAP"
              description="Type bullets — AI expands them into a full note."
              value="text_notes"
            />
          </div>
        </div>
      </main>
    </PageWrapper>
  );
}
