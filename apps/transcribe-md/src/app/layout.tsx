import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'TranscribeMD',
    template: '%s · TranscribeMD',
  },
  description:
    'AI medical transcription for solo doctors. Send audio, get a signed note.',
};

export const viewport: Viewport = {
  themeColor: '#08090D',
  colorScheme: 'dark',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
