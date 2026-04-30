'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import { APP_URL, APP_SIGNUP_URL } from '@/lib/constants';
import { QuillMark } from './home/QuillMark';
import { SpecularButton } from './specular-button';

/**
 * Sticky cream-blur top nav, used by every sub-page (pricing, about,
 * contact, demo, hipaa, privacy, security, terms, signup, not-found).
 * Mirrors the Clinician topnav style from landing-and-recording.html.
 * Transparent at page top; cream-blur surface fades in once the page
 * scrolls so it doesn't compete with hero content above the fold.
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
        'transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]',
        scrolled
          ? 'bg-[rgba(250,247,242,0.85)] backdrop-blur-xl border-b border-[rgba(43,38,32,0.08)]'
          : 'bg-transparent border-b border-transparent'
      )}
    >
      <div className="mx-auto flex h-[68px] max-w-7xl items-center justify-between px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-[20px] tracking-[0.02em] text-[#2B2620]"
          style={{ fontFamily: 'var(--font-serif), Georgia, serif', fontWeight: 500 }}
        >
          <span className="inline-grid h-[22px] w-[22px] place-items-center">
            <QuillMark />
          </span>
          <span>Quill</span>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-[14px] text-[#5C544A] transition-colors hover:text-[#2B2620]"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <SpecularButton
            href={`${APP_URL}/login`}
            variant="ghost"
            size="sm"
            className="hidden sm:inline-flex"
            sweep={false}
          >
            Sign in
          </SpecularButton>
          <SpecularButton href={APP_SIGNUP_URL} variant="primary" size="sm">
            Begin a visit
          </SpecularButton>
        </div>
      </div>
    </header>
  );
}
