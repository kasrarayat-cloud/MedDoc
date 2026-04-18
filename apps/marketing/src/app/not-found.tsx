'use client';

import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

export default function NotFound() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative flex min-h-[80vh] items-center overflow-hidden pt-32 pb-24">
          {/* Floating violet orb — the "missing" thing. Drifts gently. */}
          <motion.div
            aria-hidden
            initial={{ y: 0, opacity: 0 }}
            animate={{
              y: [0, -18, 0],
              opacity: [0.65, 0.9, 0.65],
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
            className="absolute left-1/2 top-[30%] h-[360px] w-[360px] -translate-x-1/2"
            style={{
              background:
                'radial-gradient(circle, rgba(139,92,246,0.35) 0%, rgba(124,58,237,0.1) 45%, transparent 70%)',
              filter: 'blur(24px)',
            }}
          />
          <div className="relative mx-auto max-w-3xl px-6 text-center lg:px-8">
            <motion.p
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
              className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted"
            >
              404
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.4, 0, 0.2, 1] }}
              className="mt-4 type-display"
            >
              This page <GradientText>slipped through</GradientText>
              <br />
              our AI.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.25 }}
              className="mx-auto mt-8 max-w-md text-[16px] text-text-tertiary"
            >
              Nothing lives at this URL. Very rare for our models — we&apos;ll
              flag it for review.
            </motion.p>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.35 }}
              className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
            >
              <SpecularButton href="/" variant="primary" size="lg">
                <ArrowLeft className="h-4 w-4" />
                Back to home
              </SpecularButton>
              <SpecularButton href={APP_SIGNUP_URL} variant="secondary" size="lg" sweep={false}>
                Start free trial
              </SpecularButton>
            </motion.div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
