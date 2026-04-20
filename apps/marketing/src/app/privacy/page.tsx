import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description:
    'How TranscribeMD collects, uses, and protects patient and clinician information.',
};

const LAST_UPDATED = '2026-04-20';

export default function PrivacyPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">Legal</Badge>
            <h1 className="mt-6 type-h1 text-text-primary">Privacy Policy</h1>
            <p className="mt-6 text-[14px] text-text-muted">
              Last updated: {LAST_UPDATED}
            </p>

            <div className="mt-8 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-[13px] leading-relaxed text-amber-200">
              <strong className="font-semibold">
                [DRAFT — PENDING LEGAL REVIEW]
              </strong>
              <p className="mt-1.5">
                This document is a placeholder structure. The content below is
                an operational summary of how we handle data; it has not yet
                been reviewed by counsel and is not the final, binding Privacy
                Policy. Please email the contact at the bottom of this page if
                you need to cite a reviewed version.
              </p>
            </div>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-12">
          <div className="mx-auto max-w-3xl px-6 lg:px-8 space-y-10 text-[15px] leading-relaxed text-text-secondary">
            <div>
              <h2 className="type-h2 text-text-primary">1. Who we are</h2>
              <p className="mt-4">
                TranscribeMD is a medical-transcription product operated by
                AshTech Group. This Privacy Policy covers information collected
                through the TranscribeMD app (https://app.transcribemd.com once
                DNS lands) and the marketing site you&apos;re reading now.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                2. What we collect
              </h2>
              <p className="mt-4">We collect two kinds of information:</p>
              <ul className="mt-3 list-disc space-y-2 pl-5">
                <li>
                  <strong className="text-text-primary">Account data</strong>:
                  email, name, hashed password, IP + user agent at sign-in,
                  and product usage analytics.
                </li>
                <li>
                  <strong className="text-text-primary">Clinical data</strong>:
                  audio recordings you upload, transcripts, SOAP notes, ICD/CPT
                  codes, prescriptions, and any text you paste into the editor.
                  This content may contain Protected Health Information (PHI)
                  under HIPAA.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                3. How we use it
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  Operate the product: generate transcripts, SOAP notes, and
                  related artifacts on your behalf.
                </li>
                <li>
                  Improve model prompting using anonymized signals from how
                  doctors edit AI drafts (see the{' '}
                  <a
                    href="/hipaa"
                    className="text-violet-400 hover:text-violet-300"
                  >
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
              <h2 className="type-h2 text-text-primary">
                4. Who we share it with
              </h2>
              <p className="mt-4">
                We use subprocessors for specific functions. All subprocessors
                that touch PHI have signed Business Associate Agreements:
              </p>
              <ul className="mt-3 list-disc space-y-2 pl-5">
                <li>
                  <strong className="text-text-primary">Anthropic</strong> —
                  Claude models (SOAP generation, structured extraction).
                </li>
                <li>
                  <strong className="text-text-primary">OpenAI</strong> —
                  embeddings for style-matching.
                </li>
                <li>
                  <strong className="text-text-primary">Deepgram</strong> —
                  audio transcription.
                </li>
                <li>
                  <strong className="text-text-primary">Resend</strong> —
                  email delivery for signed-note exports.
                </li>
              </ul>
              <p className="mt-3">
                We do not sell your data. We do not share clinical data with
                any party outside this list.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">5. Your rights</h2>
              <p className="mt-4">
                You can request a copy of your data, correction of inaccurate
                information, or deletion of your account at any time from the
                Settings page within the app, or by emailing the contact
                address below.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">6. Retention</h2>
              <p className="mt-4">
                Audio files: 90 days past visit completion (configurable per
                practice). Transcripts and signed notes: 7 years minimum
                (HIPAA recordkeeping). Account data: until you delete the
                account. Edit-pattern embeddings: indefinitely while the
                account is active.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                7. Contact
              </h2>
              <p className="mt-4">
                Privacy questions: <code>privacy@ashtechgroup.com</code>. We
                respond within 30 days.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
