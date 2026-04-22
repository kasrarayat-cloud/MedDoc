'use client';

import { useReveal } from '@/hooks/useReveal';

/**
 * Invisible client-only component that wires up the global IntersectionObserver
 * for `.reveal` scroll triggers. Lives alongside the server-rendered sections
 * so page.tsx can stay a server component.
 */
export function RevealMount() {
  useReveal();
  return null;
}
