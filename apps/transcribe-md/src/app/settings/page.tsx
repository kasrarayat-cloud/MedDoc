import type { Metadata } from 'next';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import { FileText, ArrowRight } from 'lucide-react';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { getCurrentSessionId } from '@/lib/auth';
import { describeUserAgent, describeIpLocation, parseUserAgent } from '@/lib/fingerprint';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { Suspense } from 'react';
import { ProfileForm } from './profile-form';
import { SessionPanel } from './session-panel';
import { DeleteAccountDialog } from './delete-account-dialog';
import { ChangePasswordForm } from './change-password-form';
import { ChangeEmailDialog } from './change-email-dialog';
import { EmailChangeToast } from './email-change-toast';
import { isDataExportEnabled } from '../api/settings/export-data/route';

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

  const [user, sessionId] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        name: true,
        email: true,
        createdAt: true,
      },
    }),
    getCurrentSessionId(),
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
        <Suspense fallback={null}>
          <EmailChangeToast />
        </Suspense>
        <h1 className="type-h1 text-text-primary">Settings</h1>

        {/* Profile */}
        <section className="mt-10">
          <SectionHeader
            title="Profile"
            description="Your name is how you'll be addressed in the app."
          />
          <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            <ProfileForm defaultName={user.name ?? ''} />
            <div className="mt-6 grid grid-cols-1 gap-3 border-t border-border-subtle pt-5 sm:grid-cols-2">
              <EmailWithChangeButton email={user.email} />
              <ReadOnlyRow label="Member since" value={formatDate(user.createdAt)} />
            </div>
          </div>
        </section>

        {/* Security (T-M16.2) */}
        <section className="mt-10">
          <SectionHeader
            title="Security"
            description="Change your password. Other devices are signed out — this one stays."
          />
          <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            <ChangePasswordForm />
          </div>
        </section>

        {/* Templates (T-M24) */}
        <section className="mt-10">
          <SectionHeader
            title="Templates"
            description="Upload your own SOAP template (.docx) — we fill it with AI-generated content on every visit that uses it."
          />
          <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            <Link
              href="/settings/templates"
              className="group flex items-center justify-between gap-4"
            >
              <div className="flex items-start gap-3">
                <div
                  aria-hidden
                  className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-violet-500/10 text-violet-300"
                >
                  <FileText className="h-4 w-4" aria-hidden />
                </div>
                <div>
                  <div className="text-[14px] font-medium text-text-primary">
                    Manage your templates
                  </div>
                  <div className="mt-0.5 text-[12px] text-text-tertiary">
                    Upload, preview, and delete templates.
                  </div>
                </div>
              </div>
              <ArrowRight
                className="h-4 w-4 flex-none text-text-muted transition-colors group-hover:text-text-primary"
                aria-hidden
              />
            </Link>
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

        {/* Your data (T-M16.2) */}
        {isDataExportEnabled() && (
          <section className="mt-10">
            <SectionHeader
              title="Your data"
              description="Download a ZIP containing every visit, transcript, SOAP note, audio file, and signed PDF we have for your account."
            />
            <div className="mt-6 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-[13px] leading-relaxed text-text-secondary">
                  <p>
                    The export includes visit metadata as JSON, original
                    audio files, signed PDFs, and your per-doctor edit
                    patterns. No passwords or MFA secrets.
                  </p>
                  <p className="mt-2 text-text-tertiary">
                    Large exports can take up to five minutes. Your browser
                    will start the download as bytes become available.
                  </p>
                </div>
                <a
                  href="/api/settings/export-data"
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-[13px] font-medium text-violet-200 hover:bg-violet-500/15 hover:border-violet-500/60 transition-colors"
                >
                  Export my data
                </a>
              </div>
            </div>
          </section>
        )}

        {/* Danger zone */}
        <section className="mt-10">
          <SectionHeader
            title="Danger zone"
            description="Deleting your account is permanent. We erase every visit, transcript, and exported file."
          />
          <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/5 p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="text-[13px] leading-relaxed text-text-secondary">
                <p>
                  This removes your account and all associated data from
                  our servers. A compliance record (email, deletion date,
                  visit count) is kept for 90 days and then purged.
                </p>
                <p className="mt-2 text-text-tertiary">
                  You&apos;ll be asked to re-enter your password and type
                  DELETE to confirm.
                </p>
              </div>
              <div className="shrink-0">
                <DeleteAccountDialog />
              </div>
            </div>
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

function EmailWithChangeButton({ email }: { email: string }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
          Email
        </div>
        <ChangeEmailDialog currentEmail={email} />
      </div>
      <div className="mt-1 text-[13px] text-text-secondary break-all">{email}</div>
    </div>
  );
}
