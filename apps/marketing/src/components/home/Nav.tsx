import Link from 'next/link';
import { APP_URL, APP_WAITLIST_URL } from '@/lib/constants';

const LINKS = [
  { href: '/#how', label: 'How' },
  { href: '/#features', label: 'Features' },
  { href: '/#compare', label: 'Vs. others' },
  { href: '/#security', label: 'Security' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'FAQ' },
];

/**
 * Sticky 56px top nav — Phase 7 v6 (Apple Product).
 *
 * Translucent + blurred surface, sage gradient brand-quill, mid-nav links,
 * mono ⌘K chip, sign-in link, sage primary "Get started" pill.
 */
export function Nav() {
  return (
    <nav className="top">
      <div className="container nav-inner">
        <Link href="/" className="brand">
          <span className="brand-quill" aria-hidden />
          <span>QuillMD</span>
        </Link>
        <div className="nav-links">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </div>
        <div className="nav-cta">
          <span className="cmdk-chip" aria-hidden>
            ⌘K
          </span>
          <a href={APP_URL} className="nav-item">
            Sign in
          </a>
          <a href={APP_WAITLIST_URL} className="btn btn-primary">
            Get started
          </a>
        </div>
      </div>
    </nav>
  );
}
