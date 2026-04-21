'use client';

import Link from 'next/link';
import { Plus, Search } from 'lucide-react';
import { motion, useScroll, useTransform } from 'framer-motion';

import { SpecularButton } from '@/components/specular-button';
import { UserMenu } from '@/components/user-menu';
import { formatCommandKey } from '@/lib/shortcuts';

interface NavBarProps {
  name: string | null;
  email: string;
}

/**
 * Top navigation — wordmark + violet orb icon on the left, Cmd+K
 * search trigger + "+ New Visit" CTA + UserMenu on the right. Backdrop
 * goes glassmorphic on scroll (useScroll → useTransform).
 *
 * Mobile (<sm): "+ New Visit" text collapses to an icon-only circle so
 * the bar still fits on a 375px viewport without squishing the
 * wordmark. The search trigger disappears below sm — Cmd+K is still
 * accessible from the keyboard.
 */
export function NavBar({ name, email }: NavBarProps) {
  const { scrollY } = useScroll();
  const bg = useTransform(
    scrollY,
    [0, 80],
    ['rgba(8,9,13,0)', 'rgba(8,9,13,0.7)']
  );
  const borderOpacity = useTransform(scrollY, [0, 80], [0, 1]);
  const blur = useTransform(scrollY, [0, 80], ['blur(0px)', 'blur(12px)']);

  function openCommandPalette() {
    // Synthesize the same keyboard event the palette listens for so we
    // don't need to plumb an imperative "open" API through context.
    const evt = new KeyboardEvent('keydown', {
      key: 'k',
      metaKey: true,
      ctrlKey: true,
      bubbles: true,
    });
    window.dispatchEvent(evt);
  }

  return (
    <motion.nav
      style={{
        backgroundColor: bg,
        backdropFilter: blur,
        WebkitBackdropFilter: blur,
      }}
      className="sticky top-0 z-40 w-full"
    >
      <motion.div
        style={{ opacity: borderOpacity }}
        className="absolute inset-x-0 bottom-0 h-px bg-border-subtle"
      />
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:gap-6 sm:px-6 lg:px-8">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 text-[15px] font-semibold tracking-tight text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-md"
        >
          <span
            aria-hidden
            className="inline-block h-3 w-3 rounded-full bg-[radial-gradient(circle_at_30%_30%,#C4B5FD_0%,#7C3AED_55%,#4C1D95_100%)] shadow-[0_0_12px_rgba(139,92,246,0.6)]"
          />
          QuillMD
        </Link>

        <div className="flex items-center gap-2 sm:gap-3">
          {/* Cmd+K search trigger — desktop only. Mobile users get the
              keyboard shortcut if they have a bluetooth keyboard; touch
              users get N via the empty-state tips + CTA. */}
          <button
            type="button"
            onClick={openCommandPalette}
            aria-label="Open command palette"
            className="hidden sm:inline-flex items-center gap-2 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1.5 text-[12px] text-text-tertiary transition-colors duration-150 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
          >
            <Search className="h-3.5 w-3.5" aria-hidden />
            <span>Search</span>
            <kbd className="ml-2 rounded bg-bg-surface-3 px-1.5 py-0.5 text-[10px] font-medium">
              {formatCommandKey('K')}
            </kbd>
          </button>

          {/* New-visit CTA — full pill on sm+, icon-only circle on mobile. */}
          <SpecularButton
            href="/visits/new"
            variant="primary"
            size="sm"
            className="hidden sm:inline-flex"
          >
            <Plus className="h-3.5 w-3.5" />
            New Visit
          </SpecularButton>
          <Link
            href="/visits/new"
            aria-label="New visit"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3),0_8px_24px_-8px_rgba(124,58,237,0.6)] transition-shadow duration-200 hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5),0_10px_28px_-8px_rgba(124,58,237,0.8)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base sm:hidden"
          >
            <Plus className="h-4 w-4" aria-hidden />
          </Link>

          <UserMenu name={name} email={email} />
        </div>
      </div>
    </motion.nav>
  );
}
