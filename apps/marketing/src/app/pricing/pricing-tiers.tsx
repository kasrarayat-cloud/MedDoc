'use client';

import { motion } from 'framer-motion';
import { Check, ArrowRight } from 'lucide-react';
import { GlowCard } from '@/components/glow-card';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { cn } from '@/lib/cn';

// TODO: Real pricing to be finalized after pilot. These tiers are
// placeholders and should not be communicated externally until then.
const TIERS = [
  {
    name: 'Free Trial',
    price: '$0',
    priceSuffix: '/14 days',
    blurb: 'Try the full product with real audio, no commitment.',
    cta: 'Start free trial',
    highlight: false,
    features: [
      '10 signed notes',
      'Batch + live transcription',
      'Signed SOAP + ICD-10 + Rx',
      'Email support',
    ],
  },
  {
    name: 'Pro',
    price: '$49',
    priceSuffix: '/month',
    blurb: 'For the solo doctor shipping notes daily.',
    cta: 'Start Pro',
    highlight: true,
    features: [
      '200 signed notes / month',
      'Batch + live transcription',
      'Full output bundle',
      'EHR macro export',
      'Priority email support',
    ],
  },
  {
    name: 'Unlimited',
    price: '$149',
    priceSuffix: '/month',
    blurb: 'High-volume practices + small clinics.',
    cta: 'Start Unlimited',
    highlight: false,
    features: [
      'Unlimited notes',
      'Everything in Pro',
      'Custom specialty templates',
      'Audit-log UI',
      'Same-day support',
    ],
  },
];

export function PricingTiers() {
  return (
    <section className="relative pb-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {TIERS.map((tier, i) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{
                duration: 0.5,
                ease: [0.4, 0, 0.2, 1],
                delay: i * 0.08,
              }}
              className="h-full"
            >
              {tier.highlight ? (
                <GradientBorder className="relative h-full">
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-white shadow-[0_6px_24px_-8px_rgba(124,58,237,0.8)]">
                      Most popular
                    </span>
                  </div>
                  <TierBody tier={tier} />
                </GradientBorder>
              ) : (
                <GlowCard className="h-full">
                  <TierBody tier={tier} />
                </GlowCard>
              )}
            </motion.div>
          ))}
        </div>
        <p className="mt-6 text-center text-[12px] text-text-muted">
          Prices in USD. Cancel anytime; we pro-rate your last month.
        </p>
      </div>
    </section>
  );
}

function TierBody({ tier }: { tier: (typeof TIERS)[number] }) {
  return (
    <div className="flex h-full flex-col p-8">
      <h3 className="text-[14px] font-semibold uppercase tracking-[0.12em] text-text-muted">
        {tier.name}
      </h3>
      <div className="mt-5 flex items-baseline gap-1">
        <span
          className={cn(
            'text-[52px] font-bold tracking-tight leading-none',
            tier.highlight && 'text-transparent',
          )}
          style={
            tier.highlight
              ? {
                  background:
                    'linear-gradient(135deg, #C4B5FD 0%, #A78BFA 60%, #E9D5FF 100%)',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }
              : undefined
          }
        >
          {tier.highlight ? <GradientText>{tier.price}</GradientText> : tier.price}
        </span>
        <span className="text-[14px] text-text-tertiary">{tier.priceSuffix}</span>
      </div>
      <p className="mt-4 text-[14px] leading-relaxed text-text-tertiary">
        {tier.blurb}
      </p>
      <ul className="mt-6 space-y-3">
        {tier.features.map((f) => (
          <li key={f} className="flex items-start gap-3 text-[14px] text-text-secondary">
            <span className="mt-0.5 inline-flex h-4 w-4 flex-none items-center justify-center rounded-full bg-violet-500/15 text-violet-300">
              <Check className="h-3 w-3" />
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-8 pt-6 border-t border-border-subtle">
        <SpecularButton
          href="/signup"
          variant={tier.highlight ? 'primary' : 'secondary'}
          size="md"
          className="w-full"
        >
          {tier.cta}
          <ArrowRight className="h-4 w-4" />
        </SpecularButton>
      </div>
    </div>
  );
}
