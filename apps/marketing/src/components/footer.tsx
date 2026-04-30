import Link from 'next/link';
import { QuillMark } from './home/QuillMark';

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
 * Sub-page footer (used by pricing, about, contact, demo, hipaa, privacy,
 * security, terms, signup, not-found). Cream-2 surface, sage hairline
 * dividers, ink-feather wordmark.
 */
export function Footer() {
  return (
    <footer className="border-t border-[rgba(43,38,32,0.08)] bg-[#F2EDE3]">
      <div className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2.5">
              <span className="inline-grid h-[22px] w-[22px] place-items-center">
                <QuillMark />
              </span>
              <span
                className="text-[20px] tracking-[0.02em] text-[#2B2620]"
                style={{ fontFamily: 'var(--font-serif), Georgia, serif', fontWeight: 500 }}
              >
                Quill
              </span>
            </div>
            <p
              className="mt-4 text-[14px] leading-relaxed text-[#5C544A]"
              style={{ fontFamily: 'var(--font-serif), Georgia, serif' }}
            >
              Made for doctors who deserve better tools.
            </p>
          </div>
          {COLS.map((col) => (
            <div key={col.title}>
              <h3 className="text-[11.5px] font-medium uppercase tracking-[0.10em] text-[#8A8278]">
                {col.title}
              </h3>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) =>
                  l.external ? (
                    <li key={l.href}>
                      <a
                        href={l.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[13.5px] text-[#5C544A] transition-colors hover:text-[#2F5040]"
                      >
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.href}>
                      <Link
                        href={l.href}
                        className="text-[13.5px] text-[#5C544A] transition-colors hover:text-[#2F5040]"
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
        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-[rgba(43,38,32,0.08)] pt-6 text-[12px] text-[#8A8278] md:flex-row md:items-center">
          <p>© {new Date().getFullYear()} QuillMD. All rights reserved.</p>
          <p className="flex items-center gap-2">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#7AA68C]" />
            All systems operational
          </p>
        </div>
      </div>
    </footer>
  );
}
