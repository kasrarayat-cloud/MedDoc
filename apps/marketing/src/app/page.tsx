import type { Metadata } from 'next';
import { Manrope, IBM_Plex_Mono } from 'next/font/google';
import { FinalLanding } from '@/components/landing-final/FinalLanding';
import './final-landing.css';

// ============================================================================
// Landing page — the approved split-screen redesign, promoted from
// staging.quillmd.com/final (PR #325 review build) on 2026-07-03. Replaces
// the Phase 7 v6 "Apple Product Page" landing.
//
// components/home/* was DELETED 2026-07-29. It had been kept "for reference"
// and had gone stale into a liability: sixteen unreferenced components still
// asserting "BAA on file", "HIPAA-compliant end to end", "PHI never leaves our
// US-hosted environment" and "Compliant by default" — claims that are false
// today and that the next person building a page could have imported in good
// faith. The deploy-level rollback for this landing is the
// :pre-landing-20260703 image tag, which is a better reference than dead code.
//
// The design carries its own type pair (Manrope body + IBM Plex Mono data),
// scoped to .fx-root via next/font variables so the root layout's
// Inter/JetBrains pair (used by every subpage) is untouched.
// ============================================================================

const body = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  weight: ['400', '500', '600'],
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'QuillMD — The note writes itself',
  description:
    'Evidence-anchored clinical notes from the visit conversation, machine-verified, with a review lane for anything it can’t ground. You sign every note. $49 flat, HIPAA-ready, US-hosted.',
};

export default function HomePage() {
  return (
    <div className={`${body.variable} ${mono.variable}`}>
      <FinalLanding />
    </div>
  );
}
