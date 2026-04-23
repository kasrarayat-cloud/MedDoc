// ============================================================================
// Settings — app-redesign-v1 (HANDOFF §2.2 Gate 12).
// ----------------------------------------------------------------------------
// Full redesign shell with sticky left index + stacked Section cards.
// Preserves all existing T-M16.2 / T-M17.3 form behaviour: profile,
// password, email change, session status, data export, account delete.
// New: clinician profile fields (specialty / NPI / clinic / timezone)
// land in the Profile section; 2FA + multi-session UI are scaffolded
// as "Coming soon" stubs since the backend wiring (otplib, session
// list endpoints) is a Gate 14 item.
// ============================================================================

import type { Metadata } from 'next';
import { Suspense } from 'react';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { getCurrentSessionId } from '@/lib/auth';
import {
  describeIpLocation,
  parseUserAgent,
} from '@/lib/fingerprint';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
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

const SECTIONS = [
  { id: 'profile', label: 'Profile' },
  { id: 'security', label: 'Security' },
  { id: 'sessions', label: 'Active sessions' },
  { id: 'data', label: 'Your data' },
  { id: 'billing', label: 'Billing' },
  { id: 'danger', label: 'Danger zone' },
] as const;

export default async function SettingsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  type UserRow = {
    name: string | null;
    email: string;
    createdAt: Date;
    specialty: string | null;
    npi: string | null;
    clinicName: string | null;
    timeZone: string | null;
    mfaEnabled: boolean;
  };

  const [user, sessionId] = (await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        name: true,
        email: true,
        createdAt: true,
        specialty: true,
        npi: true,
        clinicName: true,
        timeZone: true,
        mfaEnabled: true,
      },
    }),
    getCurrentSessionId(),
  ])) as [UserRow | null, string | null];
  if (!user) redirect('/login');

  const activeSession = sessionId
    ? await prisma.userSession.findUnique({
        where: { sessionToken: sessionId },
      })
    : null;

  const { browser, os } = parseUserAgent(activeSession?.userAgent ?? null);

  return (
    <AppFrame>
      <Suspense fallback={null}>
        <EmailChangeToast />
      </Suspense>
      <PageHeader
        eyebrow="§ You"
        title={
          <>
            Your <em style={{ color: 'var(--accent-bright)' }}>settings</em>
          </>
        }
        subtitle="Profile, security, session, exports, and the billing link."
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '200px 1fr',
          gap: 32,
          padding: '0 32px 48px',
          alignItems: 'flex-start',
          maxWidth: 1200,
        }}
      >
        <aside
          style={{
            position: 'sticky',
            top: 16,
            alignSelf: 'flex-start',
          }}
        >
          <div className="qm-sectlabel" style={{ marginBottom: 10 }}>
            § On this page
          </div>
          <nav
            style={{ display: 'flex', flexDirection: 'column', gap: 2 }}
          >
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                style={{
                  padding: '7px 10px',
                  fontSize: 13,
                  color: 'var(--fg-3)',
                  borderRadius: 8,
                  textDecoration: 'none',
                  borderLeft: '2px solid transparent',
                }}
              >
                {s.label}
              </a>
            ))}
          </nav>
        </aside>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Section id="profile" eyebrow="§ 01 / Profile" title="Profile">
            <ProfileForm
              defaultName={user.name ?? ''}
              defaultSpecialty={user.specialty ?? ''}
              defaultNpi={user.npi ?? ''}
              defaultClinicName={user.clinicName ?? ''}
              defaultTimeZone={user.timeZone ?? ''}
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 14,
                marginTop: 18,
                paddingTop: 16,
                borderTop: '1px solid var(--line-soft)',
              }}
            >
              <EmailWithChangeButton email={user.email} />
              <ReadOnlyRow label="Member since" value={formatDate(user.createdAt)} />
            </div>
          </Section>

          <Section
            id="security"
            eyebrow="§ 02 / Security"
            title="Security"
            subtitle="Change your password. Other devices are signed out; this one stays."
          >
            <ChangePasswordForm />
            <div style={{ marginTop: 20 }}>
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: 12,
                  border: '1px dashed var(--line)',
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    marginBottom: 6,
                  }}
                >
                  <Ic.shield
                    width={14}
                    height={14}
                    style={{ color: 'var(--accent-bright)' }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 500 }}>
                    Two-factor authentication
                  </span>
                  <span
                    className={
                      user.mfaEnabled
                        ? 'qm-chip qm-chip-mint dot'
                        : 'qm-chip qm-chip-amber'
                    }
                  >
                    {user.mfaEnabled ? 'Enabled' : 'Off'}
                  </span>
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: 12.5,
                    color: 'var(--fg-3)',
                    lineHeight: 1.55,
                  }}
                >
                  TOTP setup + recovery codes UI lands in the next batch of
                  Settings work. The database supports it today (mfaSecret,
                  mfaBackupCodes[]).
                </p>
              </div>
            </div>
          </Section>

          <Section
            id="sessions"
            eyebrow="§ 03 / Sessions"
            title="Active session"
            subtitle="One device at a time. Signing in elsewhere revokes this session automatically."
          >
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
              <p style={{ fontSize: 13, color: 'var(--fg-3)' }}>
                Your current session predates the single-device enforcement
                rollout. Sign out and back in to enable it.
              </p>
            )}
          </Section>

          {isDataExportEnabled() && (
            <Section
              id="data"
              eyebrow="§ 04 / Data"
              title="Your data"
              subtitle="Download a ZIP containing every visit, transcript, SOAP note, audio file, and signed PDF."
            >
              <div
                style={{
                  display: 'flex',
                  gap: 16,
                  flexWrap: 'wrap',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                }}
              >
                <p
                  style={{
                    margin: 0,
                    fontSize: 13,
                    color: 'var(--fg-2)',
                    lineHeight: 1.55,
                    flex: 1,
                    minWidth: 220,
                  }}
                >
                  Export includes visit metadata, original audio, signed PDFs,
                  and your per-doctor edit patterns. No passwords or MFA
                  secrets. Large exports can take up to five minutes.
                </p>
                <a
                  href="/api/settings/export-data"
                  className="qm-btn qm-btn-ghost"
                  style={{ textDecoration: 'none' }}
                >
                  <Ic.download width={13} height={13} />
                  Export my data
                </a>
              </div>
            </Section>
          )}

          <Section
            id="billing"
            eyebrow="§ 05 / Billing"
            title="Billing"
            subtitle="Manage your subscription and payment method."
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  color: 'var(--fg-3)',
                  maxWidth: 400,
                }}
              >
                Stripe customer portal integration lands in the next Settings
                wave. Trial usage + invoices will appear here.
              </p>
              <button
                type="button"
                disabled
                className="qm-btn qm-btn-ghost"
                title="Coming soon"
                style={{
                  opacity: 0.55,
                  cursor: 'not-allowed',
                }}
              >
                Manage billing
              </button>
            </div>
          </Section>

          <Section
            id="danger"
            eyebrow="§ 06 / Danger"
            title="Danger zone"
            subtitle="Delete your account. Every visit, transcript, and exported file gets erased."
            danger
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  color: 'var(--fg-2)',
                  lineHeight: 1.55,
                  maxWidth: 440,
                }}
              >
                A compliance record (email, deletion date, visit count) is
                kept for 90 days and then purged. You&apos;ll be asked to
                re-enter your password and type DELETE to confirm.
              </p>
              <DeleteAccountDialog />
            </div>
          </Section>
        </div>
      </div>
    </AppFrame>
  );
}

function Section({
  id,
  eyebrow,
  title,
  subtitle,
  danger,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="qm-glass"
      style={{
        padding: '24px 26px',
        borderColor: danger ? 'rgba(251,113,133,0.3)' : undefined,
      }}
    >
      <div
        className="qm-sectlabel"
        style={{ marginBottom: 8, color: danger ? 'var(--coral)' : undefined }}
      >
        {eyebrow}
      </div>
      <h3
        className="qm-serif"
        style={{
          margin: 0,
          fontSize: 22,
          fontWeight: 400,
          letterSpacing: '-0.015em',
        }}
      >
        {title}
      </h3>
      {subtitle && (
        <p
          style={{
            margin: '6px 0 18px',
            fontSize: 12.5,
            color: 'var(--fg-3)',
            lineHeight: 1.55,
          }}
        >
          {subtitle}
        </p>
      )}
      {!subtitle && <div style={{ marginBottom: 18 }} />}
      {children}
    </section>
  );
}

function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontFamily: 'var(--mono)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--fg-4)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>{value}</div>
    </div>
  );
}

function EmailWithChangeButton({ email }: { email: string }) {
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 4,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontFamily: 'var(--mono)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: 'var(--fg-4)',
          }}
        >
          Email
        </div>
        <ChangeEmailDialog currentEmail={email} />
      </div>
      <div style={{ fontSize: 13, color: 'var(--fg-2)', wordBreak: 'break-all' }}>
        {email}
      </div>
    </div>
  );
}
