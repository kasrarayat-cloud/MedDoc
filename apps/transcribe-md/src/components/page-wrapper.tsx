'use client';

import { motion } from 'framer-motion';

/**
 * Subtle page-enter animation. Wraps a page's content so navigating to
 * it fades in from 12px below. Because Next's App Router unmounts the
 * previous page before mounting the next, a plain one-shot mount
 * animation is enough — we don't need AnimatePresence here.
 *
 * The same curve + duration live in the design tokens so toast pops,
 * dropdown opens, and page loads all share a rhythm.
 */
export function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
      className="min-h-screen"
    >
      {children}
    </motion.div>
  );
}
