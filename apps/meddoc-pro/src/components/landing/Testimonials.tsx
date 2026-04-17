'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Star, Quote } from 'lucide-react';

const testimonials = [
  {
    name: 'Dr. Sarah M.',
    specialty: 'Pain Management',
    quote:
      'MedDoc Pro has cut my documentation time by 80%. I can focus on patients instead of paperwork.',
    rating: 5,
    initials: 'SM',
    color: 'from-blue-500 to-blue-600',
  },
  {
    name: 'Dr. James L.',
    specialty: 'Orthopedic Surgery',
    quote:
      'The AI assistant is incredible. It understands exactly what procedure I\'m describing.',
    rating: 5,
    initials: 'JL',
    color: 'from-teal-500 to-teal-600',
  },
  {
    name: 'Dr. Emily R.',
    specialty: 'Sports Medicine',
    quote:
      'Finally, a documentation tool built by doctors, for doctors. Highly recommend.',
    rating: 5,
    initials: 'ER',
    color: 'from-purple-500 to-purple-600',
  },
];

function StarRating({ count }: { count: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: count }).map((_, i) => (
        <Star
          key={i}
          className="h-4 w-4 fill-amber-400 text-amber-400"
        />
      ))}
    </div>
  );
}

export default function Testimonials() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="relative py-24 sm:py-32 bg-slate-50 dark:bg-slate-900/50 overflow-hidden">
      {/* Decorative background */}
      <div className="absolute top-0 left-1/4 w-64 h-64 bg-blue-100/40 rounded-full blur-3xl dark:bg-blue-950/20" />
      <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-teal-100/40 rounded-full blur-3xl dark:bg-teal-950/20" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8" ref={ref}>
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block rounded-full bg-amber-100 px-4 py-1.5 text-sm font-medium text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 mb-4">
            Testimonials
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white">
            Trusted by{' '}
            <span className="gradient-text">Healthcare Professionals</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            See what doctors are saying about how MedDoc Pro transforms their
            documentation workflow.
          </p>
        </motion.div>

        {/* Testimonial Cards */}
        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, i) => (
            <motion.div
              key={testimonial.name}
              initial={{ opacity: 0, y: 40 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              className="group"
            >
              <div className="relative h-full rounded-2xl bg-white dark:bg-slate-800/50 p-8 shadow-sm border border-slate-200/60 dark:border-slate-700/40 transition-all duration-300 hover:shadow-lg hover:-translate-y-1">
                {/* Quote icon */}
                <div className="absolute top-6 right-6 opacity-10">
                  <Quote className="h-10 w-10 text-blue-500" />
                </div>

                {/* Rating */}
                <StarRating count={testimonial.rating} />

                {/* Quote */}
                <p className="mt-5 text-base leading-relaxed text-slate-700 dark:text-slate-300">
                  &ldquo;{testimonial.quote}&rdquo;
                </p>

                {/* Author */}
                <div className="mt-6 flex items-center gap-3 pt-6 border-t border-slate-100 dark:border-slate-700/50">
                  {/* Avatar */}
                  <div
                    className={`h-11 w-11 rounded-full bg-gradient-to-br ${testimonial.color} flex items-center justify-center text-white text-sm font-semibold shadow-md`}
                  >
                    {testimonial.initials}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">
                      {testimonial.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {testimonial.specialty}
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Social proof bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.8 }}
          className="mt-16 flex flex-wrap items-center justify-center gap-8 sm:gap-16 text-center"
        >
          <div>
            <p className="text-3xl font-bold gradient-text">500+</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Active Doctors
            </p>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block" />
          <div>
            <p className="text-3xl font-bold gradient-text">50,000+</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Documents Generated
            </p>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block" />
          <div>
            <p className="text-3xl font-bold gradient-text">4.9/5</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Average Rating
            </p>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block" />
          <div>
            <p className="text-3xl font-bold gradient-text">80%</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Time Saved
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
