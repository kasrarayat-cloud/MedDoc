import type { Metadata } from 'next';
import { HeroLab } from '../../components/heroes/HeroLab';

export const metadata: Metadata = {
  title: 'QuillMD — Hero Concepts',
  description: 'Four reference-locked hero concepts for the QuillMD landing. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function HeroesPage() {
  return <HeroLab />;
}
