import Link from 'next/link';

type FooterLink = { href: string; label: string; external?: boolean };

/**
 * Home page footer — Linear V1 (Faithful).
 *
 * Mirrors landing-v1.html lines 1067-1126: brand block + 4 columns + a
 * mono compliance footer at the bottom. Drop the QuillMark SVG (Linear
 * V1 wordmark uses .brand-quill::after's flat sage square). landing.css
 * already styles .foot/.foot-grid/.foot-bottom to Linear V1 tokens.
 */
const COLUMNS: { title: string; links: FooterLink[] }[] = [
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
          <div>
            <Link href="/" className="brand">
              <span className="brand-quill" aria-hidden />
              <span>QuillMD</span>
            </Link>
            <p
              style={{
                marginTop: 14,
                fontSize: 13,
                color: 'var(--color-linear-text-3)',
                lineHeight: 1.55,
                maxWidth: 220,
              }}
            >
              The medical scribe that practitioners actually use. Made in the US, audited
              end-to-end.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title} className="foot-col">
              <h4>{col.title}</h4>
              <ul>
                {col.links.map((link) =>
                  link.external ? (
                    <li key={link.href}>
                      <a href={link.href} target="_blank" rel="noopener noreferrer">
                        {link.label}
                      </a>
                    </li>
                  ) : (
                    <li key={link.href}>
                      <Link href={link.href}>{link.label}</Link>
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </div>
        <div className="foot-bottom">
          <span>© {new Date().getFullYear()} QuillMD, Inc. All rights reserved.</span>
          <div
            className="legal"
            style={{
              display: 'flex',
              gap: 14,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
            }}
          >
            <span>HIPAA</span>
            <span>·</span>
            <span>SOC 2 TYPE II</span>
            <span>·</span>
            <span>US-HOSTED</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
