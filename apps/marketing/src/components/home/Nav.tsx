import Link from 'next/link';
import { APP_URL, APP_SIGNUP_URL } from '@/lib/constants';
import { QuillMark } from './QuillMark';

const LINKS = [
  { href: '/#how', label: 'How' },
  { href: '/#features', label: 'Features' },
  { href: '/#compare', label: 'Vs. others' },
  { href: '/#security', label: 'Security' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'FAQ' },
];

/**
 * Sticky cream-blur top nav. Wordmark uses the Clinician "Quill" lockup
 * (Source Serif 4 + sage ink-feather mark) per the landing mockup; the
 * "MD" italic suffix is dropped because the Clinician brand mark is just
 * "Quill" (the sub-domain remains quillmd.com — that's the URL, not the
 * brand).
 */
export function Nav() {
  return (
    <nav className="top">
      <div className="container nav-inner">
        <Link href="/" className="brand">
          <span className="brand-quill">
            <QuillMark gradientId="navQuill" />
          </span>
          <span>Quill</span>
        </Link>
        <div className="nav-links">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </div>
        <div className="nav-cta">
          <a href={APP_URL} className="btn btn-ghost">
            Sign in
          </a>
          <a href={APP_SIGNUP_URL} className="btn btn-primary">
            Begin a visit <span className="arrow">→</span>
          </a>
        </div>
      </div>
    </nav>
  );
}
