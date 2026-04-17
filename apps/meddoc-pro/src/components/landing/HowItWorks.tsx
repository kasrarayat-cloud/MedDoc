'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { MousePointerClick, ClipboardEdit, Download } from 'lucide-react';

const steps = [
  {
    number: '01',
    icon: MousePointerClick,
    title: 'Select Procedure',
    description:
      'Choose from LESI, CESI, PRP, LFB and more. Over 26 procedure templates with bilateral, left, and right variations.',
    color: 'blue',
    iconBg: 'bg-blue-100 dark:bg-blue-950/50',
    iconColor: 'text-blue-600 dark:text-blue-400',
    numberColor: 'text-blue-600/20 dark:text-blue-400/20',
    dotColor: 'bg-blue-500',
  },
  {
    number: '02',
    icon: ClipboardEdit,
    title: 'Enter Patient Details',
    description:
      'Fill in the patient name, DOB, date of service, and procedure-specific details. Smart forms adapt to each procedure type.',
    color: 'teal',
    iconBg: 'bg-teal-100 dark:bg-teal-950/50',
    iconColor: 'text-teal-600 dark:text-teal-400',
    numberColor: 'text-teal-600/20 dark:text-teal-400/20',
    dotColor: 'bg-teal-500',
  },
  {
    number: '03',
    icon: Download,
    title: 'Download Document',
    description:
      'Get a perfectly formatted Word document instantly. Professional procedure notes ready for your records.',
    color: 'purple',
    iconBg: 'bg-purple-100 dark:bg-purple-950/50',
    iconColor: 'text-purple-600 dark:text-purple-400',
    numberColor: 'text-purple-600/20 dark:text-purple-400/20',
    dotColor: 'bg-purple-500',
  },
];

export default function HowItWorks() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section
      id="how-it-works"
      className="relative py-24 sm:py-32 bg-slate-50 dark:bg-slate-900/50"
    >
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-gradient-to-r from-blue-50 via-teal-50 to-purple-50 rounded-full blur-3xl opacity-60 dark:from-blue-950/20 dark:via-teal-950/20 dark:to-purple-950/20" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8" ref={ref}>
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 lg:mb-20"
        >
          <span className="inline-block rounded-full bg-teal-100 px-4 py-1.5 text-sm font-medium text-teal-700 dark:bg-teal-950/50 dark:text-teal-300 mb-4">
            How It Works
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white">
            Three Simple{' '}
            <span className="gradient-text">Steps</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            From procedure selection to final document -- your workflow has never been
            this streamlined.
          </p>
        </motion.div>

        {/* Steps */}
        <div className="relative grid md:grid-cols-3 gap-8 lg:gap-12">
          {/* Connecting Line (desktop) */}
          <div className="hidden md:block absolute top-24 left-[16.67%] right-[16.67%] h-[2px]">
            <motion.div
              className="h-full bg-gradient-to-r from-blue-300 via-teal-300 to-purple-300 dark:from-blue-700 dark:via-teal-700 dark:to-purple-700"
              initial={{ scaleX: 0 }}
              animate={isInView ? { scaleX: 1 } : {}}
              transition={{ duration: 1.2, delay: 0.5 }}
              style={{ transformOrigin: 'left' }}
            />
          </div>

          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.number}
                initial={{ opacity: 0, y: 40 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.6, delay: 0.3 + i * 0.25 }}
                className="relative text-center"
              >
                {/* Step card */}
                <div className="relative bg-white dark:bg-slate-800/50 rounded-2xl p-8 shadow-sm border border-slate-200/60 dark:border-slate-700/40 transition-all duration-300 hover:shadow-lg hover:-translate-y-1">
                  {/* Large faded number */}
                  <span
                    className={`absolute top-4 right-6 text-6xl font-black ${step.numberColor} select-none`}
                  >
                    {step.number}
                  </span>

                  {/* Icon with dot indicator */}
                  <div className="relative inline-flex mb-6">
                    <div
                      className={`h-16 w-16 rounded-2xl ${step.iconBg} flex items-center justify-center`}
                    >
                      <Icon className={`h-8 w-8 ${step.iconColor}`} />
                    </div>
                    {/* Active dot */}
                    <span
                      className={`absolute -top-1 -right-1 h-4 w-4 rounded-full ${step.dotColor} border-2 border-white dark:border-slate-800`}
                    />
                  </div>

                  {/* Title */}
                  <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-3">
                    {step.title}
                  </h3>

                  {/* Description */}
                  <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                    {step.description}
                  </p>
                </div>

                {/* Mobile connecting arrow */}
                {i < steps.length - 1 && (
                  <div className="md:hidden flex justify-center my-4">
                    <motion.svg
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      fill="none"
                      className="text-slate-300 dark:text-slate-600"
                      initial={{ opacity: 0 }}
                      animate={isInView ? { opacity: 1 } : {}}
                      transition={{ delay: 0.8 + i * 0.25 }}
                    >
                      <path
                        d="M12 5v14m0 0l-6-6m6 6l6-6"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </motion.svg>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
