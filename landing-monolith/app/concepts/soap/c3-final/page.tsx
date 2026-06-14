import type { Metadata } from 'next';
import { C3Final } from '../../../../components/concepts/soap/C3Final';
import './c3-final.css';

export const metadata: Metadata = {
  title: 'QuillMD — C3 Drawer (complete)',
  description: 'The complete, polished C3 "Drawer" SOAP-review concept across every state. Static mockup, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function C3FinalPage() {
  return <C3Final />;
}
