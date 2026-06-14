import { Newsreader } from 'next/font/google';
import './structures.css';

// Newsreader (serif incl. italic) + the structures stylesheet load ONLY on /structures,
// so the root landing, /motion and /heroes stay byte-identical. The serif variable is
// scoped to this wrapper (used by S5's single statement and a few headings).
const serif = Newsreader({
  weight: ['300', '400', '500'],
  style: ['normal', 'italic'],
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
});

export default function StructuresLayout({ children }: { children: React.ReactNode }) {
  return <div className={serif.variable}>{children}</div>;
}
