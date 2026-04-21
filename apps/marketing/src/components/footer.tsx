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

export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-bg-surface-1/40 backdrop-blur">
      <div className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className="block h-4 w-4 rotate-45 rounded-[3px] bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)]"
              />
              <span className="text-[15px] font-semibold tracking-tight text-text-primary">
                QuillMD
              </span>
            </div>
            <p className="mt-4 text-[13px] leading-relaxed text-text-tertiary">
              Made for doctors who deserve better tools.
            </p>
          </div>
          {COLS.map((col) => (
            <div key={col.title}>
              <h3 className="text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                {col.title}
              </h3>
              <ul className="mt-4 space-y-2">
                {col.links.map((l) =>
                  l.external ? (
                    <li key={l.href}>
                      <a
                        href={l.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[13px] text-text-tertiary transition-colors hover:text-text-primary"
                      >
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.href}>
                      <Link
                        href={l.href}
                        className="text-[13px] text-text-tertiary transition-colors hover:text-text-primary"
                      >
                        {l.label}
                      </Link>
                    </li>
                  )
                )}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-border-subtle pt-6 text-[12px] text-text-muted md:flex-row md:items-center">
          <p>© {new Date().getFullYear()} QuillMD. All rights reserved.</p>
          <p className="flex items-center gap-1">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan-400" />
            All systems operational
          </p>
        </div>
      </div>
    </footer>
  );
}
