import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Contact',
  description:
    'Ways to reach QuillMD for support, sales, compliance, and security.',
};

export default function ContactPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">Contact</Badge>
            <h1 className="mt-6 type-h1">Get in touch</h1>
            <p className="mt-6 type-body">
              We&apos;re a small team. You&apos;ll reach a human, usually the
              same day.
            </p>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-12">
          <div className="mx-auto max-w-3xl px-6 lg:px-8">
            <dl className="grid gap-8 md:grid-cols-2">
              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  General support
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:support@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    support@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Account help, billing, questions about the product.
                </p>
              </div>

              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  Sales
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:sales@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    sales@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Multi-seat deals, group practices, custom billing.
                </p>
              </div>

              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  Compliance &amp; BAAs
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:compliance@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    compliance@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Business Associate Agreements, HIPAA questions.
                </p>
              </div>

              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  Security
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:security@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    security@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Vulnerability reports, coordinated disclosure. Please do
                  not file GitHub issues for security.
                </p>
              </div>

              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  Privacy
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:privacy@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    privacy@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Data requests (access / correction / deletion) per our{' '}
                  <a
                    href="/privacy"
                    className="underline decoration-[rgba(122,166,140,0.35)] hover:text-[#7AA68C]"
                  >
                    Privacy Policy
                  </a>
                  .
                </p>
              </div>

              <div>
                <dt className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                  Legal
                </dt>
                <dd className="mt-2">
                  <a
                    href="mailto:legal@ashtechgroup.com"
                    className="text-[16px] text-[#2F5040] underline decoration-[rgba(122,166,140,0.35)] transition-colors hover:text-[#7AA68C]"
                  >
                    legal@ashtechgroup.com
                  </a>
                </dd>
                <p className="mt-2 text-[13px] text-text-tertiary">
                  Contracts, IP, disputes.
                </p>
              </div>
            </dl>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
