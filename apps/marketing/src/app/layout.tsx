import type { Metadata, Viewport } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import './landing.css';

// Phase 5 Linear V1 type pair. DM Sans + Source Serif 4 have been
// retired — Linear V1 is Inter for everything (chrome + body) plus
// JetBrains Mono for IDs / timestamps / keyboard hints. The variable
// names (`--font-sans` / `--font-mono`) line up with the @theme block in
// globals.css and the .qm-lin-* utility classes.
const sans = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
});

const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'QuillMD — The note writes itself',
    template: '%s · QuillMD',
  },
  description:
    'Evidence-anchored clinical notes from the visit conversation, machine-verified, with a review lane for anything it can’t ground. You sign every note. $49 flat.',
  openGraph: {
    title: 'QuillMD',
    description: 'The note writes itself — you sign it.',
    type: 'website',
  },
};

// Phase 5 Linear V1: pure dark canvas (#08090a) replaces the cream
// surface. Color scheme is dark, full-stop — there is no light mode.
export const viewport: Viewport = {
  themeColor: '#08090a',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        {/* Round 3 PR-I — A09-P1 WCAG 2.4.1 (Bypass Blocks). Skip-to
            content is the first focusable element on every marketing
            page; visible only when focused (sr-only → focus:not-sr-only).
            Marketing pages render `<main>` via individual page wrappers
            (most just call NavBar + section + Footer); we add the
            scroll-target landmark here so the link always has somewhere
            to land. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-[var(--color-linear-sage)] focus:px-3 focus:py-2 focus:font-medium focus:text-[var(--color-linear-bg)] focus:shadow-lg"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
