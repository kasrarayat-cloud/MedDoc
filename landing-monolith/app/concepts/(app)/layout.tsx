import type { ReactNode } from 'react';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './app.css';

// Scoped fonts for the app-concept screens (dashboard + record). Same Inter + JetBrains Mono as
// the C3 SOAP screen, so the family reads as one app. Route group (app) → does not affect the URL
// (/concepts/dashboard, /concepts/record) and does not touch the sibling /concepts/soap routes.
const sans = Inter({ subsets: ['latin'], variable: '--ax-sans', display: 'swap' });
const mono = JetBrains_Mono({ weight: ['400', '500'], subsets: ['latin'], variable: '--ax-mono', display: 'swap' });

export default function AppConceptsLayout({ children }: { children: ReactNode }) {
  return <div className={`${sans.variable} ${mono.variable}`}>{children}</div>;
}
