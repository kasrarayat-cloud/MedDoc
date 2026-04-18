'use client';

import Link from 'next/link';
import { Plus } from 'lucide-react';
import { motion, useScroll, useTransform } from 'framer-motion';

import { SpecularButton } from '@/components/specular-button';
import { UserMenu } from '@/components/user-menu';

interface NavBarProps {
  name: string | null;
  email: string;
}

/**
 * Top navigation — wordmark + violet orb icon on the left, "+ New Visit"
 * CTA + UserMenu on the right. Backdrop goes glassmorphic on scroll
 * (framer-motion useScroll + useTransform, same pattern as marketing).
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
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-3 lg:px-8">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 text-[15px] font-semibold tracking-tight text-text-primary"
        >
          <span
            aria-hidden
            className="inline-block h-3 w-3 rounded-full bg-[radial-gradient(circle_at_30%_30%,#C4B5FD_0%,#7C3AED_55%,#4C1D95_100%)] shadow-[0_0_12px_rgba(139,92,246,0.6)]"
          />
          TranscribeMD
        </Link>

        <div className="flex items-center gap-3">
          <SpecularButton href="/visits/new" variant="primary" size="sm">
            <Plus className="h-3.5 w-3.5" />
            New Visit
          </SpecularButton>
          <UserMenu name={name} email={email} />
        </div>
      </div>
    </motion.nav>
  );
}
