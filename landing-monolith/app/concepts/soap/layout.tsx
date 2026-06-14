import { Inter, JetBrains_Mono } from 'next/font/google';
import './soap.css';

// The SOAP concepts mirror the REAL app's type (Inter + JetBrains Mono), loaded ONLY on
// /concepts/soap so the landing routes stay byte-identical. Scoped to --soap-sans / --soap-mono
// to avoid colliding with the landing's global fonts.
const sans = Inter({ subsets: ['latin'], variable: '--soap-sans', display: 'swap' });
const mono = JetBrains_Mono({ weight: ['400', '500'], subsets: ['latin'], variable: '--soap-mono', display: 'swap' });

export default function ConceptsSoapLayout({ children }: { children: React.ReactNode }) {
  return <div className={`${sans.variable} ${mono.variable}`}>{children}</div>;
}
