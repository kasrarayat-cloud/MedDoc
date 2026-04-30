'use client';

import { motion } from 'framer-motion';
import { Check, ArrowRight } from 'lucide-react';
import { GlowCard } from '@/components/glow-card';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { cn } from '@/lib/cn';
import { APP_SIGNUP_URL } from '@/lib/constants';

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
                    <span className="rounded-full bg-[#2F5040] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.10em] text-[#FFFCF5] shadow-[0_6px_18px_rgba(122,166,140,0.36)]">
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
      <h3 className="qm-cl-eyebrow">{tier.name}</h3>
      <div className="mt-5 flex items-baseline gap-1">
        <span
          className={cn(
            'text-[52px] tracking-tight leading-none text-[#2B2620]',
            tier.highlight && 'text-transparent',
          )}
          style={{
            fontFamily: 'var(--font-serif), Georgia, serif',
            fontWeight: 400,
          }}
        >
          {tier.highlight ? <GradientText>{tier.price}</GradientText> : tier.price}
        </span>
        <span className="text-[14px] text-[#5C544A]">{tier.priceSuffix}</span>
      </div>
      <p
        className="mt-4 text-[15px] leading-relaxed text-[#5C544A]"
        style={{ fontFamily: 'var(--font-serif), Georgia, serif' }}
      >
        {tier.blurb}
      </p>
      <ul className="mt-6 space-y-3">
        {tier.features.map((f) => (
          <li
            key={f}
            className="flex items-start gap-3 text-[15px] text-[#2B2620]"
            style={{ fontFamily: 'var(--font-serif), Georgia, serif' }}
          >
            <span className="mt-1 inline-flex h-4 w-4 flex-none items-center justify-center rounded-full bg-[rgba(122,166,140,0.18)] text-[#2F5040]">
              <Check className="h-3 w-3" />
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-8 pt-6 border-t border-[rgba(43,38,32,0.08)]">
        <SpecularButton
          href={APP_SIGNUP_URL}
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
