// ============================================================================
// Phase 5 — Linear V1 Faithful settings.
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html chrome (linear-bg + hairline borders).
//
// Two-column layout: 200 px sticky section index on the left, single
// stack of section cards on the right. Each section sits on
// linear-surface-1 with a hairline border. The Phase 4 cream-paper
// .qm-glass treatment is gone.
//
// Server actions + form behaviour (T-M16.2 / T-M17.3) are unchanged
// per PROTECTED_CONTRACTS.
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
import { LocalTime } from '@/components/ui/local-time';
import { ProfileForm } from './profile-form';
import { SessionPanel } from './session-panel';
import { DeleteAccountDialog } from './delete-account-dialog';
import { ChangePasswordForm } from './change-password-form';
import { ChangeEmailDialog } from './change-email-dialog';
import { EmailChangeToast } from './email-change-toast';
import { isDataExportEnabled } from '../api/settings/export-data/route';

export const metadata: Metadata = { title: 'Settings' };

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

      <div style={{ padding: '18px 24px 0' }}>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            fontWeight: 500,
            color: 'var(--color-linear-text-3)',
            letterSpacing: '0.07em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}
        >
          Account
        </div>
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 22,
            fontWeight: 500,
            color: 'var(--color-linear-text)',
            letterSpacing: '-0.012em',
            lineHeight: 1.2,
          }}
        >
          Settings
        </h1>
        <p
          style={{
            margin: '6px 0 0',
            fontFamily: 'var(--font-sans)',
            fontSize: 13,
            color: 'var(--color-linear-text-2)',
            lineHeight: 1.5,
          }}
        >
          Profile, security, session, exports, and the billing link.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '200px 1fr',
          gap: 32,
          padding: '24px 24px 48px',
          alignItems: 'flex-start',
          maxWidth: 1200,
        }}
      >
        <aside
          style={{
            position: 'sticky',
            top: 64,
            alignSelf: 'flex-start',
          }}
        >
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10.5,
              fontWeight: 500,
              color: 'var(--color-linear-text-3)',
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              marginBottom: 10,
              padding: '0 8px',
            }}
          >
            On this page
          </div>
          <nav
            aria-label="Settings sections"
            style={{ display: 'flex', flexDirection: 'column', gap: 1 }}
          >
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="qm-tap-44"
                style={{
                  padding: '6px 8px',
                  height: 28,
                  display: 'flex',
                  alignItems: 'center',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                  borderRadius: 5,
                  textDecoration: 'none',
                  transition:
                    'background-color 80ms ease, color 80ms ease',
                }}
              >
                {s.label}
              </a>
            ))}
          </nav>
        </aside>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Section id="profile" eyebrow="01 / Profile" title="Profile">
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
                borderTop: '1px solid var(--color-linear-hairline)',
              }}
            >
              <EmailWithChangeButton email={user.email} />
              <ReadOnlyRow
                label="Member since"
                value={
                  <LocalTime
                    iso={user.createdAt.toISOString()}
                    variant="date"
                  />
                }
              />
            </div>
          </Section>

          <Section
            id="security"
            eyebrow="02 / Security"
            title="Security"
            subtitle="Change your password. Other devices are signed out; this one stays."
          >
            <ChangePasswordForm />
            <div style={{ marginTop: 20 }}>
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: 8,
                  border: '1px dashed var(--color-linear-border-strong)',
                  background: 'var(--color-linear-row-hover)',
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
                    style={{ color: 'var(--color-linear-sage-bright)' }}
                  />
                  <span
                    style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: 13,
                      fontWeight: 500,
                      color: 'var(--color-linear-text)',
                    }}
                  >
                    Two-factor authentication
                  </span>
                  <span
                    className={
                      user.mfaEnabled
                        ? 'qm-lin-pill qm-lin-pill--ready'
                        : 'qm-lin-pill qm-lin-pill--review'
                    }
                  >
                    {user.mfaEnabled ? 'Enabled' : 'Off'}
                  </span>
                </div>
                <p
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-sans)',
                    fontSize: 12.5,
                    color: 'var(--color-linear-text-2)',
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
            eyebrow="03 / Sessions"
            title="Active session"
            subtitle="One device at a time. Signing in elsewhere revokes this session automatically."
          >
            {activeSession ? (
              <SessionPanel
                ipAddress={activeSession.ipAddress}
                browser={browser}
                os={os}
                locationLabel={describeIpLocation(activeSession.ipAddress)}
                loggedInAtIso={activeSession.createdAt.toISOString()}
                expiresAtIso={activeSession.expiresAt.toISOString()}
                lastActiveAtIso={activeSession.lastActiveAt.toISOString()}
              />
            ) : (
              <p
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                }}
              >
                Your current session predates the single-device enforcement
                rollout. Sign out and back in to enable it.
              </p>
            )}
          </Section>

          {isDataExportEnabled() && (
            <Section
              id="data"
              eyebrow="04 / Data"
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
                    fontFamily: 'var(--font-sans)',
                    fontSize: 13,
                    color: 'var(--color-linear-text-2)',
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
                  className="qm-lin-btn"
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
            eyebrow="05 / Billing"
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
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                  maxWidth: 400,
                }}
              >
                Stripe customer portal integration lands in the next Settings
                wave. Trial usage + invoices will appear here.
              </p>
              <button
                type="button"
                disabled
                className="qm-lin-btn"
                title="Coming soon"
                style={{
                  opacity: 0.45,
                  cursor: 'not-allowed',
                }}
              >
                Manage billing
              </button>
            </div>
          </Section>

          <Section
            id="danger"
            eyebrow="06 / Danger"
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
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
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
      style={{
        padding: '20px 22px',
        background: 'var(--color-linear-surface-1)',
        border: `1px solid ${
          danger
            ? 'rgba(212, 87, 74, 0.30)'
            : 'var(--color-linear-border)'
        }`,
        borderRadius: 10,
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          fontWeight: 500,
          letterSpacing: '0.07em',
          textTransform: 'uppercase',
          color: danger
            ? 'var(--color-linear-coral)'
            : 'var(--color-linear-text-3)',
          marginBottom: 8,
        }}
      >
        {eyebrow}
      </div>
      <h3
        style={{
          margin: 0,
          fontFamily: 'var(--font-sans)',
          fontSize: 18,
          fontWeight: 500,
          color: 'var(--color-linear-text)',
          letterSpacing: '-0.012em',
        }}
      >
        {title}
      </h3>
      {subtitle && (
        <p
          style={{
            margin: '6px 0 18px',
            fontFamily: 'var(--font-sans)',
            fontSize: 12.5,
            color: 'var(--color-linear-text-2)',
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

function ReadOnlyRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--color-linear-text-3)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 13,
          color: 'var(--color-linear-text)',
        }}
      >
        {value}
      </div>
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
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
          }}
        >
          Email
        </div>
        <ChangeEmailDialog currentEmail={email} />
      </div>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 13,
          color: 'var(--color-linear-text)',
          wordBreak: 'break-all',
        }}
      >
        {email}
      </div>
    </div>
  );
}
