import type { Metadata } from 'next';
import { MotionLab } from '../../components/motion/MotionLab';

export const metadata: Metadata = {
  title: 'QuillMD — Motion Lab',
  description: 'Five motion concepts for the QuillMD hero. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function MotionPage() {
  return <MotionLab />;
}
