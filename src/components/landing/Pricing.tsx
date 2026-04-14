'use client';

import { useRef } from 'react';
import Link from 'next/link';
import { motion, useInView } from 'framer-motion';
import { Check, Sparkles } from 'lucide-react';

const plans = [
  {
    name: 'Starter',
    price: 'Free',
    period: '',
    description: 'Perfect for trying out MedDoc Pro',
    features: [
      '5 documents per month',
      'Basic procedure templates',
      'Email support',
      'Standard formatting',
    ],
    cta: 'Get Started Free',
    href: '/register',
    popular: false,
  },
  {
    name: 'Professional',
    price: '$49',
    period: '/mo',
    description: 'Best for individual practitioners',
    features: [
      'Unlimited documents',
      'AI-powered assistant',
      'All 26+ procedure templates',
      'Priority support',
      'Custom letterhead',
      'Export in multiple formats',
    ],
    cta: 'Start Free Trial',
    href: '/register',
    popular: true,
  },
  {
    name: 'Enterprise',
    price: '$149',
    period: '/mo',
    description: 'For clinics and practices',
    features: [
      'Everything in Professional',
      'Multi-doctor accounts',
      'Custom procedure templates',
      'Dedicated support',
      'API access',
      'Audit logs & compliance',
    ],
    cta: 'Contact Sales',
    href: '/register',
    popular: false,
  },
];

export default function Pricing() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="pricing" className="relative py-24 sm:py-32 bg-white dark:bg-slate-950">
      {/* Background decoration */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-blue-50/50 rounded-full blur-3xl dark:bg-blue-950/10" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-teal-50/50 rounded-full blur-3xl dark:bg-teal-950/10" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8" ref={ref}>
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block rounded-full bg-purple-100 px-4 py-1.5 text-sm font-medium text-purple-700 dark:bg-purple-950/50 dark:text-purple-300 mb-4">
            Pricing
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white">
            Simple, Transparent{' '}
            <span className="gradient-text">Pricing</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            Choose the plan that fits your practice. No hidden fees, cancel
            anytime.
          </p>
        </motion.div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 items-start">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 40 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              className={`relative ${plan.popular ? 'md:-mt-4 md:mb-4' : ''}`}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 z-10">
                  <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-blue-600 to-teal-500 px-4 py-1 text-xs font-semibold text-white shadow-lg shadow-blue-500/25">
                    <Sparkles className="h-3 w-3" />
                    MOST POPULAR
                  </span>
                </div>
              )}

              <div
                className={`relative rounded-2xl p-8 transition-all duration-300 hover:shadow-xl ${
                  plan.popular
                    ? 'bg-gradient-to-b from-blue-600 to-blue-700 text-white shadow-2xl shadow-blue-500/20 ring-1 ring-blue-500'
                    : 'bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 shadow-sm hover:-translate-y-1'
                }`}
              >
                {/* Plan name */}
                <h3
                  className={`text-lg font-semibold ${
                    plan.popular ? 'text-blue-100' : 'text-slate-900 dark:text-white'
                  }`}
                >
                  {plan.name}
                </h3>

                {/* Price */}
                <div className="mt-4 flex items-baseline gap-1">
                  <span
                    className={`text-5xl font-bold tracking-tight ${
                      plan.popular ? 'text-white' : 'text-slate-900 dark:text-white'
                    }`}
                  >
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span
                      className={`text-base ${
                        plan.popular ? 'text-blue-200' : 'text-slate-500 dark:text-slate-400'
                      }`}
                    >
                      {plan.period}
                    </span>
                  )}
                </div>

                {/* Description */}
                <p
                  className={`mt-2 text-sm ${
                    plan.popular ? 'text-blue-100' : 'text-slate-600 dark:text-slate-400'
                  }`}
                >
                  {plan.description}
                </p>

                {/* Divider */}
                <div
                  className={`mt-6 mb-6 border-t ${
                    plan.popular ? 'border-blue-500/30' : 'border-slate-200 dark:border-slate-700'
                  }`}
                />

                {/* Features */}
                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <Check
                        className={`h-5 w-5 shrink-0 mt-0.5 ${
                          plan.popular ? 'text-teal-300' : 'text-teal-500'
                        }`}
                      />
                      <span
                        className={`text-sm ${
                          plan.popular ? 'text-blue-50' : 'text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <Link
                  href={plan.href}
                  className={`block w-full rounded-xl py-3 px-6 text-center text-sm font-semibold transition-all duration-300 ${
                    plan.popular
                      ? 'bg-white text-blue-700 hover:bg-blue-50 shadow-lg'
                      : 'bg-gradient-to-r from-blue-600 to-teal-500 text-white hover:shadow-lg hover:shadow-blue-500/25 hover:scale-[1.02]'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Bottom note */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ delay: 0.8 }}
          className="text-center text-sm text-slate-500 dark:text-slate-400 mt-12"
        >
          All plans include a 14-day free trial. No credit card required.
        </motion.p>
      </div>
    </section>
  );
}
