import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Security',
  description:
    'How QuillMD is built, deployed, and monitored to keep patient data safe.',
};

const LAST_UPDATED = '2026-04-20';

const SECTION_TITLE: React.CSSProperties = {
  color: 'var(--color-linear-text)',
};
const SECTION_BODY: React.CSSProperties = {
  marginTop: 16,
  fontSize: 15,
  lineHeight: 1.7,
  color: 'var(--color-linear-text-2)',
};
const CODE: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  color: 'var(--color-linear-sage-bright)',
};
const LINK: React.CSSProperties = {
  color: 'var(--color-linear-sage-bright)',
  textDecoration: 'underline',
  textDecorationColor: 'rgba(122,166,140,0.4)',
};

export default function SecurityPage() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 48 }}
        >
          <div className="container" style={{ maxWidth: 760, position: 'relative' }}>
            <Badge dot="violet">Security</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              Security practices
            </h1>
            <p
              style={{
                marginTop: 16,
                fontSize: 13,
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              Last updated: {LAST_UPDATED}
            </p>
            <div className="qm-warn-moderate" style={{ marginTop: 24 }}>
              <strong style={{ fontWeight: 600, color: 'var(--color-linear-text)' }}>
                [DRAFT — PENDING LEGAL REVIEW]
              </strong>
              <p style={{ marginTop: 6 }}>
                This page summarizes how QuillMD is built and operated.
                It&apos;s a transparent operational statement, not a marketing
                claim. If you need a signed SOC 2, ISO 27001, or HITRUST
                report, see &quot;Certifications&quot; below.
              </p>
            </div>
          </div>
        </section>

        <section
          style={{
            position: 'relative',
            borderTop: '1px solid var(--color-linear-hairline)',
            paddingTop: 48,
            paddingBottom: 96,
          }}
        >
          <div
            className="container"
            style={{
              maxWidth: 760,
              display: 'flex',
              flexDirection: 'column',
              gap: 40,
            }}
          >
            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Application
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  Auth via NextAuth (Auth.js v5) with JWT sessions, bcrypt-12
                  password hashing, 5-attempt lockout with 15-minute cooldown.
                </li>
                <li>
                  Single-session enforcement: a new login revokes prior
                  sessionTokens so stolen JWTs stop resolving.
                </li>
                <li>
                  Every API route validates session + per-record ownership
                  before serving data; cross-user access returns 404 to
                  prevent ID enumeration.
                </li>
                <li>
                  Structured input validation via Zod on every request that
                  accepts user data.
                </li>
                <li>
                  File uploads are size-capped (500 MB audio, 50 MB
                  dictation) and MIME-validated before being streamed to
                  object storage.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Infrastructure
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  All services run in Docker containers on a dedicated VPS.
                  No shared-tenant compute.
                </li>
                <li>
                  Postgres (with pgvector for embedding workloads), Redis
                  (BullMQ broker), and MinIO (S3-compatible object storage)
                  are bound to localhost on the VPS. Public traffic enters
                  only through Caddy.
                </li>
                <li>
                  Caddy serves as the public edge; TLS is handled by Let&apos;s
                  Encrypt with auto-renewal once a domain is configured.
                </li>
                <li>
                  Secrets live in a root-owned <code style={CODE}>.env</code> file on
                  the VPS only; <code style={CODE}>.env*</code> is gitignored.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Data handling
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  TLS 1.2+ for every outbound call to AI providers, email, and
                  the browser.
                </li>
                <li>
                  At-rest encryption inherits from the VPS provider&apos;s disk
                  encryption.
                </li>
                <li>
                  A PHI scrubber (<code style={CODE}>redactPhi</code>) masks emails,
                  phone numbers, and SSNs in error logs and Sentry events.
                  Free-text fields above a length threshold collapse to
                  length markers.
                </li>
                <li>
                  Audio retention defaults to 90 days; transcripts retain for
                  7 years per HIPAA.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Operations
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  Secrets rotated quarterly (JWT, AI provider keys) per our
                  internal rotation runbook.
                </li>
                <li>
                  Every deploy is preceded by a pg_dump backup; rollback path
                  is documented.
                </li>
                <li>
                  Production error surfacing via Sentry on the CRM app;
                  transcribe-md Sentry integration is in progress (tracked
                  in the T-M15 audit).
                </li>
                <li>
                  Vulnerability disclosure: email{' '}
                  <code style={CODE}>security@ashtechgroup.com</code>. We aim to
                  acknowledge within 48 hours. Please do not open GitHub
                  issues for security reports.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Certifications
              </h2>
              <p style={SECTION_BODY}>
                QuillMD does not currently hold a SOC 2, ISO 27001, or HITRUST
                certification. Our launch target is SOC 2 Type 2 readiness
                within 12 months of general availability. Our HIPAA posture
                is covered by{' '}
                <a href="/hipaa" style={LINK}>
                  BAAs and operational controls
                </a>{' '}
                rather than third-party audit today.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Known gaps (transparent)
              </h2>
              <p style={SECTION_BODY}>
                We publish pre-launch audit findings. See our internal{' '}
                <code style={CODE}>docs/T-M15-AUDIT-REPORT.md</code> (available on
                request for prospects under NDA) for the current queue of
                hardening work.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Contact
              </h2>
              <p style={SECTION_BODY}>
                Security: <code style={CODE}>security@ashtechgroup.com</code>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
