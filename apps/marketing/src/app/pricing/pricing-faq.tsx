'use client';

import * as Accordion from '@radix-ui/react-accordion';
import { ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';

const FAQ = [
  {
    q: 'How does the 14-day free trial work?',
    a: 'Sign up, get 10 free signed notes, and use the full feature set — batch + live transcription, full output bundle, EHR export. No credit card required. You can upgrade to Pro anytime during or after the trial.',
  },
  {
    q: 'Is this HIPAA-compliant?',
    a: 'Yes. Data is encrypted at rest and in transit. Every AI processor in the pipeline (Anthropic, OpenAI, Deepgram) has a signed BAA before production traffic flows. Every action on every patient record is logged to an immutable audit trail.',
  },
  {
    q: 'Which EHRs do you support?',
    a: 'Output is formatted for Epic, Athena, and Cerner macro fields — you copy the section you need into your EHR. We do not integrate directly with the EHR; this keeps things fast and means no vendor review for you to navigate.',
  },
  {
    q: 'How accurate is the transcription?',
    a: '94–96% accuracy on medical audio, measured against a held-out set of 200+ real-clinic recordings. Hallucination rate on SOAP generation is under 2%, verified via an evidence-quote detector that checks every finding against the transcript verbatim.',
  },
  {
    q: 'Can I cancel anytime?',
    a: 'Yes. Cancel in-app with a single button. We pro-rate your last month and keep your data accessible for 30 days afterwards in case you change your mind.',
  },
  {
    q: 'Do you offer refunds?',
    a: 'If it doesn\'t work for your workflow in the first 30 days of a paid month, email support and we\'ll refund it. We don\'t make you talk to anyone to ask.',
  },
  {
    q: 'Is the audio stored permanently?',
    a: 'No. Audio auto-deletes 90 days after the visit ends (clinic-configurable). Signed clinical notes retain per HIPAA (6-year minimum + a buffer year by default). You can tighten either window from the retention settings.',
  },
  {
    q: 'What about controlled substances?',
    a: 'We never generate a controlled-substance prescription unless the clinician explicitly named it in the transcript. The Rx drafter always flags them with a mandatory-review banner before signing.',
  },
];

export function PricingFaq() {
  return (
    <section className="relative border-t border-border-subtle bg-bg-surface-1/30 py-24">
      <div className="mx-auto max-w-3xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        >
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Frequently asked
          </p>
          <h2 className="mt-3 type-h2 text-text-primary">
            The answers to things people usually email about.
          </h2>
        </motion.div>

        <Accordion.Root
          type="single"
          collapsible
          className="mt-10 divide-y divide-border-subtle overflow-hidden rounded-2xl border border-border-default bg-bg-surface-2/60 backdrop-blur"
        >
          {FAQ.map((item, i) => (
            <Accordion.Item key={item.q} value={`item-${i}`}>
              <Accordion.Header>
                <Accordion.Trigger className="group flex w-full items-center justify-between px-6 py-5 text-left text-[15px] font-medium text-text-primary transition-colors hover:bg-bg-surface-3/40 data-[state=open]:bg-bg-surface-3/30">
                  <span>{item.q}</span>
                  <ChevronDown className="h-4 w-4 text-text-tertiary transition-transform duration-300 group-data-[state=open]:rotate-180" />
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Content className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
                <div className="px-6 pb-5 text-[14px] leading-relaxed text-text-tertiary">
                  {item.a}
                </div>
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </div>
    </section>
  );
}
