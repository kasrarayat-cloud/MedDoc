import Link from 'next/link';
import { QuillMark } from './QuillMark';

type FooterLink = { href: string; label: string; external?: boolean };

const COLUMNS: { title: string; links: FooterLink[] }[] = [
  {
    title: 'Product',
    links: [
      { href: '/#features', label: 'Features' },
      { href: '/#demo', label: 'Live demo' },
      { href: '/#pricing', label: 'Pricing' },
      { href: '/#compare', label: 'Vs. others' },
    ],
  },
  {
    title: 'Trust',
    links: [
      { href: '/#security', label: 'Security' },
      { href: '/hipaa', label: 'HIPAA & BAA' },
      { href: '/privacy', label: 'Privacy policy' },
      { href: '/terms', label: 'Terms of service' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { href: '/#faq', label: 'FAQ' },
      { href: '/demo', label: 'Watch demo' },
      { href: '/about', label: 'About' },
      { href: '/contact', label: 'Contact' },
    ],
  },
  {
    title: 'Contact',
    links: [
      { href: 'mailto:kasra@quillmd.com', label: 'kasra@quillmd.com', external: true },
      { href: '/contact', label: 'Book a call' },
    ],
  },
];

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="foot-grid">
          <div className="foot-brand">
            <Link href="/" className="brand">
              <span className="brand-quill">
                <QuillMark gradientId="footerQuill" />
              </span>
              <span>Quill</span>
            </Link>
            <p className="blurb">
              AI medical scribe for US doctors. Real‑time notes, codes, and Rx for $49 a month.
              Made for doctors, by a doctor&apos;s son.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title} className="foot-col">
              <h6>{col.title}</h6>
              <ul>
                {col.links.map((link) =>
                  link.external ? (
                    <li key={link.href}>
                      <a href={link.href}>{link.label}</a>
                    </li>
                  ) : (
                    <li key={link.href}>
                      <Link href={link.href}>{link.label}</Link>
                    </li>
                  )
                )}
              </ul>
            </div>
          ))}
        </div>
        <div className="foot-bottom">
          <span>© {new Date().getFullYear()} QuillMD · All rights reserved</span>
          <div className="legal">
            <span>Made for doctors, by a doctor&apos;s son</span>
            <span>v1.0 · Built in Brooklyn</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
