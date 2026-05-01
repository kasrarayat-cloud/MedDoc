import Link from 'next/link';

// External = absolute URL, opens in new tab. Internal = same-origin Link.
type LinkDef = { href: string; label: string; external?: boolean };
const COLS: { title: string; links: LinkDef[] }[] = [
  {
    title: 'Product',
    links: [
      { href: '/#features', label: 'Features' },
      { href: '/pricing', label: 'Pricing' },
      { href: '/demo', label: 'Demo' },
      {
        href: 'https://github.com/kasrarayat-cloud/MedDoc',
        label: 'Docs',
        external: true,
      },
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
      { href: '/hipaa', label: 'HIPAA' },
      { href: '/security', label: 'Security' },
    ],
  },
  {
    title: 'Social',
    links: [
      {
        href: 'https://github.com/kasrarayat-cloud/MedDoc',
        label: 'GitHub',
        external: true,
      },
    ],
  },
];

/**
 * Sub-page footer — Linear V1 (Faithful).
 *
 * Used by every sub-page (pricing, about, contact, demo, hipaa, privacy,
 * security, terms, signup, not-found). Linear V1 dark surface with the
 * .foot/.foot-grid/.foot-bottom structure styled in landing.css. The
 * mark is the flat sage rounded-square (.brand-quill::after).
 */
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
              Made for doctors who deserve better tools.
            </p>
          </div>
          {COLS.map((col) => (
            <div key={col.title} className="foot-col">
              <h4>{col.title}</h4>
              <ul>
                {col.links.map((l) =>
                  l.external ? (
                    <li key={l.href}>
                      <a href={l.href} target="_blank" rel="noopener noreferrer">
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.href}>
                      <Link href={l.href}>{l.label}</Link>
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </div>
        <div className="foot-bottom">
          <span>© {new Date().getFullYear()} QuillMD. All rights reserved.</span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--color-linear-sage)',
              }}
            />
            All systems operational
          </span>
        </div>
      </div>
    </footer>
  );
}
