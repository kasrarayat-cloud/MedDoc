'use client';

import { motion } from 'framer-motion';
import {
  Sparkles,
  Layers,
  Timer,
  ShieldCheck,
  MousePointerClick,
  Gauge,
} from 'lucide-react';
import { GlowCard } from '@/components/glow-card';

const FEATURES = [
  {
    icon: Sparkles,
    title: 'AI self-critique',
    body:
      'Every SOAP note is scored section-by-section for confidence. Low-confidence sections get flagged before you ever see them.',
  },
  {
    icon: Layers,
    title: 'Any EHR',
    body:
      'Output is formatted for Epic, Athena, and Cerner macros. Copy the section you need — no re-typing, no reformatting.',
  },
  {
    icon: Timer,
    title: '2–5 min turnaround',
    body:
      'Batch visits finish in the time it takes to grab coffee. Live visits finalise seconds after you sign off.',
  },
  {
    icon: ShieldCheck,
    title: 'HIPAA architected',
    body:
      'Encryption at rest + in transit. Tenant-isolated Postgres + S3. Every action audited. BAAs with every processor.',
  },
  {
    icon: MousePointerClick,
    title: 'No sales call',
    body:
      'Pricing is posted. Signup is a form. Cancellation is a button. Nothing about this should require a 45-minute Zoom.',
  },
  {
    icon: Gauge,
    title: 'Actually accurate',
    body:
      '94–96% transcription accuracy on medical audio. <2% hallucination rate on SOAP generation, verified against a golden set.',
  },
];

export function Features() {
  return (
    <section
      id="features"
      className="relative overflow-hidden border-t border-border-subtle py-24 lg:py-32"
    >
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
          className="max-w-2xl"
        >
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Why it&apos;s different
          </p>
          <h2 className="mt-3 type-h2 text-text-primary">Built different.</h2>
          <p className="mt-4 type-body text-text-tertiary">
            No sales team. No six-figure enterprise contract. Just a tool that
            does exactly what it says — for the price on the page.
          </p>
        </motion.div>

        <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{
                duration: 0.5,
                ease: [0.4, 0, 0.2, 1],
                delay: (i % 3) * 0.06 + Math.floor(i / 3) * 0.04,
              }}
            >
              <GlowCard className="h-full p-6">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-default bg-bg-surface-3/80">
                  <f.icon className="h-4 w-4 text-violet-400" />
                </div>
                <h3 className="mt-4 text-[16px] font-semibold tracking-tight text-text-primary">
                  {f.title}
                </h3>
                <p className="mt-2 text-[14px] leading-relaxed text-text-tertiary">
                  {f.body}
                </p>
              </GlowCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
