import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description:
    'How QuillMD collects, uses, and protects patient and clinician information.',
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
const STRONG: React.CSSProperties = {
  color: 'var(--color-linear-text)',
  fontWeight: 600,
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

export default function PrivacyPage() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 48 }}
        >
          <div className="container" style={{ maxWidth: 760, position: 'relative' }}>
            <Badge dot="violet">Legal</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              Privacy Policy
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
                This document is a placeholder structure. The content below is
                an operational summary of how we handle data; it has not yet
                been reviewed by counsel and is not the final, binding Privacy
                Policy. Please email the contact at the bottom of this page if
                you need to cite a reviewed version.
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
                1. Who we are
              </h2>
              <p style={SECTION_BODY}>
                QuillMD is a medical-transcription product operated by
                AshTech Group. This Privacy Policy covers information collected
                through the QuillMD app (https://app.quillmd.com once
                DNS lands) and the marketing site you&apos;re reading now.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                2. What we collect
              </h2>
              <p style={SECTION_BODY}>We collect two kinds of information:</p>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  <strong style={STRONG}>Account data</strong>: email, name, hashed
                  password, IP + user agent at sign-in, and product usage
                  analytics.
                </li>
                <li>
                  <strong style={STRONG}>Clinical data</strong>: audio recordings you
                  upload, transcripts, SOAP notes, ICD/CPT codes, prescriptions,
                  and any text you paste into the editor. This content may
                  contain Protected Health Information (PHI) under HIPAA.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                3. How we use it
              </h2>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  Operate the product: generate transcripts, SOAP notes, and
                  related artifacts on your behalf.
                </li>
                <li>
                  Improve model prompting using anonymized signals from how
                  doctors edit AI drafts (see the{' '}
                  <a href="/hipaa" style={LINK}>
                    HIPAA page
                  </a>{' '}
                  for the de-identification approach).
                </li>
                <li>
                  Communicate with you about the product (transactional email
                  only; no marketing unless you opt in separately).
                </li>
                <li>
                  Comply with legal obligations, including HIPAA audit logs.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                4. Who we share it with
              </h2>
              <p style={SECTION_BODY}>
                We use subprocessors for specific functions. All subprocessors
                that touch PHI have signed Business Associate Agreements:
              </p>
              <ul style={{ ...SECTION_BODY, paddingLeft: 20, listStyle: 'disc' }}>
                <li>
                  <strong style={STRONG}>Anthropic</strong> — Claude models (SOAP
                  generation, structured extraction).
                </li>
                <li>
                  <strong style={STRONG}>OpenAI</strong> — embeddings for
                  style-matching.
                </li>
                <li>
                  <strong style={STRONG}>Deepgram</strong> — audio transcription.
                </li>
                <li>
                  <strong style={STRONG}>Resend</strong> — email delivery for
                  signed-note exports.
                </li>
              </ul>
              <p style={SECTION_BODY}>
                We do not sell your data. We do not share clinical data with
                any party outside this list.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                5. Your rights
              </h2>
              <p style={SECTION_BODY}>
                You can request a copy of your data, correction of inaccurate
                information, or deletion of your account at any time from the
                Settings page within the app, or by emailing the contact
                address below.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                6. Retention
              </h2>
              <p style={SECTION_BODY}>
                Audio files: 90 days past visit completion (configurable per
                practice). Transcripts and signed notes: 7 years minimum
                (HIPAA recordkeeping). Account data: until you delete the
                account. Edit-pattern embeddings: indefinitely while the
                account is active.
              </p>
            </div>

            <div>
              <h2 className="section-title" style={SECTION_TITLE}>
                7. Contact
              </h2>
              <p style={SECTION_BODY}>
                Privacy questions:{' '}
                <code style={CODE}>privacy@ashtechgroup.com</code>. We respond
                within 30 days.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
