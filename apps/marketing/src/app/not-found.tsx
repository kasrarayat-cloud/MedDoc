'use client';

import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';
import { APP_SIGNUP_URL } from '@/lib/constants';

/**
 * 404 page — Linear V1 (Faithful).
 *
 * Centered eyebrow + Inter 600 heading + body copy + sage primary "Back
 * to home" + sage outline "Start free trial". No serif italic accent;
 * GradientText now resolves to sage-bright Inter.
 */
export default function NotFound() {
  return (
    <>
      <NavBar />
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <section
          className="relative flex items-center overflow-hidden"
          style={{ minHeight: '80vh', paddingTop: 96, paddingBottom: 64 }}
        >
          <motion.div
            aria-hidden
            initial={{ y: 0, opacity: 0 }}
            animate={{
              y: [0, -10, 0],
              opacity: [0.4, 0.7, 0.4],
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="absolute left-1/2 top-[30%] h-[360px] w-[360px] -translate-x-1/2"
            style={{
              background:
                'radial-gradient(circle, rgba(122,166,140,0.28) 0%, rgba(122,166,140,0.08) 45%, transparent 70%)',
              filter: 'blur(24px)',
              pointerEvents: 'none',
            }}
          />
          <div className="container" style={{ textAlign: 'center', position: 'relative' }}>
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="section-eyebrow">404</div>
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="hero-title"
              style={{ marginTop: 16 }}
            >
              This page <GradientText>slipped through</GradientText>
              <br />
              our AI.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.25 }}
              className="hero-sub"
              style={{ marginTop: 24 }}
            >
              Nothing lives at this URL. Very rare for our models — we&apos;ll
              flag it for review.
            </motion.p>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.35 }}
              style={{
                marginTop: 32,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
              }}
              className="sm:flex-row"
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
