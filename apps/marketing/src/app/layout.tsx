import type { Metadata, Viewport } from 'next';
import { DM_Sans, JetBrains_Mono, Source_Serif_4 } from 'next/font/google';
import './globals.css';
import './landing.css';

// DM Sans (chrome / labels / nav / metadata) — quiet humanist-geometric face
// per docs/design-directions-v3/clinician/README.md §Typography. Replaces
// Inter Tight, which read too sharp/architectural for the warm Clinician
// surfaces.
const sans = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
  display: 'swap',
});

// Source Serif 4 (body / patient names / hero headlines) — humanist serif
// optimized for screen. Holds at 14px and at 64px without losing warmth.
const serif = Source_Serif_4({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  style: ['normal', 'italic'],
  variable: '--font-serif',
  display: 'swap',
});

// JetBrains Mono — used sparingly for codes, IDs, MRN numbers.
const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'QuillMD — Stop writing notes. Start practicing medicine.',
    template: '%s · QuillMD',
  },
  description:
    'AI medical scribe for US doctors. Real-time SOAP notes, ICD-10/CPT codes, Rx drafts — $49/month flat.',
  openGraph: {
    title: 'QuillMD',
    description: 'Stop writing notes. Start practicing medicine.',
    type: 'website',
  },
};

// Theme color is now warm cream — matches the Clinician canvas. Color scheme
// is light because Clinician is light-mode-first (per CL-1 in the Phase 2
// plan). Dark-mode users are second-class on this surface by design.
export const viewport: Viewport = {
  themeColor: '#FAF7F2',
  colorScheme: 'light',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${serif.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      {/* qm-cl-app makes the bare-name Clinician CSS vars (--cream, --ink,
          --sage, --serif, etc.) resolve everywhere on the site so any
          hand-written .qm-cl-* utility (used by the home/* hero, recording
          card, etc.) reads correctly. data-grain layers the warm radial
          wash from the landing mockup. */}
      <body className="qm-cl-app min-h-screen antialiased" data-grain>
        {children}
      </body>
    </html>
  );
}
