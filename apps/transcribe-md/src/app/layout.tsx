import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';

import { auth } from '@/lib/nextauth';
import { CommandPalette } from '@/components/command-palette';
import { GlobalShortcuts } from '@/components/global-shortcuts';
import { Toaster } from '@/components/toaster';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'QuillMD',
    template: '%s · QuillMD',
  },
  description:
    'AI medical transcription for solo doctors. Send audio, get a signed note.',
};

export const viewport: Viewport = {
  themeColor: '#08090D',
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
      className={`${GeistSans.variable} ${GeistMono.variable} dark`}
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
