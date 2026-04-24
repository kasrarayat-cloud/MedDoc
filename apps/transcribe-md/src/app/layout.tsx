import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import {
  Source_Serif_4,
  Inter_Tight,
  JetBrains_Mono,
} from 'next/font/google';

import { auth } from '@/lib/nextauth';
import { CommandPalette } from '@/components/command-palette';
import { GlobalShortcuts } from '@/components/global-shortcuts';
import { Toaster } from '@/components/toaster';
import './globals.css';

// App-redesign-v1 font trio (HANDOFF §1.2). Variables match the bare-name
// tokens the ported .qm-* CSS references (var(--serif), var(--sans),
// var(--mono)). Fallback stacks mirror the handoff values so the page
// renders reasonably before the webfont finishes loading.
const serif = Source_Serif_4({
  subsets: ['latin'],
  variable: '--serif',
  display: 'swap',
  fallback: ['Charter', 'Iowan Old Style', 'Georgia', 'serif'],
});
const sans = Inter_Tight({
  subsets: ['latin'],
  variable: '--sans',
  display: 'swap',
  fallback: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
});
const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
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
  themeColor: '#07060C',
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
      className={`${GeistSans.variable} ${GeistMono.variable} ${serif.variable} ${sans.variable} ${mono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        {children}
        <CommandPalette authed={authed} />
        <GlobalShortcuts authed={authed} />
        <Toaster />
      </body>
    </html>
  );
}
