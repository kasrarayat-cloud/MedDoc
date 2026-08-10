import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import localFont from 'next/font/local';

import { auth } from '@/lib/nextauth';
import { CommandPalette } from '@/components/command-palette';
import { GlobalShortcuts } from '@/components/global-shortcuts';
import { Toaster } from '@/components/toaster';
import './globals.css';
import './rounds-tokens.css';

// Phase 5 Linear V1 font pair. Source Serif 4 + Inter Tight have been
// retired — Linear V1 is Inter for chrome + body and JetBrains Mono for
// IDs, codes, timestamps, and keyboard hints. The variable names line up
// with `--font-sans` / `--font-mono` consumed by the @theme block in
// globals.css and the ported .qm-lin-* utility classes.
// ⚠️ SELF-HOSTED, NOT `next/font/google` — AND THAT IS THE POINT.
// That loader fetches font CSS from Google's servers DURING `next build`. When
// the fetch fails the build does not say "network": it emits CSS pointing at
// `@vercel/turbopack-next/internal/font/google/font`, which does not resolve,
// and dies with `Module not found` inside this file. Two main-side builds died
// that way on 2026-08-10 while the same tree built green minutes earlier.
// See AGENTS.md, "an external fault does not spend the cure budget".
//
// These are VARIABLE fonts: one file per style covering the whole weight range,
// declared with a weight RANGE rather than as discrete faces. Provenance,
// licence and the exact ranges: ./fonts/README.md.
const sans = localFont({
  src: './fonts/inter-latin.woff2',
  weight: '400 700',
  style: 'normal',
  variable: '--font-sans',
  display: 'swap',
  fallback: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
});
const mono = localFont({
  src: './fonts/jetbrains-mono-latin.woff2',
  weight: '400 500',
  style: 'normal',
  variable: '--font-mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
});

// ── Rounds type ───────────────────────────────────────────────────────────
// Loaded unconditionally rather than behind the flag: next/font resolves at
// BUILD time, so a conditional import is not a thing that exists. The cost of
// an unused face is a preload the browser skips; the cost of trying to be
// clever here is a font that silently fails to load on the skin that needs it.
//
// Source Serif 4 carries ALL clinical prose, including the default paper
// template — see docs/design-tokens.md. Clinical prose is read differently from
// interface text and the typeface is the cue.
const roundsDisplay = localFont({
  src: './fonts/bricolage-grotesque-latin.woff2',
  weight: '500 700',
  style: 'normal',
  variable: '--font-rounds-display',
  display: 'swap',
  fallback: ['system-ui', 'sans-serif'],
});
const roundsUi = localFont({
  src: './fonts/figtree-latin.woff2',
  weight: '400 600',
  style: 'normal',
  variable: '--font-rounds-ui',
  display: 'swap',
  fallback: ['system-ui', 'sans-serif'],
});
const roundsClinical = localFont({
  src: [
    {
      path: './fonts/source-serif-4-latin.woff2',
      weight: '400 600',
      style: 'normal',
    },
    {
      path: './fonts/source-serif-4-latin-italic.woff2',
      weight: '400 600',
      style: 'italic',
    },
  ],
  variable: '--font-rounds-clinical',
  display: 'swap',
  fallback: ['Georgia', 'Times New Roman', 'serif'],
});

export const metadata: Metadata = {
  title: {
    default: 'QuillMD',
    template: '%s · QuillMD',
  },
  description:
    'AI medical transcription for solo doctors. Send audio, get a signed note.',
  // app.quillmd.com is the authenticated surface. The marketing site
  // (quillmd.com) carries the public-facing content and should be
  // indexed; everything behind this layout sits behind session auth,
  // so block crawlers from following URLs they shouldn't fingerprint.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: '#08090a',
  colorScheme: 'dark',
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Resolve auth once in the root layout so we can show/hide the authed
  // commands + shortcuts without each page having to wire them. auth()
  // is a cookie read and a DB lookup via the session callback — cheap
  // enough for every navigation.
  const session = await auth();
  const authed = Boolean(session?.user?.id);

  return (
    <html
      lang="en"
      data-theme="dark"
      // data-skin scopes the whole Rounds token layer, and it is set on <html>
      // for two reasons: the stage gradient has to cascade from the root, and a
      // screenshot of any page then carries evidence of which skin produced it.
      data-skin="rounds"
      className={`${GeistSans.variable} ${GeistMono.variable} ${sans.variable} ${mono.variable} ${roundsDisplay.variable} ${roundsUi.variable} ${roundsClinical.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        {/* Round-2 audit P3-R2-003: WCAG 2.4.1 (Bypass Blocks).
         *  Skip-to-content link is the first focusable element — keyboard /
         *  screen-reader users can bypass the global nav on every page.
         *  Visible only when focused (sr-only → focus:not-sr-only). The
         *  href targets `#main`, which page-level layouts wrap their primary
         *  content with (e.g., dashboard, /visits/[id]). For pages that
         *  don't yet have <main id="main">, the link still passes WCAG
         *  technique G1 (skip link present); the target landing simply
         *  scrolls to the top of the body. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-linear-sage focus:px-3 focus:py-2 focus:font-medium focus:text-linear-bg focus:shadow-lg"
        >
          Skip to main content
        </a>
        {children}
        <CommandPalette authed={authed} />
        <GlobalShortcuts authed={authed} />
        <Toaster />
      </body>
    </html>
  );
}
