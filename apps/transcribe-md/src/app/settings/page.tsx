import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { getCurrentSessionId } from '@/lib/auth';
import { describeUserAgent, describeIpLocation, parseUserAgent } from '@/lib/fingerprint';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { ProfileForm } from './profile-form';
import { SessionPanel } from './session-panel';

export const metadata: Metadata = { title: 'Settings' };

function formatDate(d: Date): string {
  return d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function relativeAgo(d: Date): string {
  const diff = Date.now() - d.getTime();
  const min = Math.max(0, Math.floor(diff / 60_000));
  if (min < 1) return 'just now';
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const days = Math.floor(hr / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

export default async function SettingsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, specialties, sessionId, mostRecentVisit] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        name: true,
        email: true,
        createdAt: true,
      },
    }),
    prisma.scribeSpecialtyTemplate.findMany({
      where: { active: true },
      orderBy: { displayName: 'asc' },
      select: { slug: true, displayName: true },
    }),
    getCurrentSessionId(),
    prisma.transcribeVisit.findFirst({
      where: { userId: session.user.id },
      orderBy: { createdAt: 'desc' },
      select: { specialty: true },
    }),
  ]);
  if (!user) redirect('/login');

  // Look up the live UserSession row so we can show IP / UA / timestamps.
  // A null `sessionId` means a legacy (pre-T-M2) token — display a nudge.
  const activeSession = sessionId
    ? await prisma.userSession.findUnique({
        where: { sessionToken: sessionId },
      })
    : null;

  const { browser, os } = parseUserAgent(activeSession?.userAgent ?? null);
  void describeUserAgent; // kept for potential future inline usage

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-3xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <h1 className="type-h1 text-text-primary">Settings</h1>

        {/* Profile */}
        <section className="mt-10">
          <SectionHeader
            title="Profile"
            description="Your name is how you'll be addressed in the app."
          />
          <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            <ProfileForm
              defaultName={user.name ?? ''}
              defaultSpecialty={mostRecentVisit?.specialty ?? ''}
              specialties={specialties}
            />
            <div className="mt-6 grid grid-cols-1 gap-3 border-t border-border-subtle pt-5 sm:grid-cols-2">
              <ReadOnlyRow label="Email" value={user.email} />
              <ReadOnlyRow label="Member since" value={formatDate(user.createdAt)} />
            </div>
          </div>
        </section>

        {/* Active Session */}
        <section className="mt-10">
          <SectionHeader
            title="Active session"
            description="One device at a time. Signing in elsewhere revokes this session automatically."
          />
          <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            {activeSession ? (
              <SessionPanel
                ipAddress={activeSession.ipAddress}
                browser={browser}
                os={os}
                locationLabel={describeIpLocation(activeSession.ipAddress)}
                loggedInAt={formatDate(activeSession.createdAt)}
                expiresAt={formatDate(activeSession.expiresAt)}
                lastActiveAt={relativeAgo(activeSession.lastActiveAt)}
              />
            ) : (
              <div className="text-[13px] text-text-tertiary">
                Your current session predates the single-device enforcement
                rollout. Sign out and back in to enable it.
              </div>
            )}
          </div>
        </section>
      </main>
    </PageWrapper>
  );
}

function SectionHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div>
      <h2 className="type-h2 text-text-primary">{title}</h2>
      <p className="mt-1 text-[13px] text-text-tertiary">{description}</p>
    </div>
  );
}

function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className="mt-1 text-[13px] text-text-secondary break-all">{value}</div>
    </div>
  );
}
