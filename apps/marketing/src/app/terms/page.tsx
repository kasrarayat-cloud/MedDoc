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

export default function TermsPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">Legal</Badge>
            <h1 className="mt-6 type-h1 text-text-primary">
              Terms of Service
            </h1>
            <p className="mt-6 text-[14px] text-text-muted">
              Last updated: {LAST_UPDATED}
            </p>

            <div className="mt-8 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-[13px] leading-relaxed text-amber-200">
              <strong className="font-semibold">
                [DRAFT — PENDING LEGAL REVIEW]
              </strong>
              <p className="mt-1.5">
                These Terms are an operational placeholder and have not yet
                been reviewed by counsel. The final, binding Terms of Service
                will replace this document before paid customers sign up.
                Email the contact at the bottom of this page for the current
                reviewed version.
              </p>
            </div>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-12">
          <div className="mx-auto max-w-3xl px-6 lg:px-8 space-y-10 text-[15px] leading-relaxed text-text-secondary">
            <div>
              <h2 className="type-h2 text-text-primary">
                1. Acceptance
              </h2>
              <p className="mt-4">
                By creating an account on QuillMD you agree to these Terms
                and our{' '}
                <a
                  href="/privacy"
                  className="text-violet-400 hover:text-violet-300"
                >
                  Privacy Policy
                </a>
                . If you&apos;re agreeing on behalf of a practice or employer,
                you confirm you have authority to bind them.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                2. What we provide
              </h2>
              <p className="mt-4">
                QuillMD is an AI-assisted medical-transcription service.
                You upload audio or dictation; we return a draft SOAP note,
                ICD/CPT code suggestions, prescription drafts, referral drafts,
                and a patient summary. All output is a draft until YOU sign
                it. Clinical judgment remains yours.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                3. Your responsibilities
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
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
              <h2 className="type-h2 text-text-primary">
                4. AI output disclaimer
              </h2>
              <p className="mt-4">
                AI-generated text is a draft. QuillMD is not a medical
                device, not a replacement for clinical judgment, and does not
                diagnose, treat, or prescribe. Drug-interaction warnings are
                advisory and not exhaustive. You are responsible for every
                final note, code, and prescription that leaves your account.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                5. Billing
              </h2>
              <p className="mt-4">
                Subscription fees and the free-trial terms are listed on our
                Pricing page. Cancellation is self-service in the Settings
                page and takes effect at the end of the current billing
                period. Refunds for unused time are at our discretion.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                6. Termination
              </h2>
              <p className="mt-4">
                You may terminate your account at any time. We may suspend or
                terminate accounts for violation of these Terms, for
                non-payment, or for activity that risks the integrity of the
                service. On termination, your data is retained per the{' '}
                <a
                  href="/privacy"
                  className="text-violet-400 hover:text-violet-300"
                >
                  Privacy Policy
                </a>{' '}
                retention schedule, then deleted.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                7. Limitation of liability
              </h2>
              <p className="mt-4">
                To the maximum extent permitted by law, QuillMD&apos;s
                total liability for any claim arising out of these Terms is
                limited to the fees you paid us in the twelve months preceding
                the claim. We are not liable for indirect, incidental, or
                consequential damages.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                8. Governing law
              </h2>
              <p className="mt-4">
                These Terms are governed by the laws of the United States.
                Any dispute will be resolved in the state and federal courts
                serving our registered business address (AshTech Group).
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                9. Changes to these Terms
              </h2>
              <p className="mt-4">
                We may update these Terms. Material changes will be announced
                in-app and via email before taking effect. Continued use of
                the service after the effective date constitutes acceptance.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                10. Contact
              </h2>
              <p className="mt-4">
                Legal questions: <code>legal@ashtechgroup.com</code>. General
                support: <code>support@ashtechgroup.com</code>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
