'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import { SpecularButton } from './specular-button';

/**
 * Sticky nav. Transparent at page top; as soon as the page scrolls, a
 * glassmorphic surface + border fades in. Follows Linear's pattern of a
 * thin translucent bar that never competes with hero content but still
 * frames the page above the fold.
 */
const LINKS = [
  { href: '/#how', label: 'How it works' },
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
        'fixed top-0 left-0 right-0 z-50',
        'transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
        scrolled
          ? 'bg-bg-base/70 backdrop-blur-xl border-b border-border-subtle'
          : 'bg-transparent border-b border-transparent'
      )}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-8">
        <Link
          href="/"
          className="group flex items-center gap-2 text-[15px] font-semibold tracking-tight text-text-primary"
        >
          {/* Logo mark — a violet diamond that spins 90° on hover. */}
          <span className="relative inline-flex h-6 w-6 items-center justify-center">
            <span
              aria-hidden
              className="block h-4 w-4 rotate-45 rounded-[3px] bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] transition-transform duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] group-hover:rotate-[135deg]"
            />
          </span>
          <span>TranscribeMD</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-full px-3 py-1.5 text-[13px] text-text-tertiary transition-colors hover:text-text-primary"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <SpecularButton
            href="/signup"
            variant="ghost"
            size="sm"
            className="hidden sm:inline-flex"
            sweep={false}
          >
            Sign in
          </SpecularButton>
          <SpecularButton href="/signup" variant="primary" size="sm">
            Start free trial
          </SpecularButton>
        </div>
      </div>
    </header>
  );
}
