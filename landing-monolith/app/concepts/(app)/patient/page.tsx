import type { Metadata } from 'next';
import { PatientScreen } from '../../../../components/concepts/app/PatientScreen';

export const metadata: Metadata = {
  title: 'QuillMD — Patient (concept)',
  description: 'Calm patient detail concept — header + visit timeline. Static mockup, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function PatientConceptPage() {
  return <PatientScreen />;
}
