'use client';

import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';

import { SpecularButton } from '@/components/specular-button';
import { formatCommandKey } from '@/lib/shortcuts';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-56 w-56" /> }
);

/**
 * Dashboard empty state — orb, headline, CTA, and three shortcut hints.
 * Staggered fade: orb → headline → sub → CTA → tips (60ms between each)
 * so the page reveals itself as the user's eye travels down.
 */
export function EmptyState() {
  const base = { ease: [0.4, 0, 0.2, 1] as [number, number, number, number] };

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.9, ...base }}
        className="relative mb-10 h-64 w-64 sm:h-72 sm:w-72"
      >
        {/* Outer halo — CSS-pulsed, slower than the R3F pulse inside the
            orb so the two rhythms never lock in phase. */}
        <div
          aria-hidden
          className="orb-pulse pointer-events-none absolute inset-0 -z-10 rounded-full"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(139,92,246,0.42) 0%, rgba(139,92,246,0.12) 40%, transparent 72%)',
            filter: 'blur(28px)',
          }}
        />
        <VioletOrb radius={1.35} quiet />
      </motion.div>

      <motion.h2
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, delay: 0.25, ...base }}
        className="type-h1 text-text-primary"
      >
        Your first visit is one click away.
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.35, ...base }}
        className="mt-3 max-w-md text-[15px] leading-relaxed text-text-tertiary"
      >
        Upload audio, dictate live, or paste text notes. QuillMD turns it
        into a signed SOAP note in minutes.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.45, ...base }}
        className="mt-8"
      >
        <SpecularButton href="/visits/new" variant="primary" size="lg">
          <Plus className="h-4 w-4" />
          New Visit
        </SpecularButton>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6, ...base }}
        className="mt-12 flex flex-col items-center gap-2 text-[12px] text-text-muted sm:flex-row sm:gap-6"
      >
        <ShortcutTip keys={['N']} label="create a new visit" />
        <ShortcutTip keys={[formatCommandKey('K')]} label="search anything" />
        <ShortcutTip keys={['S']} label="open settings" />
      </motion.div>
    </div>
  );
}

function ShortcutTip({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="flex items-center gap-1">
        {keys.map((k) => (
          <kbd
            key={k}
            className="rounded-md bg-bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary ring-1 ring-border-subtle"
          >
            {k}
          </kbd>
        ))}
      </span>
      <span>{label}</span>
    </span>
  );
}
