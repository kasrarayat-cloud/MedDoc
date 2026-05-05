import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'HIPAA Compliance',
  description:
    'How QuillMD handles PHI under HIPAA — BAAs, encryption, retention, audit logs.',
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
const LINK: React.CSSProperties = {
  color: 'var(--color-linear-sage-bright)',
  textDecoration: 'underline',
  textDecorationColor: 'rgba(122,166,140,0.4)',
};

export default function HipaaPage() {
  return (
    <>
      <NavBar />
      <main>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 48 }}
        >
          <div className="container" style={{ maxWidth: 760, position: 'relative' }}>
            <Badge dot="violet">Compliance</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              HIPAA Compliance
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
                This page is a practical summary of our HIPAA posture for
                prospective customers. A reviewed version and our signed BAA
                template will replace this document before we onboard paid
                customers handling PHI.
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
                Business Associate Agreements (BAAs)
              </h2>
              <p style={SECTION_BODY}>
                AshTech Group will execute a Business Associate Agreement with
                any Covered Entity or Business Associate customer before PHI
                is sent to QuillMD. Each subprocessor that processes PHI on
                our behalf will have an executed BAA in place before that
                customer&apos;s PHI flows through their integration:
              </p>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>Anthropic (Claude models)</li>
                <li>OpenAI (embeddings)</li>
                <li>Deepgram (audio transcription, Nova-3 Medical model)</li>
                <li>Resend (email delivery)</li>
                <li>Backblaze B2 (encrypted offsite backup)</li>
                <li>Sentry (error monitoring; PHI redacted at source)</li>
              </ul>
              <p style={SECTION_BODY}>
                We maintain an internal compliance register that tracks BAA
                status for every subprocessor. Pre-pilot, the BAA execution
                step is part of customer onboarding rather than a one-time
                vendor sign-off; the per-subprocessor status is reviewable
                by covered-entity prospects upon request via{' '}
                <a href="/contact" style={LINK}>contact@quillmd.com</a>.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Encryption and transport
              </h2>
              <p style={SECTION_BODY}>
                PHI is encrypted in transit (TLS 1.2+ on every provider call
                and to the browser once a domain with TLS is active). At
                rest, PostgreSQL data and MinIO objects inherit host-level
                disk encryption from our VPS provider. Backups are stored
                encrypted.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Access controls
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  Every clinical record is scoped to the user who created it.
                  Cross-user access is rejected with a 404 (anti-enumeration).
                </li>
                <li>
                  Single-session enforcement: a new login revokes prior
                  sessions, so a stolen JWT stops working the next time the
                  true owner signs in.
                </li>
                <li>
                  Password storage uses bcrypt with a 12-round cost factor.
                  After 5 failed logins, the account is locked for 15
                  minutes.
                </li>
                <li>
                  Production secrets are rotated quarterly (see our internal
                  rotation runbook) and on any suspected exposure.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Audit logging
              </h2>
              <p style={SECTION_BODY}>
                Every sensitive action (login, password change, data access,
                note signing, export) writes a row to the audit log, scoped
                to the practice tenant. Audit logs are retained for the
                HIPAA minimum of 6 years.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Retention and deletion
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  Audio files: 90 days past visit completion. Configurable
                  per practice.
                </li>
                <li>Transcripts and signed notes: 7 years minimum.</li>
                <li>Account + audit logs: retained per HIPAA.</li>
              </ul>
              <p style={SECTION_BODY}>
                You may request deletion of your account and associated data
                at any time from Settings. Backups include PHI and are
                retained for the shorter of 90 days or until next quarterly
                prune.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Breach notification
              </h2>
              <p style={SECTION_BODY}>
                If we become aware of a breach of unsecured PHI, we will
                notify affected customers within 60 days as required by 45
                CFR § 164.410, with a written description of what was
                disclosed and what mitigations are in place.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                De-identification for product improvement
              </h2>
              <p style={SECTION_BODY}>
                QuillMD captures anonymized edit patterns to improve AI
                output for each doctor (the &quot;few-shot prompting&quot;
                system). This data is scoped to the signed-in doctor and
                stored as embeddings of text snippets. It is never shared
                across accounts without a separate data-use agreement.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                Contact
              </h2>
              <p style={SECTION_BODY}>
                BAA requests and compliance questions:{' '}
                <code
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    color: 'var(--color-linear-sage-bright)',
                  }}
                >
                  compliance@ashtechgroup.com
                </code>
                .
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
