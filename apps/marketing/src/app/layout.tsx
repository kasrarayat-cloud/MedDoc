import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'QuillMD — AI medical transcription that takes 5 minutes',
    template: '%s · QuillMD',
  },
  description:
    'Send audio. Get a signed note. 5 minutes. The AI medical transcription service built for solo doctors who deserve better tools.',
  openGraph: {
    title: 'QuillMD',
    description: 'Send audio. Get a signed note. 5 minutes.',
    type: 'website',
  },
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
