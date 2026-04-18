'use client';

import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { ArrowRight, Play } from 'lucide-react';
import { AnimatedGrid } from '@/components/animated-grid';
import { Badge } from '@/components/badge';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

// Three.js SSR's into bundle bloat; load only client-side.
const DocumentStream3D = dynamic(
  () =>
    import('@/components/document-stream-3d').then(
      (mod) => mod.DocumentStream3D
    ),
  { ssr: false }
);

// 100ms stagger on hero lines — each line fades up in sequence so the
// eye tracks the phrase the way it would read it aloud.
const heroLines = ['SEND AUDIO.', 'GET A SIGNED NOTE.', '5 MINUTES.'];

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 pb-20 lg:pt-36 lg:pb-32">
      <AnimatedGrid />

      {/* Violet radial haze — colours the top third of the section. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[800px]"
        style={{
          background:
            'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(139,92,246,0.22) 0%, rgba(124,58,237,0.06) 40%, transparent 70%)',
        }}
      />

      <div className="relative z-10 mx-auto max-w-7xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
          className="flex justify-center"
        >
          <Badge dot="cyan">Now in private beta</Badge>
        </motion.div>

        <h1 className="mt-8 text-center type-display">
          {heroLines.map((line, i) => (
            <motion.span
              key={line}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.55,
                ease: [0.4, 0, 0.2, 1],
                delay: 0.12 + i * 0.1,
              }}
              className="block"
            >
              {i === 2 ? <GradientText>{line}</GradientText> : line}
            </motion.span>
          ))}
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.5 }}
          className="mx-auto mt-8 max-w-2xl text-center text-[18px] leading-relaxed text-text-secondary"
        >
          The AI medical transcription service that replaces your old one.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1], delay: 0.6 }}
          className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <SpecularButton href={APP_SIGNUP_URL} variant="primary" size="lg">
            Start free trial
            <ArrowRight className="h-4 w-4" />
          </SpecularButton>
          <SpecularButton
            href="/demo"
            variant="secondary"
            size="lg"
            sweep={false}
          >
            <Play className="h-3.5 w-3.5" />
            See 60s demo
          </SpecularButton>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.75 }}
          className="mt-5 text-center text-[13px] text-text-muted"
        >
          $0/month for first 14 days. No credit card.
        </motion.p>

        {/* 3D stream — fills the remaining viewport height below the
            CTAs on desktop. On mobile the Canvas is a bit shorter to
            keep time-to-interactive snappy. */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.4, ease: [0.4, 0, 0.2, 1] }}
          className="mt-16 flex justify-center"
        >
          <div className="relative h-[440px] w-full max-w-5xl sm:h-[520px] lg:h-[580px]">
            {/* Soft glow plate under the canvas — adds weight to the
                scene without making the canvas itself opaque. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-8 top-1/2 h-[60%] -translate-y-1/2 rounded-[40%]"
              style={{
                background:
                  'radial-gradient(ellipse at center, rgba(139,92,246,0.28) 0%, transparent 70%)',
                filter: 'blur(48px)',
              }}
            />
            <DocumentStream3D className="h-full w-full" />
            {/* Top fade so the canvas blends into the hero text area. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-0 h-24"
              style={{
                background:
                  'linear-gradient(to bottom, #08090D 0%, transparent 100%)',
              }}
            />
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-24"
              style={{
                background:
                  'linear-gradient(to top, #08090D 0%, transparent 100%)',
              }}
            />
          </div>
        </motion.div>
      </div>
    </section>
  );
}
