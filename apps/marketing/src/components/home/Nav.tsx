import Link from 'next/link';
import { APP_URL, APP_SIGNUP_URL } from '@/lib/constants';

const LINKS = [
  { href: '/#how', label: 'How' },
  { href: '/#features', label: 'Features' },
  { href: '/#compare', label: 'Vs. others' },
  { href: '/#security', label: 'Security' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'FAQ' },
];

/**
 * Sticky 48px top nav — Linear V1 (Faithful).
 *
 * Source of truth: docs/design-directions-v8-linear/landing-v1.html lines
 * 776–794. Sage logo mark, mid-nav links, mono Cmd-K chip + sign-in link
 * + sage primary "Get started" pill on the right.
 *
 * The mark is the standard Linear V1 sage rounded-square (set in CSS via
 * `.brand-quill::after`); we drop the SVG quill in favour of the plain
 * sage-on-bg lockup the Linear V1 mockup uses for the wordmark.
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
          <span
            className="cmdk-chip"
            aria-hidden
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '3px 7px',
              border: '1px solid var(--color-linear-border)',
              borderRadius: 5,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--color-linear-text-3)',
              background: 'var(--color-linear-surface-1)',
            }}
          >
            ⌘K
          </span>
          <a href={APP_URL} className="nav-item">
            Sign in
          </a>
          <a href={APP_SIGNUP_URL} className="btn btn-primary">
            Get started
          </a>
        </div>
      </div>
    </nav>
  );
}
