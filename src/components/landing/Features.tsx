'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { FileText, Bot, Layout, Shield } from 'lucide-react';

const features = [
  {
    icon: FileText,
    title: 'Smart Document Generation',
    description:
      'Select your procedure, enter patient details, and download a perfectly formatted Word document in seconds.',
    color: 'blue',
    gradient: 'from-blue-500 to-blue-600',
    bgLight: 'bg-blue-50',
    bgDark: 'dark:bg-blue-950/30',
    textColor: 'text-blue-600 dark:text-blue-400',
  },
  {
    icon: Bot,
    title: 'AI-Powered Assistant',
    description:
      'Describe your procedure in natural language. Our AI understands medical terminology and generates accurate notes.',
    color: 'teal',
    gradient: 'from-teal-500 to-teal-600',
    bgLight: 'bg-teal-50',
    bgDark: 'dark:bg-teal-950/30',
    textColor: 'text-teal-600 dark:text-teal-400',
  },
  {
    icon: Layout,
    title: '26+ Procedure Templates',
    description:
      'LESI, CESI, PRP, LFB and more. All procedure types with bilateral, left, and right variations.',
    color: 'purple',
    gradient: 'from-purple-500 to-purple-600',
    bgLight: 'bg-purple-50',
    bgDark: 'dark:bg-purple-950/30',
    textColor: 'text-purple-600 dark:text-purple-400',
  },
  {
    icon: Shield,
    title: 'Secure & Compliant',
    description:
      'HIPAA-aware design with encrypted data storage. Your patient data stays protected.',
    color: 'emerald',
    gradient: 'from-emerald-500 to-emerald-600',
    bgLight: 'bg-emerald-50',
    bgDark: 'dark:bg-emerald-950/30',
    textColor: 'text-emerald-600 dark:text-emerald-400',
  },
];

export default function Features() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="features" className="relative py-24 sm:py-32 bg-white dark:bg-slate-950">
      {/* Subtle background accents */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-blue-50/50 rounded-full blur-3xl dark:bg-blue-950/20" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8" ref={ref}>
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block rounded-full bg-blue-100 px-4 py-1.5 text-sm font-medium text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 mb-4">
            Features
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white">
            Everything You{' '}
            <span className="gradient-text">Need</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            Powerful tools designed specifically for medical professionals to
            streamline documentation workflows.
          </p>
        </motion.div>

        {/* Feature Cards Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 40 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5, delay: i * 0.15 }}
              >
                <div className="card-gradient-border group h-full">
                  <div className="relative p-6 h-full rounded-2xl bg-white dark:bg-slate-900 transition-all duration-300 group-hover:shadow-xl group-hover:-translate-y-1">
                    {/* Icon */}
                    <div
                      className={`mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl ${feature.bgLight} ${feature.bgDark} transition-transform duration-300 group-hover:scale-110`}
                    >
                      <Icon className={`h-6 w-6 ${feature.textColor}`} />
                    </div>

                    {/* Title */}
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
                      {feature.title}
                    </h3>

                    {/* Description */}
                    <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                      {feature.description}
                    </p>

                    {/* Decorative gradient dot */}
                    <div
                      className={`absolute top-6 right-6 h-2 w-2 rounded-full bg-gradient-to-r ${feature.gradient} opacity-0 transition-opacity duration-300 group-hover:opacity-100`}
                    />
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
