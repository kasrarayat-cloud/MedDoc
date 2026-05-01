'use client';

import { motion } from 'framer-motion';
import { Check, ArrowRight } from 'lucide-react';
import { GlowCard } from '@/components/glow-card';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * Pricing tiers — Linear V1 (Faithful).
 *
 * 3-card grid; the highlighted tier wears a GradientBorder (now flat
 * sage-tint hairline + glow shadow) and a "Most popular" sage pill above.
 * Drop Source Serif body / hardcoded cream hex colors / type-* legacy
 * utility classes.
 *
 * TODO: Real pricing to be finalized after pilot. These tiers are
 * placeholders and should not be communicated externally until then.
 */
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
    <section style={{ paddingBottom: 96 }}>
      <div
        className="container"
        style={{ maxWidth: 1040 }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 16,
          }}
        >
          {TIERS.map((tier, i) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{
                duration: 0.5,
                ease: [0.16, 1, 0.3, 1],
                delay: i * 0.08,
              }}
              style={{ height: '100%', position: 'relative' }}
            >
              {tier.highlight ? (
                <GradientBorder>
                  <div
                    aria-hidden
                    style={{
                      position: 'absolute',
                      top: -12,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      zIndex: 1,
                    }}
                  >
                    <span className="qm-lin-pill qm-lin-pill--sage">
                      Most popular
                    </span>
                  </div>
                  <TierBody tier={tier} />
                </GradientBorder>
              ) : (
                <GlowCard>
                  <TierBody tier={tier} />
                </GlowCard>
              )}
            </motion.div>
          ))}
        </div>
        <p
          style={{
            marginTop: 24,
            textAlign: 'center',
            fontSize: 12,
            color: 'var(--color-linear-text-3)',
          }}
        >
          Prices in USD. Cancel anytime; we pro-rate your last month.
        </p>
      </div>
    </section>
  );
}

function TierBody({ tier }: { tier: (typeof TIERS)[number] }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: 28,
      }}
    >
      <h3 className="section-eyebrow" style={{ margin: 0 }}>
        {tier.name}
      </h3>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 4,
          marginTop: 18,
        }}
      >
        <span
          style={{
            fontSize: 40,
            fontWeight: 600,
            letterSpacing: '-0.022em',
            lineHeight: 1,
            color: 'var(--color-linear-text)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          {tier.highlight ? <GradientText>{tier.price}</GradientText> : tier.price}
        </span>
        <span style={{ fontSize: 14, color: 'var(--color-linear-text-3)' }}>
          {tier.priceSuffix}
        </span>
      </div>
      <p
        style={{
          marginTop: 14,
          fontSize: 14,
          lineHeight: 1.55,
          color: 'var(--color-linear-text-2)',
        }}
      >
        {tier.blurb}
      </p>
      <ul
        style={{
          listStyle: 'none',
          margin: '20px 0 0',
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        {tier.features.map((f) => (
          <li
            key={f}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              fontSize: 13.5,
              color: 'var(--color-linear-text-2)',
            }}
          >
            <span
              style={{
                marginTop: 3,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                flex: '0 0 14px',
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: 'var(--color-linear-sage-tint)',
                color: 'var(--color-linear-sage)',
              }}
            >
              <Check style={{ width: 9, height: 9 }} />
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div
        style={{
          marginTop: 28,
          paddingTop: 20,
          borderTop: '1px solid var(--color-linear-hairline)',
        }}
      >
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
