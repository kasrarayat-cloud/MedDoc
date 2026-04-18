'use client';

import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';

import { SpecularButton } from '@/components/specular-button';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-40 w-40" /> }
);

export function EmptyState() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-20 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
        className="relative mb-8 h-48 w-48"
      >
        {/* Soft halo behind the orb so it feels grounded, not floating. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 rounded-full"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(139,92,246,0.35) 0%, rgba(139,92,246,0.08) 40%, transparent 70%)',
            filter: 'blur(24px)',
          }}
        />
        <VioletOrb radius={1.15} />
      </motion.div>

      <motion.h2
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.2 }}
        className="type-h1 text-text-primary"
      >
        Your first visit is one click away.
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.3 }}
        className="mt-3 max-w-md text-[15px] leading-relaxed text-text-tertiary"
      >
        Upload audio, dictate live, or paste text notes. TranscribeMD turns it
        into a signed SOAP note in minutes.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.4 }}
        className="mt-8"
      >
        <SpecularButton href="/visits/new" variant="primary" size="lg">
          <Plus className="h-4 w-4" />
          New Visit
        </SpecularButton>
      </motion.div>
    </div>
  );
}
