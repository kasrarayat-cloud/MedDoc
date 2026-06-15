import { Inter, JetBrains_Mono } from 'next/font/google';
import '../soap/soap.css';
import './soap-v2.css';

// SOAP v2 concepts mirror the real app's type (Inter + JetBrains Mono), loaded ONLY on
// /concepts/soap-v2. We import the v1 lab's soap.css for the shared base (tokens, the note,
// buttons, cards, Rx/lane, switcher) and layer soap-v2.css on top for the two new full-width
// shells — so the v1 lab at /concepts/soap stays byte-identical.
const sans = Inter({ subsets: ['latin'], variable: '--soap-sans', display: 'swap' });
const mono = JetBrains_Mono({ weight: ['400', '500'], subsets: ['latin'], variable: '--soap-mono', display: 'swap' });

export default function ConceptsSoapV2Layout({ children }: { children: React.ReactNode }) {
  return <div className={`${sans.variable} ${mono.variable}`}>{children}</div>;
}
