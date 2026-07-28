'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import { APP_URL, APP_WAITLIST_URL } from '@/lib/constants';

/**
 * Sub-page top nav — Linear V1 (Faithful).
 *
 * Fixed 48px chrome on the dark canvas, blurred translucent surface,
 * hairline bottom border. Used by every sub-page that doesn't render
 * the home/Nav (pricing, about, contact, demo, hipaa, privacy, security,
 * terms, signup, not-found). The mark is the Linear V1 flat sage square
 * (.brand-quill::after — defined in landing.css).
 */
const LINKS = [
  { href: '/#how', label: 'How' },
  { href: '/#features', label: 'Features' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/about', label: 'About' },
];

export function NavBar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={cn(
        'fixed top-0 left-0 right-0 z-50 transition-all duration-200',
      )}
      style={{
        height: 48,
        background: scrolled
          ? 'rgba(8, 9, 10, 0.78)'
          : 'transparent',
        backdropFilter: scrolled ? 'saturate(180%) blur(12px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'saturate(180%) blur(12px)' : 'none',
        borderBottom: scrolled
          ? '1px solid var(--color-linear-hairline)'
          : '1px solid transparent',
      }}
    >
      <div
        className="container"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 48,
        }}
      >
        <Link href="/" className="brand">
          <span className="brand-quill" aria-hidden />
          <span>QuillMD</span>
        </Link>

        <nav
          className="nav-links"
          style={{
            display: 'flex',
            gap: 22,
          }}
        >
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href}>
              {l.label}
            </Link>
          ))}
        </nav>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <a
            href={`${APP_URL}/login`}
            className="nav-item"
            style={{ display: 'inline-flex', alignItems: 'center' }}
          >
            Sign in
          </a>
          <a href={APP_WAITLIST_URL} className="btn btn-primary">
            Get started
          </a>
        </div>
      </div>
    </header>
  );
}
