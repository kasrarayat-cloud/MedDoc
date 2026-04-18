'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { AnimatedGrid } from '@/components/animated-grid';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';

export function FinalCTA() {
  return (
    <section className="relative overflow-hidden border-t border-border-subtle bg-bg-surface-1/30 py-28 lg:py-40">
      <AnimatedGrid />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-1/2 h-[400px] -translate-y-1/2"
        style={{
          background:
            'radial-gradient(ellipse 60% 80% at 50% 50%, rgba(139,92,246,0.22) 0%, transparent 65%)',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
        className="relative mx-auto max-w-3xl px-6 text-center lg:px-8"
      >
        <h2 className="type-h1 text-text-primary">
          Ready to stop
          <br />
          <GradientText>typing notes?</GradientText>
        </h2>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <SpecularButton href="/signup" variant="primary" size="lg">
            Start free trial
            <ArrowRight className="h-4 w-4" />
          </SpecularButton>
          <SpecularButton href="/demo" variant="secondary" size="lg" sweep={false}>
            Watch demo
          </SpecularButton>
        </div>
        <p className="mt-6 text-[13px] text-text-muted">
          14-day free trial. No credit card required.
        </p>
      </motion.div>
    </section>
  );
}
