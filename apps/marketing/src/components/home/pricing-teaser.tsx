'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';

export function PricingTeaser() {
  // TODO: Real pricing to be finalized after pilot. These numbers are
  // placeholders and should NOT be surfaced to real prospects yet.
  return (
    <section className="relative overflow-hidden border-t border-border-subtle py-24 lg:py-32">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(139,92,246,0.12) 0%, transparent 65%)',
        }}
      />

      <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        >
          <GradientBorder className="relative overflow-hidden p-10 text-center lg:p-14">
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">
              Pricing
            </p>
            <div className="mt-4">
              <span className="text-[18px] font-medium text-text-tertiary">
                Starts at
              </span>{' '}
              <span className="type-display align-baseline">
                <GradientText>$49</GradientText>
              </span>{' '}
              <span className="text-[18px] font-medium text-text-tertiary">
                / mo
              </span>
            </div>
            <p className="mt-4 text-[15px] text-text-secondary">
              10 free notes. 14-day trial. No credit card.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <SpecularButton href="/signup" variant="primary" size="md">
                Start free trial
                <ArrowRight className="h-4 w-4" />
              </SpecularButton>
              <Link
                href="/pricing"
                className="group inline-flex items-center gap-1 text-[14px] font-medium text-text-secondary transition-colors hover:text-text-primary"
              >
                See full pricing
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5" />
              </Link>
            </div>
          </GradientBorder>
        </motion.div>
      </div>
    </section>
  );
}
