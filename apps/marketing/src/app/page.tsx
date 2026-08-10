import type { Metadata } from 'next';
import localFont from 'next/font/local';
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

// ⚠️ SELF-HOSTED — see ./fonts/README.md. `next/font/google` fetches from
// Google DURING the build and fails as a `Module not found` on an internal
// turbopack path, which reads as a code defect rather than a network one.
//
// Manrope is a VARIABLE font (one file, whole range). IBM Plex Mono is NOT —
// its 400/500/600 are three distinct files, so it is declared as three faces.
// Getting that backwards ships a page whose bold monospace silently falls back.
const body = localFont({
  src: './fonts/manrope-latin.woff2',
  weight: '200 800',
  style: 'normal',
  variable: '--font-body',
  display: 'swap',
});

const mono = localFont({
  src: [
    { path: './fonts/ibm-plex-mono-latin-400.woff2', weight: '400', style: 'normal' },
    { path: './fonts/ibm-plex-mono-latin-500.woff2', weight: '500', style: 'normal' },
    { path: './fonts/ibm-plex-mono-latin-600.woff2', weight: '600', style: 'normal' },
  ],
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
