'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, HelpCircle } from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Pricing from '@/components/landing/Pricing';
import Footer from '@/components/landing/Footer';

// ---------------------------------------------------------------------------
// FAQ data
// ---------------------------------------------------------------------------

const FAQ_ITEMS = [
  {
    question: "What's included in the free trial?",
    answer:
      'The 14-day free trial gives you full access to the Professional plan features, including unlimited document generation, all 26+ procedure templates, the AI-powered assistant, custom letterhead, and priority support. No credit card is required to start your trial.',
  },
  {
    question: 'Can I upgrade or downgrade anytime?',
    answer:
      'Absolutely. You can switch between plans at any time from your account settings. When upgrading, the new features are available immediately and billing is prorated. When downgrading, the change takes effect at the start of your next billing cycle, so you keep your current features until then.',
  },
  {
    question: 'Is my data HIPAA compliant?',
    answer:
      'Yes. MedDoc Pro is fully HIPAA compliant. All patient data is encrypted at rest and in transit using AES-256 encryption. We maintain a signed Business Associate Agreement (BAA), conduct regular security audits, and our infrastructure is hosted on SOC 2 Type II certified data centers. Your data is never shared with third parties.',
  },
  {
    question: 'Do you offer custom templates?',
    answer:
      'Yes. The Professional plan includes access to all 26+ built-in procedure templates. Enterprise customers can request fully customized templates tailored to their specific practice needs, including custom formatting, letterheads, and procedure-specific fields. Our team works directly with you to build templates that match your workflow.',
  },
  {
    question: 'What payment methods do you accept?',
    answer:
      'We accept all major credit and debit cards (Visa, Mastercard, American Express, Discover), as well as ACH bank transfers for annual plans. Enterprise customers can also pay via invoice with NET-30 terms. All payments are processed securely through Stripe.',
  },
];

// ---------------------------------------------------------------------------
// FAQ Accordion item
// ---------------------------------------------------------------------------

function FAQItem({
  question,
  answer,
  isOpen,
  onToggle,
  index,
}: {
  question: string;
  answer: string;
  isOpen: boolean;
  onToggle: () => void;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      className="border-b border-slate-200 dark:border-slate-700/50"
    >
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 py-5 text-left transition-colors hover:text-blue-600 dark:hover:text-blue-400"
        aria-expanded={isOpen}
      >
        <span className="text-base font-semibold text-slate-800 dark:text-white sm:text-lg">
          {question}
        </span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800"
        >
          <ChevronDown className="h-4 w-4 text-slate-500 dark:text-slate-400" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <p className="pb-5 text-sm leading-relaxed text-slate-600 dark:text-slate-400 sm:text-base">
              {answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function PricingPage() {
  const [openFAQ, setOpenFAQ] = useState<number | null>(null);

  const toggleFAQ = (index: number) => {
    setOpenFAQ((prev) => (prev === index ? null : index));
  };

  return (
    <main className="min-h-screen bg-white dark:bg-slate-950">
      <Navbar />

      {/* Hero area */}
      <section className="relative overflow-hidden pt-32 pb-16 sm:pt-40 sm:pb-20">
        {/* Background decorations */}
        <div className="absolute inset-0 gradient-mesh pointer-events-none" />
        <div className="absolute top-20 left-1/4 h-72 w-72 rounded-full bg-blue-400/10 blur-3xl" />
        <div className="absolute top-32 right-1/4 h-72 w-72 rounded-full bg-teal-400/10 blur-3xl" />

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
          <motion.span
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-block rounded-full bg-blue-100 px-4 py-1.5 text-sm font-medium text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 mb-4"
          >
            Plans & Pricing
          </motion.span>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-4xl font-bold text-slate-900 dark:text-white sm:text-5xl lg:text-6xl"
          >
            Choose Your{' '}
            <span className="gradient-text">Plan</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mx-auto mt-4 max-w-2xl text-lg text-slate-600 dark:text-slate-400 sm:text-xl"
          >
            Start free, scale as your practice grows. All plans include a 14-day
            trial with full access to professional features.
          </motion.p>
        </div>
      </section>

      {/* Pricing cards (reused landing component) */}
      <Pricing />

      {/* FAQ Section */}
      <section className="relative py-24 sm:py-32 bg-slate-50 dark:bg-slate-900/50">
        {/* Decorations */}
        <div className="absolute top-0 left-0 w-96 h-96 bg-purple-50/50 rounded-full blur-3xl dark:bg-purple-950/10" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-blue-50/50 rounded-full blur-3xl dark:bg-blue-950/10" />

        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          {/* Section header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.6 }}
            className="mb-12 text-center"
          >
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-950/50">
              <HelpCircle className="h-6 w-6 text-purple-600 dark:text-purple-400" />
            </div>
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white sm:text-4xl">
              Frequently Asked{' '}
              <span className="gradient-text">Questions</span>
            </h2>
            <p className="mt-3 text-slate-600 dark:text-slate-400">
              Everything you need to know about MedDoc Pro.
            </p>
          </motion.div>

          {/* Accordion */}
          <div className="rounded-2xl border border-slate-200 bg-white px-6 shadow-sm dark:border-slate-700/50 dark:bg-slate-800/50 sm:px-8">
            {FAQ_ITEMS.map((item, i) => (
              <FAQItem
                key={i}
                question={item.question}
                answer={item.answer}
                isOpen={openFAQ === i}
                onToggle={() => toggleFAQ(i)}
                index={i}
              />
            ))}
          </div>

          {/* Bottom CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="mt-12 text-center"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Still have questions?{' '}
              <a
                href="#"
                className="font-medium text-blue-600 transition-colors hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Contact our support team
              </a>
            </p>
          </motion.div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
