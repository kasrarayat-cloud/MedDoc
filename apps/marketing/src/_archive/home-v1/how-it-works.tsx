'use client';

import { motion } from 'framer-motion';
import { Mic, Radio, PenLine } from 'lucide-react';
import { GlowCard } from '@/components/glow-card';
import { TiltCard } from '@/components/tilt-card';

const STEPS = [
  {
    icon: Mic,
    title: 'Upload audio',
    body:
      'Record with your phone, your dictaphone, anything. Drag the .mp3 or .m4a into the browser and we turn it into a signed SOAP note in minutes.',
  },
  {
    icon: Radio,
    title: 'Dictate live',
    body:
      'Start a recording in-visit or between patients. Transcription streams in real-time with the patient and clinician turns already split.',
  },
  {
    icon: PenLine,
    title: 'Text to SOAP',
    body:
      'Already have bullet points from a quick visit? Paste them in. We structure them, fill the Assessment + Plan, and flag anything unclear.',
  },
];

export function HowItWorks() {
  return (
    <section
      id="how"
      className="relative overflow-hidden border-t border-border-subtle bg-bg-surface-1/40 py-24 lg:py-32"
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
            How it works
          </p>
          <h2 className="mt-3 type-h2 text-text-primary">
            Three inputs. One workflow.
          </h2>
          <p className="mt-4 type-body text-text-tertiary">
            However you capture the visit, the output is the same: a signed
            note you can paste into any EHR.
          </p>
        </motion.div>

        <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{
                duration: 0.5,
                ease: [0.4, 0, 0.2, 1],
                delay: i * 0.08,
              }}
            >
              <TiltCard>
                <GlowCard className="flex h-full flex-col gap-4 p-6 lg:p-8">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-bg-surface-3/80">
                    <step.icon className="h-4 w-4 text-violet-400" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-baseline gap-3">
                      <span className="type-small font-mono text-text-muted">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <h3 className="text-[18px] font-semibold tracking-tight text-text-primary">
                        {step.title}
                      </h3>
                    </div>
                    <p className="text-[14px] leading-relaxed text-text-tertiary">
                      {step.body}
                    </p>
                  </div>
                </GlowCard>
              </TiltCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
