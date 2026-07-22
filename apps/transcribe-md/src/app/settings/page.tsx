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
import { logAudit } from '@/lib/audit';
import { isSkinBeta } from '@/config/skin-beta';
import {
  SettingsSectionsC3,
  type SettingsSectionC3,
} from './settings-sections-c3';
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
import { NoteFormatManager } from './note-format/note-format-manager';
import {
  NativeTemplateManager,
  type NativeTemplateListItem,
} from './note-format/native-template-manager';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { listDoctorTemplates } from '@/lib/note-template-persist/read';
import { findSpecialty } from '@meddoc/shared/specialties';
import type { ClientTemplateListItem } from '@/lib/note-template-persist/types';

export const metadata: Metadata = { title: 'Settings' };

const SECTIONS = [
  { id: 'profile', label: 'Profile' },
  { id: 'note-format', label: 'My Note Format' },
  { id: 'security', label: 'Security' },
  { id: 'sessions', label: 'Active sessions' },
  { id: 'data', label: 'Your data' },
  { id: 'billing', label: 'Billing' },
  { id: 'danger', label: 'Danger zone' },
] as const;

// Runtime upload-capability probe (incident 2026-06-04 defense-in-depth). A
// build-time assertion already guarantees the extractor libs bundle into the
// standalone output; this is the belt-and-suspenders so a (hypothetical)
// missing lib degrades to "format not offered" instead of advertise-then-fail.
// It probes the SAME dynamic-import the extractor uses, so the UI advertises a
// format only if its extractor actually loads in THIS image. Module cache makes
// repeat calls free; .txt/.md need no lib and are always available.
let uploadCapsCache: { pdf: boolean; docx: boolean } | null = null;
async function getUploadCaps(): Promise<{ pdf: boolean; docx: boolean }> {
  if (uploadCapsCache) return uploadCapsCache;
  const [pdf, docx] = await Promise.all([
    import('@/lib/note-template-parse/pdf-to-text').then(() => true).catch(() => false),
    import('@/lib/note-template-parse/docx-to-text').then(() => true).catch(() => false),
  ]);
  uploadCapsCache = { pdf, docx };
  return uploadCapsCache;
}

/** The doctor's native (Template Twin) .docx templates + certification status. */
async function loadNativeTemplates(doctorId: string): Promise<NativeTemplateListItem[]> {
  const rows = await prisma.noteTemplate.findMany({
    where: { doctorId, templateTwinCompiledVersion: { isNot: null } },
    select: {
      id: true,
      name: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          certificationStatus: true,
          fields: { select: { id: true } },
        },
      },
    },
    orderBy: { updatedAt: 'desc' },
    take: 25,
  });
  type Row = {
    id: string;
    name: string;
    version: number;
    templateTwinCompiledVersion: {
      certificationStatus: string;
      fields: { id: string }[];
    } | null;
  };
  return (rows as Row[]).map((t) => ({
    noteTemplateId: t.id,
    name: t.name,
    version: t.version,
    certificationStatus: (
      t.templateTwinCompiledVersion?.certificationStatus ?? 'NEEDS_CONFIRMATION'
    ).toLowerCase(),
    fieldCount: t.templateTwinCompiledVersion?.fields.length ?? 0,
  }));
}

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

  // §164.312(b) audit row — F-11 from QA agent v3.2 discovery report.
  // /settings reads the user's profile + active sessions; the latter
  // exposes ipAddress + userAgent (device fingerprints), so the page
  // is PHI-adjacent under a strict §164.312(b) reading. Round 3 PR-C
  // covered other read surfaces but missed this one. Fire-and-forget
  // per the file's audit precedents — `logAudit` is internally try/
  // wrapped so failures never break the render.
  void logAudit({
    action: 'VIEWED_SETTINGS',
    targetType: 'User',
    targetId: session.user.id,
    metadata: {
      source: 'rsc:/settings',
      hasActiveSession: activeSession !== null,
    },
  });

  // Phase 2b — the doctor's own note-format templates (scoped to session.user.id;
  // a doctor never sees another's). Date → ISO + display labels for the client.
  const noteTemplates: ClientTemplateListItem[] = (
    await listDoctorTemplates(session.user.id)
  ).map((t) => ({
    id: t.id,
    name: t.name,
    encounterType: t.encounterType,
    encounterLabel: t.encounterType ? findSpecialty(t.encounterType).label : 'All my visits',
    status: t.status,
    version: t.version,
    sectionCount: t.sectionCount,
    defaultCount: t.defaultCount,
    updatedAtIso: t.updatedAt.toISOString(),
  }));

  // Which upload formats can this image actually extract (see getUploadCaps).
  const uploadCaps = await getUploadCaps();

  // Native-DOCX certify-once workspace (flag-gated). Flag OFF → nativeSlot is
  // null and the note-format section renders byte-identical to today.
  const nativeSlot = templateNativeDocxEnabled() ? (
    <NativeTemplateManager existing={await loadNativeTemplates(session.user.id)} />
  ) : null;

  // ── C3 calm-skin settings (Stage 3, flag-gated) ───────────────────────────
  // SKIN-ONLY: identical auth + Prisma reads + VIEWED_SETTINGS audit row + the
  // doctor-scoped template read above. This is a re-layout — the long 7-section
  // scroll collapses to a calm section rail showing ONE panel at a time. Every
  // panel renders the SAME server-action-wired component (ProfileForm,
  // NoteFormatManager, ChangePasswordForm, SessionPanel, DeleteAccountDialog,
  // export/billing links) the legacy layout uses. Flag OFF → the stacked
  // layout below runs, byte-identical.
  if (isSkinBeta()) {
    const c3Sections: SettingsSectionC3[] = [
      {
        id: 'profile',
        label: 'Profile',
        title: 'Profile',
        content: (
          <>
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
          </>
        ),
      },
      {
        id: 'note-format',
        label: 'Note format',
        title: 'My Note Format',
        subtitle:
          'QuillMD writes in a standard SOAP format. Most doctors leave this as-is — teaching it your own template is an explicit, opt-in step below.',
        content: (
          <>
            <NoteFormatManager templates={noteTemplates} uploadCaps={uploadCaps} />
            {nativeSlot}
          </>
        ),
      },
      {
        id: 'security',
        label: 'Security',
        title: 'Security',
        subtitle:
          'Change your password. Other devices are signed out; this one stays.',
        content: (
          <>
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
          </>
        ),
      },
      {
        id: 'sessions',
        label: 'Active session',
        title: 'Active session',
        subtitle:
          'One device at a time. Signing in elsewhere revokes this session automatically.',
        content: activeSession ? (
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
        ),
      },
      ...(isDataExportEnabled()
        ? [
            {
              id: 'data',
              label: 'Your data',
              title: 'Your data',
              subtitle:
                'Download a ZIP containing every visit, transcript, SOAP note, audio file, and signed PDF.',
              content: (
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
              ),
            } satisfies SettingsSectionC3,
          ]
        : []),
      {
        id: 'billing',
        label: 'Billing',
        title: 'Billing',
        subtitle: 'Manage your subscription and payment method.',
        content: (
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
              style={{ opacity: 0.45, cursor: 'not-allowed' }}
            >
              Manage billing
            </button>
          </div>
        ),
      },
      {
        id: 'danger',
        label: 'Danger zone',
        title: 'Danger zone',
        subtitle:
          'Delete your account. Every visit, transcript, and exported file gets erased.',
        danger: true,
        content: (
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
              A compliance record (email, deletion date, visit count) is kept
              for 90 days and then purged. You&apos;ll be asked to re-enter your
              password and type DELETE to confirm.
            </p>
            <DeleteAccountDialog />
          </div>
        ),
      },
    ];

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
        </div>
        <div style={{ padding: '20px 24px 48px', maxWidth: 1100 }}>
          <SettingsSectionsC3 sections={c3Sections} />
        </div>
      </AppFrame>
    );
  }

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
            id="note-format"
            eyebrow="02 / Note format"
            title="My Note Format"
          >
            <NoteFormatManager templates={noteTemplates} uploadCaps={uploadCaps} />
            {nativeSlot}
          </Section>

          <Section
            id="security"
            eyebrow="03 / Security"
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
            eyebrow="04 / Sessions"
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
              eyebrow="05 / Data"
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
            eyebrow="06 / Billing"
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
            eyebrow="07 / Danger"
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
