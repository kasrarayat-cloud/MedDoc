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

export default function HipaaPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">Compliance</Badge>
            <h1 className="mt-6 type-h1 text-text-primary">HIPAA Compliance</h1>
            <p className="mt-6 text-[14px] text-text-muted">
              Last updated: {LAST_UPDATED}
            </p>

            <div
              className="mt-8 rounded-xl border border-[rgba(212,165,116,0.35)] bg-[rgba(212,165,116,0.10)] p-4 text-[13.5px] leading-relaxed text-[#7A4F1F]"
              style={{ fontFamily: 'var(--font-serif), Georgia, serif' }}
            >
              <strong className="font-medium">
                [DRAFT — PENDING LEGAL REVIEW]
              </strong>
              <p className="mt-1.5">
                This page is a practical summary of our HIPAA posture for
                prospective customers. A reviewed version and our signed BAA
                template will replace this document before we onboard paid
                customers handling PHI.
              </p>
            </div>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-12">
          <div className="mx-auto max-w-3xl px-6 lg:px-8 space-y-10 text-[15px] leading-relaxed text-text-secondary">
            <div>
              <h2 className="type-h2 text-text-primary">
                Business Associate Agreements (BAAs)
              </h2>
              <p className="mt-4">
                AshTech Group will execute a Business Associate Agreement with
                any Covered Entity or Business Associate customer before PHI
                is sent to QuillMD. Our subprocessors that process PHI on
                our behalf have signed BAAs with us:
              </p>
              <ul className="mt-3 list-disc space-y-2 pl-5">
                <li>Anthropic (Claude models)</li>
                <li>OpenAI (embeddings)</li>
                <li>Deepgram (audio transcription, Nova-3 Medical model)</li>
                <li>Resend (email delivery)</li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Encryption and transport
              </h2>
              <p className="mt-4">
                PHI is encrypted in transit (TLS 1.2+ on every provider call
                and to the browser once a domain with TLS is active). At
                rest, PostgreSQL data and MinIO objects inherit host-level
                disk encryption from our VPS provider. Backups are stored
                encrypted.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Access controls
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
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
              <h2 className="type-h2 text-text-primary">
                Audit logging
              </h2>
              <p className="mt-4">
                Every sensitive action (login, password change, data access,
                note signing, export) writes a row to the audit log, scoped
                to the practice tenant. Audit logs are retained for the
                HIPAA minimum of 6 years.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Retention and deletion
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  Audio files: 90 days past visit completion. Configurable
                  per practice.
                </li>
                <li>
                  Transcripts and signed notes: 7 years minimum.
                </li>
                <li>
                  Account + audit logs: retained per HIPAA.
                </li>
              </ul>
              <p className="mt-3">
                You may request deletion of your account and associated data
                at any time from Settings. Backups include PHI and are
                retained for the shorter of 90 days or until next quarterly
                prune.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Breach notification
              </h2>
              <p className="mt-4">
                If we become aware of a breach of unsecured PHI, we will
                notify affected customers within 60 days as required by 45
                CFR § 164.410, with a written description of what was
                disclosed and what mitigations are in place.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                De-identification for product improvement
              </h2>
              <p className="mt-4">
                QuillMD captures anonymized edit patterns to improve AI
                output for each doctor (the &quot;few-shot prompting&quot;
                system). This data is scoped to the signed-in doctor and
                stored as embeddings of text snippets. It is never shared
                across accounts without a separate data-use agreement.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Contact
              </h2>
              <p className="mt-4">
                BAA requests and compliance questions:{' '}
                <code>compliance@ashtechgroup.com</code>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
