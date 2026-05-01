import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Terms of Service',
  description:
    'The terms under which QuillMD is provided to clinicians and practices.',
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

export default function TermsPage() {
  return (
    <>
      <NavBar />
      <main>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 48 }}
        >
          <div className="container" style={{ maxWidth: 760, position: 'relative' }}>
            <Badge dot="violet">Legal</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              Terms of Service
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
                These Terms are an operational placeholder and have not yet
                been reviewed by counsel. The final, binding Terms of Service
                will replace this document before paid customers sign up.
                Email the contact at the bottom of this page for the current
                reviewed version.
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
                1. Acceptance
              </h2>
              <p style={SECTION_BODY}>
                By creating an account on QuillMD you agree to these Terms
                and our{' '}
                <a href="/privacy" style={LINK}>
                  Privacy Policy
                </a>
                . If you&apos;re agreeing on behalf of a practice or employer,
                you confirm you have authority to bind them.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                2. What we provide
              </h2>
              <p style={SECTION_BODY}>
                QuillMD is an AI-assisted medical-transcription service. You
                upload audio or dictation; we return a draft SOAP note,
                ICD/CPT code suggestions, prescription drafts, referral drafts,
                and a patient summary. All output is a draft until YOU sign
                it. Clinical judgment remains yours.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                3. Your responsibilities
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  You must be a licensed clinician or an authorized member of
                  a clinical practice.
                </li>
                <li>
                  You will not upload content you don&apos;t have the right to
                  process (including patient content without proper consent
                  under your jurisdiction).
                </li>
                <li>
                  You review and edit every AI output before signing. We do
                  not guarantee clinical accuracy; you are the clinician of
                  record.
                </li>
                <li>
                  You will not probe, scrape, reverse-engineer, or attempt to
                  bypass our security or rate limits.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                4. AI output disclaimer
              </h2>
              <p style={SECTION_BODY}>
                AI-generated text is a draft. QuillMD is not a medical
                device, not a replacement for clinical judgment, and does not
                diagnose, treat, or prescribe. Drug-interaction warnings are
                advisory and not exhaustive. You are responsible for every
                final note, code, and prescription that leaves your account.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                5. Billing
              </h2>
              <p style={SECTION_BODY}>
                Subscription fees and the free-trial terms are listed on our
                Pricing page. Cancellation is self-service in the Settings
                page and takes effect at the end of the current billing
                period. Refunds for unused time are at our discretion.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                6. Termination
              </h2>
              <p style={SECTION_BODY}>
                You may terminate your account at any time. We may suspend or
                terminate accounts for violation of these Terms, for
                non-payment, or for activity that risks the integrity of the
                service. On termination, your data is retained per the{' '}
                <a href="/privacy" style={LINK}>
                  Privacy Policy
                </a>{' '}
                retention schedule, then deleted.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                7. Limitation of liability
              </h2>
              <p style={SECTION_BODY}>
                To the maximum extent permitted by law, QuillMD&apos;s total
                liability for any claim arising out of these Terms is limited
                to the fees you paid us in the twelve months preceding the
                claim. We are not liable for indirect, incidental, or
                consequential damages.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                8. Governing law
              </h2>
              <p style={SECTION_BODY}>
                These Terms are governed by the laws of the United States.
                Any dispute will be resolved in the state and federal courts
                serving our registered business address (AshTech Group).
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                9. Changes to these Terms
              </h2>
              <p style={SECTION_BODY}>
                We may update these Terms. Material changes will be announced
                in-app and via email before taking effect. Continued use of
                the service after the effective date constitutes acceptance.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                10. Contact
              </h2>
              <p style={SECTION_BODY}>
                Legal questions: <code style={CODE}>legal@ashtechgroup.com</code>.
                General support: <code style={CODE}>support@ashtechgroup.com</code>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
