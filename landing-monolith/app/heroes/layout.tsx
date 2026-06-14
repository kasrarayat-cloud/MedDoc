import { Newsreader } from 'next/font/google';
import './heroes.css';

// Newsreader (transitional serif incl. italic) + the hero stylesheet are loaded ONLY
// for the /heroes segment. This keeps the root landing (/) and the motion lab (/motion)
// byte-identical — no extra font, no extra CSS on those routes. The serif variable is
// scoped to this wrapper, which is where the reference-locked heroes consume it.
const serif = Newsreader({
  weight: ['300', '400', '500'],
  style: ['normal', 'italic'],
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
});

export default function HeroesLayout({ children }: { children: React.ReactNode }) {
  return <div className={serif.variable}>{children}</div>;
}
