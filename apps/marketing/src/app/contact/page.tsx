import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Contact',
  description:
    'Ways to reach QuillMD for support, sales, compliance, and security.',
};

const ITEMS: { label: string; email: string; helper: React.ReactNode }[] = [
  {
    label: 'General support',
    email: 'support@ashtechgroup.com',
    helper: 'Account help, billing, questions about the product.',
  },
  {
    label: 'Sales',
    email: 'sales@ashtechgroup.com',
    helper: 'Multi-seat deals, group practices, custom billing.',
  },
  {
    label: 'Compliance & BAAs',
    email: 'compliance@ashtechgroup.com',
    helper: 'Business Associate Agreements, HIPAA questions.',
  },
  {
    label: 'Security',
    email: 'security@ashtechgroup.com',
    helper:
      'Vulnerability reports, coordinated disclosure. Please do not file GitHub issues for security.',
  },
  {
    label: 'Privacy',
    email: 'privacy@ashtechgroup.com',
    helper: (
      <>
        Data requests (access / correction / deletion) per our{' '}
        <a
          href="/privacy"
          style={{
            color: 'var(--color-linear-sage-bright)',
            textDecoration: 'underline',
            textDecorationColor: 'rgba(122,166,140,0.4)',
          }}
        >
          Privacy Policy
        </a>
        .
      </>
    ),
  },
  {
    label: 'Legal',
    email: 'legal@ashtechgroup.com',
    helper: 'Contracts, IP, disputes.',
  },
];

export default function ContactPage() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 64 }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0"
            style={{
              height: 500,
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="container" style={{ maxWidth: 760, position: 'relative' }}>
            <Badge dot="violet">Contact</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              Get in touch
            </h1>
            <p className="hero-sub" style={{ marginTop: 20, marginInline: 0, textAlign: 'left' }}>
              We&apos;re a small team. You&apos;ll reach a human, usually the
              same day.
            </p>
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
          <div className="container" style={{ maxWidth: 760 }}>
            <dl
              style={{
                display: 'grid',
                gap: 32,
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              }}
            >
              {ITEMS.map((item) => (
                <div key={item.email}>
                  <dt
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: 'var(--color-linear-text-3)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {item.label}
                  </dt>
                  <dd style={{ marginTop: 8 }}>
                    <a
                      href={`mailto:${item.email}`}
                      style={{
                        fontSize: 15,
                        color: 'var(--color-linear-sage-bright)',
                        textDecoration: 'underline',
                        textDecorationColor: 'rgba(122,166,140,0.4)',
                      }}
                    >
                      {item.email}
                    </a>
                  </dd>
                  <p
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      color: 'var(--color-linear-text-3)',
                      lineHeight: 1.55,
                    }}
                  >
                    {item.helper}
                  </p>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
