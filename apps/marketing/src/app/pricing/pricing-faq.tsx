'use client';

import * as Accordion from '@radix-ui/react-accordion';
import { ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';

/**
 * Pricing FAQ — Linear V1 (Faithful).
 *
 * Surface-1 hairline accordion on dark canvas, sage chevron rotates
 * 180° on open. Drop cream surface, hardcoded ink hex colors, and
 * Source Serif body styling.
 */
const FAQ = [
  {
    q: 'How does the 14-day free trial work?',
    a: 'Sign up, get 10 free signed notes, and use the full feature set — batch + live transcription, full output bundle, EHR export. No credit card required. You can upgrade to Pro anytime during or after the trial.',
  },
  {
    q: 'Is this HIPAA-compliant?',
    a: 'QuillMD is designed for HIPAA compliance: data is encrypted at rest and in transit, every patient-record action is logged to an immutable audit trail, and every AI subprocessor (Anthropic, OpenAI, Deepgram) will have a signed BAA in place before your covered-entity PHI flows through our pipeline. We track BAA status per-subprocessor in our internal compliance register, available to prospective covered-entity customers on request.',
  },
  {
    q: 'Which EHRs do you support?',
    a: 'Output is formatted for Epic, Athena, and Cerner macro fields — you copy the section you need into your EHR. We do not integrate directly with the EHR; this keeps things fast and means no vendor review for you to navigate.',
  },
  {
    q: 'How accurate is the transcription?',
    a: `Transcription uses Deepgram's medical model — accurate, but not flawless on live clinic audio — so the note-drafting stage is built to confirm-not-fabricate: it is instructed to document only what it can tie back to the transcript, marking gaps "[not documented]" and unclear audio "[unclear in recording]" rather than guessing, and a separate critique pass re-checks the draft for unsupported claims. Every note is a draft until you review and sign it. On PriMock57, a public benchmark of 57 mock consultations, our notes score a mean 8.7/10 for completeness and accuracy; we don't publish numbers from live clinic audio yet — those arrive with the pilot, and will replace this answer before any figure here outruns the data.`,
  },
  {
    q: 'Can I cancel anytime?',
    a: 'Yes. Cancel in-app with a single button. We pro-rate your last month and keep your data accessible for 30 days afterwards in case you change your mind.',
  },
  {
    q: 'Do you offer refunds?',
    a: "If it doesn't work for your workflow in the first 30 days of a paid month, email support and we'll refund it. We don't make you talk to anyone to ask.",
  },
  {
    q: 'Is the audio stored permanently?',
    a: 'No. Audio auto-deletes 90 days after the visit is signed; the signed clinical note is kept separately for 7 years (the 6-year HIPAA minimum plus a buffer year). Shortening the audio window never touches the note.',
  },
  {
    q: 'What about controlled substances?',
    a: 'We never generate a controlled-substance prescription unless the clinician explicitly named it in the transcript. The Rx drafter always flags them with a mandatory-review banner before signing.',
  },
];

export function PricingFaq() {
  return (
    <section
      style={{
        position: 'relative',
        borderTop: '1px solid var(--color-linear-hairline)',
        paddingTop: 96,
        paddingBottom: 96,
      }}
    >
      <div className="container" style={{ maxWidth: 720 }}>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="section-eyebrow">Frequently asked</div>
          <h2 className="section-title" style={{ marginTop: 12, textAlign: 'left' }}>
            The answers to things people{' '}
            <span style={{ color: 'var(--color-linear-sage-bright)' }}>
              usually email about.
            </span>
          </h2>
        </motion.div>

        <Accordion.Root
          type="single"
          collapsible
          style={{
            marginTop: 32,
            overflow: 'hidden',
            borderRadius: 12,
            border: '1px solid var(--color-linear-border)',
            background: 'var(--color-linear-surface-1)',
          }}
        >
          {FAQ.map((item, i) => (
            <Accordion.Item
              key={item.q}
              value={`item-${i}`}
              style={{
                borderBottom:
                  i === FAQ.length - 1
                    ? 'none'
                    : '1px solid var(--color-linear-hairline)',
              }}
            >
              <Accordion.Header>
                <Accordion.Trigger
                  className="group"
                  style={{
                    display: 'flex',
                    width: '100%',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '20px 22px',
                    textAlign: 'left',
                    fontSize: 14.5,
                    fontWeight: 500,
                    color: 'var(--color-linear-text)',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                    letterSpacing: '-0.005em',
                  }}
                >
                  <span>{item.q}</span>
                  <ChevronDown
                    style={{
                      width: 14,
                      height: 14,
                      color: 'var(--color-linear-text-3)',
                      transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                    className="group-data-[state=open]:rotate-180 group-data-[state=open]:text-[color:var(--color-linear-sage)]"
                  />
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Content
                style={{ overflow: 'hidden' }}
                className="data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down"
              >
                <div
                  style={{
                    padding: '0 22px 20px',
                    fontSize: 13.5,
                    lineHeight: 1.6,
                    color: 'var(--color-linear-text-2)',
                  }}
                >
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
