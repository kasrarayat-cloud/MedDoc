import Link from 'next/link';

/**
 * Footer — Phase 7 v6 (Apple Product).
 *
 * 5-column grid (brand 1.6fr + 4 link cols 1fr each). Mobile collapses to
 * 1fr 1fr (and then 1fr at ≤640px). Mono compliance line at the bottom.
 */
type FooterCol = { title: string; links: { href: string; label: string }[] };

const COLUMNS: FooterCol[] = [
  {
    title: 'Product',
    links: [
      { href: '/#features', label: 'Features' },
      { href: '/#demo', label: 'Live demo' },
      { href: '/pricing', label: 'Pricing' },
      { href: '/#compare', label: 'Vs. others' },
    ],
  },
  {
    title: 'Company',
    links: [
      { href: '/about', label: 'About' },
      { href: '/contact', label: 'Contact' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { href: '/privacy', label: 'Privacy' },
      { href: '/terms', label: 'Terms' },
      { href: '/hipaa', label: 'HIPAA & BAA' },
    ],
  },
  {
    title: 'Trust',
    links: [
      { href: '/security', label: 'Security' },
      { href: '/#faq', label: 'FAQ' },
    ],
  },
];

export function Footer() {
  return (
    <footer className="foot">
      <div className="container">
        <div className="foot-grid">
          <div className="foot-brand">
            <Link href="/" className="brand">
              <span className="brand-quill" aria-hidden />
              <span>QuillMD</span>
            </Link>
            <p>
              The medical scribe that practitioners actually use. Made in the US, audited
              end-to-end.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title} className="foot-col">
              <div className="foot-col-title" aria-hidden>
                {col.title}
              </div>
              <nav aria-label={col.title}>
                {col.links.map((link) => (
                  <Link key={link.href} href={link.href}>
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>
          ))}
        </div>
        <div className="foot-bottom">
          <div>© {new Date().getFullYear()} QuillMD, Inc. All rights reserved.</div>
          <div className="legal">
            <span>HIPAA</span>
            <span>·</span>
            <span>US-HOSTED</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
